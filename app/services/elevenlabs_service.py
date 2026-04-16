"""
elevenlabs_service.py — ElevenLabs Conversational AI integration.

Provides helpers for managing knowledge base documents and agent tool
configuration via the ElevenLabs Conversational AI REST API.
"""

import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"


def _headers() -> dict:
    return {
        "xi-api-key": settings.elevenlabs_api_key,
        "Content-Type": "application/json",
    }


async def create_or_replace_knowledge_base_doc(
    agent_id: str,
    text: str,
    name: str = "Business Info",
    old_doc_id: str | None = None,
) -> str | None:
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_api_key is not set — skipping knowledge base update")
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Delete old document if provided
            if old_doc_id:
                try:
                    del_resp = await client.delete(
                        f"{ELEVENLABS_BASE_URL}/convai/knowledge-base/{old_doc_id}",
                        headers=_headers(),
                    )
                    if del_resp.is_error:
                        logger.warning(
                            "Failed to delete old knowledge base doc %s: %s %s",
                            old_doc_id,
                            del_resp.status_code,
                            del_resp.text,
                        )
                except Exception as exc:
                    logger.warning("Exception deleting old knowledge base doc %s: %s", old_doc_id, exc)

            # Step 2: Create new knowledge base document
            create_resp = await client.post(
                f"{ELEVENLABS_BASE_URL}/convai/knowledge-base/text",
                headers=_headers(),
                json={"text": text, "name": name},
            )
            if create_resp.is_error:
                logger.error(
                    "Failed to create knowledge base doc: %s %s",
                    create_resp.status_code,
                    create_resp.text,
                )
                return None

            doc_id = create_resp.json().get("id")
            if not doc_id:
                logger.error("No 'id' in knowledge base create response: %s", create_resp.text)
                return None

            # Step 3: Attach document to agent
            patch_resp = await client.patch(
                f"{ELEVENLABS_BASE_URL}/convai/agents/{agent_id}",
                headers=_headers(),
                json={
                    "conversation_config": {
                        "agent": {
                            "prompt": {
                                "knowledge_base": [{"type": "file", "id": doc_id}]
                            }
                        }
                    }
                },
            )
            if patch_resp.is_error:
                logger.error(
                    "Failed to attach knowledge base doc %s to agent %s: %s %s",
                    doc_id,
                    agent_id,
                    patch_resp.status_code,
                    patch_resp.text,
                )
                return None

            return doc_id

    except Exception as exc:
        logger.error("create_or_replace_knowledge_base_doc error: %s", exc)
        return None


async def get_agent(agent_id: str) -> dict | None:
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_api_key is not set — skipping get_agent")
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{ELEVENLABS_BASE_URL}/convai/agents/{agent_id}",
                headers=_headers(),
            )
            if resp.is_error:
                logger.error(
                    "Failed to get agent %s: %s %s",
                    agent_id,
                    resp.status_code,
                    resp.text,
                )
                return None
            return resp.json()

    except Exception as exc:
        logger.error("get_agent error for agent %s: %s", agent_id, exc)
        return None


async def setup_agent_tools(agent_id: str, client_id: str) -> list[str] | None:
    """
    Create (or reuse) the 4 shared webhook tools and assign them to the agent.
    client_id is included as a required body param in every tool schema so the
    agent passes it on each call.
    """
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_api_key is not set — skipping setup_agent_tools")
        return None

    # Shared tool definitions — client_id is a required body param on every tool
    tool_definitions = [
        {
            "name": "get_customer",
            "description": "Look up a customer by their phone number to check if they are a returning customer and retrieve their history.",
            "request_body_schema": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "The client ID assigned to this agent"},
                    "customer_phone": {"type": "string", "description": "The caller's phone number"},
                },
                "required": ["client_id", "customer_phone"],
            },
            "url": f"{settings.base_url}/automiteaiapplication/elevenlabs-tools/get-customer",
        },
        {
            "name": "check_availability",
            "description": "Check if an appointment slot is available for a given service and date/time.",
            "request_body_schema": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "The client ID assigned to this agent"},
                    "service_name": {"type": "string", "description": "Name of the service to check"},
                    "date_time": {"type": "string", "description": "Requested date and time in ISO 8601 format"},
                    "duration_minutes": {"type": "number", "description": "Duration of the service in minutes (default 30)"},
                },
                "required": ["client_id", "service_name", "date_time"],
            },
            "url": f"{settings.base_url}/automiteaiapplication/elevenlabs-tools/check-availability",
        },
        {
            "name": "book_appointment",
            "description": "Book an appointment for a customer for a specific service at a given date and time.",
            "request_body_schema": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "The client ID assigned to this agent"},
                    "customer_name": {"type": "string", "description": "Full name of the customer"},
                    "customer_phone": {"type": "string", "description": "Phone number of the customer"},
                    "service_name": {"type": "string", "description": "Name of the service to book"},
                    "date_time": {"type": "string", "description": "Appointment date and time in ISO 8601 format"},
                },
                "required": ["client_id", "customer_name", "customer_phone", "service_name", "date_time"],
            },
            "url": f"{settings.base_url}/automiteaiapplication/elevenlabs-tools/book-appointment",
        },
        {
            "name": "save_call_summary",
            "description": "Save a summary and transcript of the call after it ends. Also logs to Google Sheets.",
            "request_body_schema": {
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "The client ID assigned to this agent"},
                    "caller_phone": {"type": "string", "description": "Phone number of the caller"},
                    "summary": {"type": "string", "description": "Summary of the call"},
                    "transcript": {"type": "string", "description": "Full transcript of the call"},
                    "duration_seconds": {"type": "number", "description": "Duration of the call in seconds"},
                    "customer_name": {"type": "string", "description": "Name of the customer if known"},
                },
                "required": ["client_id", "caller_phone", "summary"],
            },
            "url": f"{settings.base_url}/automiteaiapplication/elevenlabs-tools/save-call-summary",
        },
    ]

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            # Step 1: Fetch existing tools to avoid re-creating shared ones
            list_resp = await http.get(
                f"{ELEVENLABS_BASE_URL}/convai/tools",
                headers=_headers(),
            )
            existing_tools_map: dict[str, str] = {}  # name -> id
            if not list_resp.is_error:
                for t in list_resp.json().get("tools", []):
                    name = t.get("tool_config", {}).get("name")
                    tid = t.get("id")
                    if name and tid:
                        existing_tools_map[name] = tid

            # Step 2: Create any missing tools; collect all 4 IDs
            tool_ids: list[str] = []
            for tool in tool_definitions:
                if tool["name"] in existing_tools_map:
                    tid = existing_tools_map[tool["name"]]
                    tool_ids.append(tid)
                    logger.info("Tool '%s' already exists (id=%s)", tool["name"], tid)
                    continue

                create_resp = await http.post(
                    f"{ELEVENLABS_BASE_URL}/convai/tools",
                    headers=_headers(),
                    json={
                        "name": tool["name"],
                        "description": tool["description"],
                        "type": "webhook",
                        "tool_config": {
                            "type": "webhook",
                            "name": tool["name"],
                            "description": tool["description"],
                            "api_schema": {
                                "url": tool["url"],
                                "method": "POST",
                                "request_body_schema": tool["request_body_schema"],
                            },
                        },
                    },
                )
                if create_resp.is_error:
                    logger.error(
                        "Failed to create tool '%s': %s %s",
                        tool["name"], create_resp.status_code, create_resp.text,
                    )
                    return None

                tid = create_resp.json().get("id")
                tool_ids.append(tid)
                logger.info("Created tool '%s' (id=%s)", tool["name"], tid)

        logger.info("Successfully resolved %d tool(s) for agent %s", len(tool_ids), agent_id)
        return tool_ids

    except Exception as exc:
        logger.error("setup_agent_tools error for agent %s: %s", agent_id, exc)
        return None


async def create_kb_text_doc(text: str, name: str = "Business Info") -> str | None:
    """Create a knowledge base text document and return its ID. Does not attach to any agent."""
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_api_key is not set — skipping create_kb_text_doc")
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{ELEVENLABS_BASE_URL}/convai/knowledge-base/text",
                headers=_headers(),
                json={"text": text, "name": name},
            )
            if resp.is_error:
                logger.error("create_kb_text_doc failed: %s %s", resp.status_code, resp.text)
                return None
            doc_id = resp.json().get("id")
            if not doc_id:
                logger.error("No 'id' in KB create response: %s", resp.text)
                return None
            return doc_id
    except Exception as exc:
        logger.error("create_kb_text_doc error: %s", exc)
        return None


async def patch_agent_full(agent_id: str, tool_ids: list[str], kb_doc_ids: list[str]) -> bool:
    """Single PATCH that sets both tool_ids and knowledge_base on an agent."""
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_api_key is not set — skipping patch_agent_full")
        return False
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(
                f"{ELEVENLABS_BASE_URL}/convai/agents/{agent_id}",
                headers=_headers(),
                json={
                    "conversation_config": {
                        "agent": {
                            "prompt": {
                                "tool_ids": tool_ids,
                                "knowledge_base": [{"type": "file", "id": did} for did in kb_doc_ids],
                            }
                        }
                    }
                },
            )
            if resp.is_error:
                logger.error(
                    "patch_agent_full failed for agent %s: %s %s",
                    agent_id, resp.status_code, resp.text,
                )
                return False
            logger.info("patch_agent_full: agent %s updated with %d tools and %d KB docs", agent_id, len(tool_ids), len(kb_doc_ids))
            return True
    except Exception as exc:
        logger.error("patch_agent_full error for agent %s: %s", agent_id, exc)
        return False
