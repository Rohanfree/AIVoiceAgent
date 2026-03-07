"""
vapi_models.py - Pydantic schemas for parsing Vapi webhook payloads.

Covers two webhook types:
  1. 'tool-calls'        - Fired when the AI invokes one of our server tools.
                           Contains call.assistantId which we use as client_id.
  2. 'end-of-call-report' - Fired when a call ends. Contains transcript/summary.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─── Nested call customer object ────────────────────────────────────────────

class VapiCustomer(BaseModel):
    """Represents the caller's phone details from Vapi."""

    model_config = ConfigDict(extra="ignore")

    number: Optional[str] = Field(
        default=None,
        description="The phone number that directly called the Vapi number.",
    )
    number_forwarded_from: Optional[str] = Field(
        default=None,
        description=(
            "When a call is forwarded, this is the ORIGINAL caller's number "
            "(Number 1 in: Number1 → Forwards → VapiNumber)."
        ),
    )


# ─── Nested call object ──────────────────────────────────────────────────────

class VapiCall(BaseModel):
    """Core call details from the Vapi webhook payload."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: Optional[str] = Field(default=None, description="Vapi's unique call ID.")
    assistant_id: Optional[str] = Field(
        default=None,
        alias="assistantId",
        description="The Vapi assistant ID — used as client_id for multi-tenancy.",
    )
    customer: Optional[VapiCustomer] = None
    ended_reason: Optional[str] = Field(
        default=None,
        description="Why the call ended (e.g. 'customer-ended-call', 'assistant-ended-call').",
    )
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Total call duration in seconds.",
    )


# ─── Nested message object ───────────────────────────────────────────────────

class VapiCallEndedMessage(BaseModel):
    """The inner 'message' object inside the Vapi webhook body."""

    model_config = ConfigDict(extra="ignore")

    type: Optional[str] = Field(
        default=None,
        description="Must be 'end-of-call-report' for call-ended events.",
    )
    call: Optional[VapiCall] = None
    transcript: Optional[str] = Field(
        default=None,
        description="Full transcript of the call conversation.",
    )
    summary: Optional[str] = Field(
        default=None,
        description="Auto-generated summary of the call.",
    )


# ─── Top-level call-ended webhook payload ────────────────────────────────────

class VapiCallEndedPayload(BaseModel):
    """Top-level body POSTed by Vapi for end-of-call-report events."""

    model_config = ConfigDict(extra="ignore")

    message: Optional[VapiCallEndedMessage] = None


# ─── Tool-call webhook models ─────────────────────────────────────────────────
# Vapi sends these when the AI invokes one of our server tools.
# The assistantId in message.call identifies WHICH client's agent is calling,
# so we use it as client_id on all tool endpoints.

class VapiToolCallFunction(BaseModel):
    """The function name + arguments extracted by the AI."""

    model_config = ConfigDict(extra="ignore")

    name: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None


class VapiToolCallItem(BaseModel):
    """A single tool invocation within the tool-calls event."""

    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = Field(default=None, description="Unique ID for this tool call; must be echoed in the response.")
    type: Optional[str] = None
    function: Optional[VapiToolCallFunction] = None


class VapiToolCallCall(BaseModel):
    """Minimal call metadata included in every Vapi webhook."""

    model_config = ConfigDict(extra="ignore")

    id: Optional[str] = None
    assistant_id: Optional[str] = Field(
        default=None,
        alias="assistantId",
        description="The Vapi assistant ID — used as client_id on all tool endpoints.",
    )

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class VapiToolCallMessage(BaseModel):
    """The inner 'message' object for tool-calls events."""

    model_config = ConfigDict(extra="ignore")

    type: Optional[str] = None
    call: Optional[VapiToolCallCall] = None
    tool_call_list: Optional[list[VapiToolCallItem]] = Field(
        default=None,
        alias="toolCallList",
    )

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class VapiToolCallPayload(BaseModel):
    """Top-level body POSTed by Vapi when the AI calls a server tool."""

    model_config = ConfigDict(extra="ignore")

    message: Optional[VapiToolCallMessage] = None
