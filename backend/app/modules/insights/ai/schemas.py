"""
Phase 3 -- structured AI output contract (section 9). "Never trust raw LLM text":
the provider abstraction requires the model to return JSON matching this schema,
and this module is where that JSON gets validated before it ever touches the
database or the API response. Anything that doesn't validate is treated as a
provider failure (fails safely -- see service.py) rather than stored or shown.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.modules.insights.models import ConfidenceLevel

_VALID_CONFIDENCE_LEVELS = {level.value for level in ConfidenceLevel}
_VALID_SEVERITIES = {"info", "warning", "critical"}

# Hard caps so a misbehaving or adversarially-influenced model can't return a
# multi-megabyte blob that gets stored or rendered.
_MAX_SUMMARY_LEN = 1000
_MAX_CAUSE_LEN = 500
_MAX_LIST_ITEMS = 10
_MAX_LIST_ITEM_LEN = 500


class AIEvidenceItem(BaseModel):
    label: str = Field(max_length=200)
    value: str = Field(max_length=_MAX_LIST_ITEM_LEN)


class AIAnalysisResult(BaseModel):
    """The ONLY shape an AI provider response is allowed to take. Required
    structured output containing summary, likely causes, confidence, evidence,
    severity, and recommendations, per section 9."""

    summary: str = Field(max_length=_MAX_SUMMARY_LEN)
    likely_causes: list[str] = Field(max_length=_MAX_LIST_ITEMS)
    confidence_level: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    evidence: list[AIEvidenceItem] = Field(max_length=_MAX_LIST_ITEMS)
    severity: str
    recommendations: list[str] = Field(max_length=_MAX_LIST_ITEMS)

    @field_validator("confidence_level")
    @classmethod
    def _validate_confidence_level(cls, v: str) -> str:
        if v not in _VALID_CONFIDENCE_LEVELS:
            raise ValueError(f"confidence_level must be one of {sorted(_VALID_CONFIDENCE_LEVELS)}, got {v!r}")
        return v

    @field_validator("severity")
    @classmethod
    def _validate_severity(cls, v: str) -> str:
        if v not in _VALID_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(_VALID_SEVERITIES)}, got {v!r}")
        return v

    @field_validator("likely_causes", "recommendations")
    @classmethod
    def _validate_list_item_lengths(cls, v: list[str]) -> list[str]:
        for item in v:
            if len(item) > _MAX_LIST_ITEM_LEN:
                raise ValueError(f"list item exceeds max length {_MAX_LIST_ITEM_LEN}")
        return v


class AIAnalysisValidationError(Exception):
    """Raised when a provider's raw response fails to parse as JSON or fails
    AIAnalysisResult validation. Always caught by service.py -- never propagates
    to break the deterministic RCA that already exists for the incident."""


def parse_and_validate(raw_text: str) -> AIAnalysisResult:
    import json

    try:
        payload = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AIAnalysisValidationError(f"AI response was not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise AIAnalysisValidationError("AI response JSON must be an object")

    try:
        return AIAnalysisResult.model_validate(payload)
    except Exception as exc:  # pydantic.ValidationError, kept broad deliberately -- any failure here means "don't trust it"
        raise AIAnalysisValidationError(f"AI response failed schema validation: {exc}") from exc
