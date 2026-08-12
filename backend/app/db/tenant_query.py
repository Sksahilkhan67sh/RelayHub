"""
Structural tenant isolation helper.

Rather than trusting every developer to remember `.where(Model.organization_id == org_id)`
on every query, all module repositories go through this helper. It is intentionally the
*only* sanctioned way to build a SELECT on a tenant-scoped model in this codebase
(enforced via code review + the `no-raw-select` lint note in CONTRIBUTING.md).
"""

from __future__ import annotations

import uuid
from typing import TypeVar

from sqlalchemy import Select, select

ModelT = TypeVar("ModelT")


def tenant_select(model: type[ModelT], organization_id: uuid.UUID) -> Select:
    if not hasattr(model, "organization_id"):
        raise TypeError(f"{model.__name__} is not tenant-scoped (missing organization_id column)")
    return select(model).where(
        model.organization_id == organization_id,  # type: ignore[attr-defined]
        getattr(model, "deleted_at", None).is_(None) if hasattr(model, "deleted_at") else True,
    )
