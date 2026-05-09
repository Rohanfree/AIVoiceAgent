"""
elevenlabs_service.py — ElevenLabs Conversational AI integration.

Provides helpers for managing knowledge base documents and agent tool
configuration via the ElevenLabs Conversational AI REST API.
"""

import asyncio
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


async def list_agents(search: str | None = None, cursor: str | None = None, page_size: int = 30) -> dict:
    """List ElevenLabs ConvAI agents. Returns { agents, next_cursor, has_more }."""
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_api_key is not set — skipping list_agents")
        return {"agents": [], "next_cursor": None, "has_more": False}

    params: dict = {"page_size": page_size}
    if search:
        params["search"] = search
    if cursor:
        params["cursor"] = cursor

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{ELEVENLABS_BASE_URL}/convai/agents",
                headers=_headers(),
                params=params,
            )
            if resp.is_error:
                logger.error("list_agents failed: %s %s", resp.status_code, resp.text)
                return {"agents": [], "next_cursor": None, "has_more": False}
            data = resp.json()
            return {
                "agents": data.get("agents", []),
                "next_cursor": data.get("next_cursor"),
                "has_more": data.get("has_more", False),
            }
    except Exception as exc:
        logger.error("list_agents error: %s", exc)
        return {"agents": [], "next_cursor": None, "has_more": False}


async def duplicate_agent(agent_id: str, name: str | None = None) -> str | None:
    """Duplicate an ElevenLabs agent. Returns the new agent_id or None on failure."""
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_api_key is not set — skipping duplicate_agent")
        return None

    body = {}
    if name:
        body["name"] = name

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{ELEVENLABS_BASE_URL}/convai/agents/{agent_id}/duplicate",
                headers=_headers(),
                json=body,
            )
            if resp.is_error:
                logger.error("duplicate_agent failed for %s: %s %s", agent_id, resp.status_code, resp.text)
                return None
            new_id = resp.json().get("agent_id")
            logger.info("Duplicated agent %s → new agent %s", agent_id, new_id)
            return new_id
    except Exception as exc:
        logger.error("duplicate_agent error for %s: %s", agent_id, exc)
        return None


async def update_agent_system_prompt(agent_id: str, prompt: str) -> bool:
    """Replace the system prompt on an agent (does not touch Automite config block)."""
    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_api_key is not set — skipping update_agent_system_prompt")
        return False
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(
                f"{ELEVENLABS_BASE_URL}/convai/agents/{agent_id}",
                headers=_headers(),
                json={
                    "conversation_config": {
                        "agent": {
                            "prompt": {"prompt": prompt}
                        }
                    }
                },
            )
            if resp.is_error:
                logger.error("update_agent_system_prompt failed for %s: %s %s", agent_id, resp.status_code, resp.text)
                return False
            logger.info("System prompt updated for agent %s", agent_id)
            return True
    except Exception as exc:
        logger.error("update_agent_system_prompt error for %s: %s", agent_id, exc)
        return False


async def _fetch_conversation_credits(conversation_id: str, http: httpx.AsyncClient) -> int:
    """
    Fetch a conversation's total credit cost from metadata.cost.
    ElevenLabs uses credits as the billing unit (1 credit ≈ 1 TTS character).
    tts_usage is null for ConvAI phone/agent calls; metadata.cost is the reliable field.
    """
    try:
        resp = await http.get(
            f"{ELEVENLABS_BASE_URL}/convai/conversations/{conversation_id}",
            headers=_headers(),
        )
        if resp.is_error:
            return 0
        data = resp.json()
        meta = data.get("metadata", {}) or {}
        return int(meta.get("cost", 0) or 0)
    except Exception:
        return 0


def _usage_cache_key(agent_id: str, year: int, month: int) -> str:
    return f"{agent_id}_{year:04d}_{month:02d}"


async def _load_usage_cache(agent_id: str, year: int, month: int) -> dict | None:
    """Return cached usage from Firestore, or None if stale/missing."""
    from datetime import datetime, timezone
    from app.db import get_firestore_client
    try:
        db = get_firestore_client()
        doc = db.collection("usage_cache").document(_usage_cache_key(agent_id, year, month)).get()
        if not doc.exists:
            return None
        cached = doc.to_dict()

        now = datetime.now(tz=timezone.utc)
        is_current_month = (now.year == year and now.month == month)

        if is_current_month:
            # Stale after 1 hour for current month
            fetched_at_str = cached.get("fetched_at", "")
            if fetched_at_str:
                fetched_at = datetime.fromisoformat(fetched_at_str)
                if (now - fetched_at).total_seconds() < 3600:
                    return cached
            return None
        else:
            # Past months never expire
            return cached
    except Exception as exc:
        logger.warning("_load_usage_cache error: %s", exc)
        return None


async def _save_usage_cache(agent_id: str, year: int, month: int, data: dict) -> None:
    """Persist only aggregate totals to Firestore — no conversation rows."""
    from datetime import datetime, timezone
    from app.db import get_firestore_client
    try:
        db = get_firestore_client()
        payload = {
            "total_characters": data.get("total_characters", 0),
            "conversation_count": data.get("conversation_count", 0),
            "total_duration_secs": data.get("total_duration_secs", 0),
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        db.collection("usage_cache").document(_usage_cache_key(agent_id, year, month)).set(payload)
    except Exception as exc:
        logger.warning("_save_usage_cache error: %s", exc)


async def get_agent_usage(agent_id: str, start_unix_secs: int, end_unix_secs: int) -> dict:
    """
    Fetch credit usage for an agent over a date range.

    Caching strategy:
      - Firestore cache stores ONLY aggregate totals (3 numbers, ~200 bytes/doc).
        Conversation rows are never persisted — too much storage for large accounts.
      - On a cache hit the aggregates are returned immediately. The conversation
        breakdown is then fetched fresh (conversations list + parallel detail calls)
        so the UI always shows up-to-date rows.
      - Past months cached permanently; current month TTL = 1 hour.
    """
    from datetime import datetime, timezone

    _empty = {"total_characters": 0, "conversation_count": 0, "total_duration_secs": 0, "conversations": []}

    if not settings.elevenlabs_api_key:
        logger.warning("elevenlabs_api_key is not set — skipping get_agent_usage")
        return _empty

    # Determine if range is within a single calendar month → enable caching
    start_dt = datetime.fromtimestamp(start_unix_secs, tz=timezone.utc)
    end_dt = datetime.fromtimestamp(end_unix_secs, tz=timezone.utc)
    single_month = (start_dt.year == end_dt.year and start_dt.month == end_dt.month)

    cached_totals: dict | None = None
    if single_month:
        cached_totals = await _load_usage_cache(agent_id, start_dt.year, start_dt.month)
        if cached_totals:
            logger.info("get_agent_usage: aggregate cache hit for agent %s %d-%02d", agent_id, start_dt.year, start_dt.month)

    all_conversations: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=60.0) as http:
            # Step 1 — paginate conversation list (always needed for the breakdown)
            cursor = None
            while True:
                params: dict = {
                    "agent_id": agent_id,
                    "call_start_after_unix": start_unix_secs,
                    "call_start_before_unix": end_unix_secs,
                    "page_size": 100,
                }
                if cursor:
                    params["cursor"] = cursor

                resp = await http.get(
                    f"{ELEVENLABS_BASE_URL}/convai/conversations",
                    headers=_headers(),
                    params=params,
                )
                if resp.is_error:
                    logger.error("get_agent_usage: conversations list failed: %s %s", resp.status_code, resp.text)
                    break

                data = resp.json()
                page_convos = data.get("conversations", [])
                all_conversations.extend(page_convos)

                if not data.get("has_more") or not page_convos:
                    break
                cursor = data.get("next_cursor")

            # Step 2 — fetch per-conversation credit cost in parallel (batches of 20).
            # Skip if we already have cached totals — saves N individual API calls.
            convo_ids = [c["conversation_id"] for c in all_conversations if c.get("conversation_id")]
            credit_map: dict[str, int] = {}

            if not cached_totals:
                for i in range(0, len(convo_ids), 20):
                    batch = convo_ids[i:i + 20]
                    results = await asyncio.gather(
                        *[_fetch_conversation_credits(cid, http) for cid in batch],
                        return_exceptions=True,
                    )
                    for cid, credits in zip(batch, results):
                        credit_map[cid] = credits if isinstance(credits, int) else 0

    except Exception as exc:
        logger.error("get_agent_usage error for agent %s: %s", agent_id, exc)

    # Step 3 — build response
    rows = []
    total_credits = 0
    total_duration = 0

    for c in all_conversations:
        cid = c.get("conversation_id", "")
        credits = credit_map.get(cid, 0)
        duration = c.get("call_duration_secs", 0) or 0
        total_credits += credits
        total_duration += duration
        rows.append({
            "conversation_id": cid,
            "start_time_unix_secs": c.get("start_time_unix_secs"),
            "call_duration_secs": duration,
            "characters": credits,   # ElevenLabs credits (0 when served from cache)
            "call_summary_title": c.get("call_summary_title") or c.get("transcript_summary") or "",
            "call_successful": c.get("call_successful"),
            "status": c.get("status", ""),
        })

    rows.sort(key=lambda r: r.get("start_time_unix_secs") or 0, reverse=True)

    # Use cached totals if available (avoids N individual detail calls)
    if cached_totals:
        total_credits = cached_totals.get("total_characters", total_credits)
        total_duration = cached_totals.get("total_duration_secs", total_duration)

    result = {
        "total_characters": total_credits,
        "conversation_count": len(all_conversations),
        "total_duration_secs": total_duration,
        "conversations": rows,
    }

    # Cache aggregates only — never persist conversation rows
    if single_month and not cached_totals and all_conversations:
        await _save_usage_cache(agent_id, start_dt.year, start_dt.month, result)

    return result


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


