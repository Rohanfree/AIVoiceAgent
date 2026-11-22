"""Campaign import and provider preference endpoints for authenticated clients."""

import csv
import io
import logging
from datetime import datetime, timezone

import httpx

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from google.cloud.firestore import Client

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/client-portal/campaigns", tags=["Campaigns"])
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
REQUIRED_FIELDS = ("name", "phone", "do_not_call")
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"


def _elevenlabs_headers() -> dict:
    if not settings.elevenlabs_api_key:
        raise HTTPException(status_code=503, detail="ElevenLabs API key is not configured.")
    return {"xi-api-key": settings.elevenlabs_api_key, "Content-Type": "application/json"}


async def _elevenlabs_request(method: str, path: str, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, f"{ELEVENLABS_BASE_URL}{path}", headers=_elevenlabs_headers(), **kwargs)
    except httpx.HTTPError as exc:
        logger.warning("ElevenLabs campaign API request failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Unable to reach ElevenLabs campaign API.") from exc
    if response.is_error:
        logger.warning("ElevenLabs campaign API returned HTTP %s", response.status_code)
        raise HTTPException(status_code=502, detail="ElevenLabs rejected the campaign request.")
    return response.json()


def _client_id(user: dict) -> str:
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=404, detail="No client profile associated with this account.")
    return client_id


@router.get("/phone-numbers")
async def list_campaign_phone_numbers(user: dict = Depends(get_current_user)) -> dict:
    numbers = await _elevenlabs_request("GET", "/convai/phone-numbers")
    return {"phone_numbers": [
        {"phone_number_id": item.get("phone_number_id"), "label": item.get("label") or "Phone number",
         "phone_number": item.get("phone_number"), "provider": item.get("provider")}
        for item in numbers if item.get("phone_number_id") and item.get("phone_number")
    ]}


@router.get("/agent")
async def get_campaign_agent(user: dict = Depends(get_current_user), db: Client = Depends(get_db)) -> dict:
    client_id = _client_id(user)
    doc = db.collection("clients").document(client_id).get()
    data = doc.to_dict() if doc.exists else {}
    agent_id = data.get("elevenlabs_agent_id")
    if not agent_id:
        raise HTTPException(status_code=404, detail="No ElevenLabs agent is linked to this client.")
    from app.services.elevenlabs_service import get_agent
    agent = (await get_agent(agent_id)) or {}
    if not agent:
        raise HTTPException(status_code=502, detail="The linked ElevenLabs agent could not be retrieved.")
    return {"agent_id": agent.get("agent_id", agent_id), "name": agent.get("name", "Unnamed agent")}



@router.get("/template.csv")
async def download_template(user: dict = Depends(get_current_user)):
    from fastapi.responses import StreamingResponse
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["name", "phone", "do_not_call", "preferred_language", "notes"])
    writer.writerow(["Example Contact", "+15551234567", "false", "en", "Replace with consented contact data"])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=automite-campaign-template.csv"})


@router.post("/upload")
async def upload_campaign(file: UploadFile = File(...), user: dict = Depends(get_current_user)) -> dict:
    filename = (file.filename or "").lower()
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload must be 5 MB or smaller.")
    if filename.endswith(".csv"):
        try:
            rows = list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid CSV: {exc}") from exc
    elif filename.endswith(".xlsx"):
        try:
            from openpyxl import load_workbook
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheet = workbook.active
            values = sheet.iter_rows(values_only=True)
            headers = [str(value).strip().lower() if value is not None else "" for value in next(values, ())]
            rows = [dict(zip(headers, row)) for row in values]
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid XLSX workbook: {exc}") from exc
    else:
        raise HTTPException(status_code=400, detail="Choose a .csv or .xlsx file.")
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=413, detail=f"Maximum {MAX_ROWS} contacts per upload.")
    if not rows:
        raise HTTPException(status_code=400, detail="The uploaded file contains no contact rows.")
    headers = {str(key).strip().lower() for key in rows[0]}
    missing = [field for field in REQUIRED_FIELDS if field not in headers]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {', '.join(missing)}")
    errors, normalized = [], []
    for number, row in enumerate(rows, start=2):
        data = {str(key).strip().lower(): ("" if value is None else str(value).strip()) for key, value in row.items()}
        issues = []
        if not data.get("name"):
            issues.append("name is required")
        phone = data.get("phone", "")
        if not phone or len(phone) > 40 or not any(char.isdigit() for char in phone):
            issues.append("phone is required and must contain digits")
        consent = data.get("do_not_call", "").lower()
        if consent not in {"true", "false", "yes", "no", "1", "0"}:
            issues.append("do_not_call must be true/false, yes/no, or 1/0")
        if issues:
            errors.append({"row": number, "issues": issues})
        else:
            normalized.append({**data, "do_not_call": consent in {"true", "yes", "1"}})
    return {"filename": file.filename, "total_rows": len(rows), "valid_rows": len(normalized), "invalid_rows": len(errors), "errors": errors[:100], "contacts": normalized if not errors else [], "launch_available": not errors, "excluded_do_not_call": sum(row["do_not_call"] for row in normalized)}


@router.post("/launch")
async def launch_campaign(body: dict, user: dict = Depends(get_current_user), db: Client = Depends(get_db)) -> dict:
    client_id = _client_id(user)
    doc = db.collection("clients").document(client_id).get()
    data = doc.to_dict() if doc.exists else {}
    agent_id = data.get("elevenlabs_agent_id")
    if not agent_id:
        raise HTTPException(status_code=404, detail="No ElevenLabs agent is linked to this client.")
    phone_number_id = body.get("phone_number_id")
    contacts = body.get("contacts")
    if not isinstance(contacts, list) or not contacts or len(contacts) > MAX_ROWS:
        raise HTTPException(status_code=400, detail="A validated contact list of 1–5000 rows is required.")
    if not phone_number_id:
        raise HTTPException(status_code=400, detail="Select an existing ElevenLabs phone number.")
    phone_numbers = await _elevenlabs_request("GET", "/convai/phone-numbers")
    if not any(item.get("phone_number_id") == phone_number_id for item in phone_numbers):
        raise HTTPException(status_code=400, detail="Selected phone number is not configured in this ElevenLabs account.")
    recipients = []
    for row in contacts:
        if not isinstance(row, dict) or row.get("do_not_call") is not False:
            continue
        phone = str(row.get("phone", "")).strip()
        if not phone or len(phone) > 40 or not any(char.isdigit() for char in phone):
            raise HTTPException(status_code=400, detail="Contact list failed server-side validation.")
        variables = {key: value for key, value in row.items() if key not in {"phone", "do_not_call"}}
        recipients.append({"phone_number": phone, "conversation_initiation_client_data": {"dynamic_variables": variables}})
    if not recipients:
        raise HTTPException(status_code=400, detail="No callable contacts remain after do-not-call filtering.")
    result = await _elevenlabs_request("POST", "/convai/batch-calling/submit", json={
        "call_name": str(body.get("call_name") or f"Campaign {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"),
        "agent_id": agent_id,
        "agent_phone_number_id": phone_number_id,
        "recipients": recipients,
    })
    return {"batch_id": result.get("id"), "status": result.get("status"), "scheduled_recipients": len(recipients), "excluded_do_not_call": len(contacts) - len(recipients)}
