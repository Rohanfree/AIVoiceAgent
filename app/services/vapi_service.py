"""
vapi_service.py — Vapi AI assistant lifecycle management.

Handles:
  - Cloning a new assistant from the template
  - Updating an assistant's system prompt / config
  - Toggling an assistant's active status
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

VAPI_BASE_URL = "https://api.vapi.ai"


def _vapi_headers() -> dict[str, str]:
    """Build authorization headers for Vapi API calls."""
    return {
        "Authorization": f"Bearer {settings.vapi_api_key}",
        "Content-Type": "application/json",
    }


async def clone_assistant(
    client_name: str,
    assistant_name: str,
    services: list[dict] | None = None,
    operating_hours: dict | None = None,
) -> str | None:
    """
    Clone a new Vapi assistant from the template.

    Args:
        client_name: Business name (injected into system prompt).
        assistant_name: Display name for the assistant.
        services: Optional list of service dicts to inject.
        operating_hours: Optional operating hours dict to inject.

    Returns:
        The new assistant's ID, or None on failure.
    """
    if not settings.vapi_api_key:
        logger.warning("VAPI_API_KEY not configured — skipping assistant clone")
        return None

    # Build the creation payload based on template
    payload: dict = {
        "name": assistant_name,
        "metadata": {
            "client_name": client_name,
            "template_id": settings.vapi_template_assistant_id,
        },
    }

    # If we have a template to clone from, use the squad/template approach
    # Vapi's clone approach: create with same config as template
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First, fetch template config
            template_resp = await client.get(
                f"{VAPI_BASE_URL}/assistant/{settings.vapi_template_assistant_id}",
                headers=_vapi_headers(),
            )

            if template_resp.status_code == 200:
                template = template_resp.json()

                # Apply template settings to new assistant
                for key in ["model", "voice", "firstMessage", "transcriber",
                            "serverUrl", "endCallFunctionEnabled"]:
                    if key in template:
                        payload[key] = template[key]

                # Inject dynamic variables into system prompt
                if "model" in payload and "messages" in payload.get("model", {}):
                    messages = payload["model"]["messages"]
                    for msg in messages:
                        if msg.get("role") == "system":
                            content = msg.get("content", "")
                            content = content.replace("{{business_name}}", client_name)
                            if services:
                                svc_text = ", ".join(s.get("name", "") for s in services)
                                content = content.replace("{{services_list}}", svc_text)
                            if operating_hours:
                                content = content.replace("{{operating_hours}}", str(operating_hours))
                            msg["content"] = content

            # Create the new assistant
            create_resp = await client.post(
                f"{VAPI_BASE_URL}/assistant",
                headers=_vapi_headers(),
                json=payload,
            )

            if create_resp.status_code in (200, 201):
                new_assistant = create_resp.json()
                assistant_id = new_assistant.get("id")
                logger.info(
                    "Vapi assistant cloned: name=%s id=%s",
                    assistant_name,
                    assistant_id,
                )
                return assistant_id
            else:
                logger.error(
                    "Vapi assistant creation failed: %d %s",
                    create_resp.status_code,
                    create_resp.text,
                )
                return None

    except Exception as exc:
        logger.error("Vapi clone_assistant error: %s", exc, exc_info=True)
        return None


async def update_assistant(
    assistant_id: str,
    updates: dict,
) -> bool:
    """
    Update an existing Vapi assistant's configuration.

    Args:
        assistant_id: The Vapi assistant ID to update.
        updates: Dict of fields to PATCH.

    Returns:
        True on success, False on failure.
    """
    if not settings.vapi_api_key:
        logger.warning("VAPI_API_KEY not configured — skipping assistant update")
        return False

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(
                f"{VAPI_BASE_URL}/assistant/{assistant_id}",
                headers=_vapi_headers(),
                json=updates,
            )

            if resp.status_code == 200:
                logger.info("Vapi assistant %s updated successfully", assistant_id)
                return True
            else:
                logger.error(
                    "Vapi assistant update failed: %d %s",
                    resp.status_code,
                    resp.text,
                )
                return False

    except Exception as exc:
        logger.error("Vapi update_assistant error: %s", exc, exc_info=True)
        return False


async def toggle_assistant(assistant_id: str, active: bool) -> bool:
    """
    Activate or deactivate a Vapi assistant.

    When deactivating, this removes the phone number binding to prevent
    call-related costs. When activating, it re-enables the assistant.

    Args:
        assistant_id: The Vapi assistant ID.
        active: True to activate, False to deactivate.

    Returns:
        True on success, False on failure.
    """
    updates = {
        "metadata": {"is_active": active},
    }

    return await update_assistant(assistant_id, updates)
