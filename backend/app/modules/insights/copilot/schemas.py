"""
Phase 5B -- Copilot chat API contract.

Two distinct schema layers, matching the existing insights/ai/schemas.py pattern
(section 9 of that module's own docstring: "never trust raw LLM text"):

  1. CopilotChatRequest / CopilotChatResponse -- the public HTTP contract.
  2. CopilotAnswer -- the internal, validated shape the AI provider's raw text
     must parse into before anything derived from it is returned to the client.
     Anything that fails this validation is treated as a provider failure, same
     as the existing incident-analysis path, never surfaced as a "raw" answer.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field, field_validator

_MAX_MESSAGE_LEN = 2000
_MAX_HISTORY_TURNS = 12  # user+assistant pairs; stateless, client-supplied (see prompt.py)
_MAX_ANSWER_LEN = 3000
_MAX_CITATIONS = 10


class CopilotChatTurn(BaseModel):
    """One prior turn, as the client already has it. The server holds no
    conversation state -- the client resends history each call, same pattern the
    codebase already documents for stateless AI integrations."""

    role: str  # "user" | "assistant"
    content: str = Field(max_length=_MAX_MESSAGE_LEN)

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str) -> str:
        if v not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        return v


class CopilotChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=_MAX_MESSAGE_LEN)
    history: list[CopilotChatTurn] = Field(default_factory=list, max_length=_MAX_HISTORY_TURNS)
    # Optional: scope the answer to one incident the user is currently looking at.
    incident_id: uuid.UUID | None = None


class CopilotCitation(BaseModel):
    incident_id: uuid.UUID
    label: str = Field(max_length=200)


class CopilotChatResponse(BaseModel):
    answer: str = Field(max_length=_MAX_ANSWER_LEN)
    citations: list[CopilotCitation] = Field(default_factory=list, max_length=_MAX_CITATIONS)
    grounded: bool  # False when answered from a canned/fallback path, not the AI provider
    disclaimer: str


class CopilotAnswer(BaseModel):
    """The ONLY shape the AI provider's raw text is allowed to take -- mirrors
    insights/ai/schemas.py's AIAnalysisResult. citations reference incident IDs
    that were actually present in the context this request assembled; the
    validator below drops any the model hallucinates rather than trusting them."""

    answer: str = Field(max_length=_MAX_ANSWER_LEN)
    citations: list[str] = Field(default_factory=list, max_length=_MAX_CITATIONS)


class CopilotValidationError(Exception):
    """Raised when the provider's raw response fails to parse as JSON or fails
    CopilotAnswer validation. Always caught by service.py -- never propagates a
    raw/unvalidated model response to the client."""


def parse_and_validate(raw_text: str) -> CopilotAnswer:
    import json

    try:
        payload = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise CopilotValidationError(f"Copilot response was not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise CopilotValidationError("Copilot response JSON must be an object")

    try:
        return CopilotAnswer.model_validate(payload)
    except Exception as exc:  # pydantic.ValidationError, kept broad deliberately -- see ai/schemas.py precedent
        raise CopilotValidationError(f"Copilot response failed schema validation: {exc}") from exc
