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


async def patch_agent_first_message(agent_id: str, first_message: str) -> bool:
    """Update the agent's opening first_message."""
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_api_key is not set — skipping patch_agent_first_message")
        return False
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(
                f"{ELEVENLABS_BASE_URL}/convai/agents/{agent_id}",
                headers=_headers(),
                json={
                    "conversation_config": {
                        "agent": {
                            "first_message": first_message,
                        }
                    }
                },
            )
            if resp.is_error:
                logger.error(
                    "patch_agent_first_message failed for agent %s: %s %s",
                    agent_id, resp.status_code, resp.text,
                )
                return False
            logger.info("First message updated for agent %s", agent_id)
            return True
    except Exception as exc:
        logger.error("patch_agent_first_message error for agent %s: %s", agent_id, exc)
        return False


async def patch_agent_tools(agent_id: str, tool_ids: list[str]) -> bool:
    """PATCH only the tool_ids on an agent. Does not touch knowledge_base."""
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_api_key is not set — skipping patch_agent_tools")
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
                            }
                        }
                    }
                },
            )
            if resp.is_error:
                logger.error(
                    "patch_agent_tools failed for agent %s: %s %s",
                    agent_id, resp.status_code, resp.text,
                )
                return False
            logger.info("patch_agent_tools: agent %s updated with %d tools", agent_id, len(tool_ids))
            return True
    except Exception as exc:
        logger.error("patch_agent_tools error for agent %s: %s", agent_id, exc)
        return False


_BLOCK_START = "--- Automite Client Config ---"
_BLOCK_END = "--- End Automite Client Config ---"


async def inject_client_context_into_prompt(
    agent_id: str,
    client_id: str,
    business_info: str = "",
) -> bool:
    """
    Inject client_id and business_info into the agent's system prompt.
    Replaces any previously injected Automite block so re-runs are idempotent.
    """
    import re

    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_api_key is not set — skipping inject_client_context_into_prompt")
        return False

    agent_data = await get_agent(agent_id)
    if not agent_data:
        logger.error("inject_client_context_into_prompt: could not fetch agent %s", agent_id)
        return False

    current_prompt = (
        agent_data
        .get("conversation_config", {})
        .get("agent", {})
        .get("prompt", {})
        .get("prompt", "")
    ) or ""

    # Strip any existing injected block
    cleaned = re.sub(
        rf"\n*{re.escape(_BLOCK_START)}.*?{re.escape(_BLOCK_END)}",
        "",
        current_prompt,
        flags=re.DOTALL,
    ).rstrip()

    # Build the new block
    block_parts = [f"Your client_id is: {client_id}"]
    if business_info.strip():
        block_parts.append(business_info.strip())

    new_block = (
        f"\n\n{_BLOCK_START}\n"
        + "\n\n".join(block_parts)
        + f"\n{_BLOCK_END}"
    )
    new_prompt = cleaned + new_block

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.patch(
                f"{ELEVENLABS_BASE_URL}/convai/agents/{agent_id}",
                headers=_headers(),
                json={
                    "conversation_config": {
                        "agent": {
                            "prompt": {"prompt": new_prompt}
                        }
                    }
                },
            )
            if resp.is_error:
                logger.error(
                    "inject_client_context_into_prompt failed for agent %s: %s %s",
                    agent_id, resp.status_code, resp.text,
                )
                return False
            logger.info("Client context injected into prompt for agent %s", agent_id)
            return True
    except Exception as exc:
        logger.error("inject_client_context_into_prompt error for agent %s: %s", agent_id, exc)
        return False


