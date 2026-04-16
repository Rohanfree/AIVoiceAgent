"""
client_router.py — Client portal endpoints under /automiteui/client-portal/*.

Authenticated routes for clients to manage their profile, view appointments,
and access call logs. All routes require a 'dashboard' scope JWT.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore import Client

from app.auth.dependencies import get_current_user
from app.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/client-portal",
    tags=["Client Portal"],
)


# ─── GET PROFILE ────────────────────────────────────────────────────────────

@router.get(
    "/profile",
    summary="Get current client's profile",
)
async def get_profile(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    """Fetch the authenticated client's full profile from Firestore."""
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No client profile associated with this account.",
        )

    doc = db.collection("clients").document(client_id).get()
    if not doc.exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client profile not found.",
        )

    data = doc.to_dict()
    return data


# ─── UPDATE PROFILE ─────────────────────────────────────────────────────────

@router.put(
    "/profile",
    summary="Update client's services, timings, and business info",
)
async def update_profile(  # noqa: C901
    updates: dict,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    """
    Update the client's profile. Accepted fields:
    - business_name, services, operating_hours, policies, currency
    """
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No client profile associated with this account.",
        )

    allowed_fields = {"business_name", "services", "operating_hours", "policies", "currency", "knowledge_base_text"}
    filtered = {k: v for k, v in updates.items() if k in allowed_fields}

    if not filtered:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No valid fields to update. Allowed: {allowed_fields}",
        )

    from datetime import datetime, timezone
    filtered["updated_at"] = datetime.now(tz=timezone.utc).isoformat()

    # Sync knowledge base text to ElevenLabs before saving to Firestore
    if "knowledge_base_text" in filtered:
        kb_text = filtered["knowledge_base_text"]
        client_doc = db.collection("clients").document(client_id).get()
        client_data = client_doc.to_dict() if client_doc.exists else {}
        agent_id = client_data.get("elevenlabs_agent_id")
        old_doc_id = client_data.get("kb_doc_id")

        if agent_id and kb_text:
            try:
                from app.services.elevenlabs_service import create_or_replace_knowledge_base_doc
                new_doc_id = await create_or_replace_knowledge_base_doc(
                    agent_id=agent_id,
                    text=kb_text,
                    name=f"Business Info — {client_data.get('business_name', client_id)}",
                    old_doc_id=old_doc_id,
                )
                if new_doc_id:
                    filtered["kb_doc_id"] = new_doc_id
                    logger.info("Knowledge base updated for client %s → doc %s", client_id, new_doc_id)
            except Exception as exc:
                logger.error("ElevenLabs KB update failed for client %s: %s", client_id, exc)
        elif agent_id and not kb_text and old_doc_id:
            # Empty text → delete existing doc from ElevenLabs
            try:
                import httpx
                from app.config import settings as _settings
                async with httpx.AsyncClient(timeout=15.0) as hclient:
                    await hclient.delete(
                        f"https://api.elevenlabs.io/v1/convai/knowledge-base/{old_doc_id}",
                        headers={"xi-api-key": _settings.elevenlabs_api_key},
                    )
                filtered["kb_doc_id"] = None
                logger.info("Knowledge base doc %s deleted for client %s", old_doc_id, client_id)
            except Exception as exc:
                logger.error("ElevenLabs KB delete failed for client %s: %s", client_id, exc)

    db.collection("clients").document(client_id).set(filtered, merge=True)
    logger.info("Client %s profile updated: %s", client_id, list(filtered.keys()))

    return {"status": "updated", "fields": list(filtered.keys())}


# ─── LIST APPOINTMENTS ───────────────────────────────────────────────────────

@router.get(
    "/appointments",
    summary="List appointments for the current client",
)
async def list_appointments(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    """Fetch all appointments for the authenticated client."""
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No client profile.")

    docs = db.collection("appointments").where("client_id", "==", client_id).stream()
    appointments = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        appointments.append(data)

    # Sort by date_time descending
    appointments.sort(key=lambda x: x.get("date_time", ""), reverse=True)

    return {"client_id": client_id, "total": len(appointments), "appointments": appointments}


# ─── LIST CALL LOGS ──────────────────────────────────────────────────────────

@router.get(
    "/call-logs",
    summary="List call logs for the current client",
)
async def list_call_logs(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
) -> dict:
    """Fetch all call logs for the authenticated client."""
    client_id = user.get("client_id")
    if not client_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No client profile.")

    docs = db.collection("call_logs").where("client_id", "==", client_id).stream()
    logs = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        logs.append(data)

    # Sort by created_at descending
    logs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {"client_id": client_id, "total": len(logs), "call_logs": logs}


# ─── PARSE TEXT (AI AUTO-FILL) ───────────────────────────────────────────────

from pydantic import BaseModel, Field

class ParseTextRequest(BaseModel):
    text: str

class ExtractedService(BaseModel):
    name: str = Field(description="Name of the service", default="Unnamed Service")
    category: str = Field(description="Category of the service, e.g., Haircut, Consultation", default="General")
    duration: int = Field(description="Duration in minutes", default=30)
    price: float = Field(description="Price of the service", default=0.0)

class ExtractedOperatingHours(BaseModel):
    Monday: str = Field(description="Hours for Monday, e.g. 09:00 - 17:00 or Closed", default="Closed")
    Tuesday: str = Field(description="Hours for Tuesday", default="Closed")
    Wednesday: str = Field(description="Hours for Wednesday", default="Closed")
    Thursday: str = Field(description="Hours for Thursday", default="Closed")
    Friday: str = Field(description="Hours for Friday", default="Closed")
    Saturday: str = Field(description="Hours for Saturday", default="Closed")
    Sunday: str = Field(description="Hours for Sunday", default="Closed")

class ProfileExtraction(BaseModel):
    services: list[ExtractedService]
    operating_hours: ExtractedOperatingHours

@router.post(
    "/parse-text",
    summary="Parse raw text into structured services and operating hours using Gemini",
)
async def parse_text(
    body: ParseTextRequest,
    user: dict = Depends(get_current_user)
) -> dict:
    """Uses Gemini API to extract services and operating hours from unstructured text."""
    from app.config import settings
    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gemini API key is not configured.",
        )

    try:
        from google import genai
        from google.genai import types
        import json

        client = genai.Client(api_key=settings.gemini_api_key)
        
        prompt = f"""
        Extract the business services and operating hours from the following text.
        If a detail is missing, provide a reasonable default (e.g., 30 mins, price 0, or 'Closed').
        
        Text:
        {body.text}
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ProfileExtraction,
                temperature=0.1,
            ),
        )
        
        parsed_data = json.loads(response.text)
        return parsed_data
        
    except Exception as exc:
        logger.error("Failed to parse text with Gemini: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI extraction failed: {str(exc)}"
        )

