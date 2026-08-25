"""
Structural tenant isolation helper.

Rather than trusting every developer to remember `.where(Model.organization_id == org_id)`
on every query, all module repositories go through this helper. It is intentionally the
*only* sanctioned way to build a SELECT on a tenant-scoped model in this codebase.

G-3 (Phase 4B): this used to be enforced by convention/code-review alone. It is now
also enforced automatically -- app/db/tenant_isolation_check.py statically scans every
module for a raw `select(<tenant-scoped model>)` with no organization_id filter and no
explicit `# tenant-scope: safe - <reason>` exemption, and
tests/unit/test_tenant_isolation_lint.py fails the suite (and therefore CI) if one is
ever introduced. See that module's docstring for exactly what it does and doesn't catch.
"""

from __future__ import annotations

import uuid
from typing import TypeVar

from sqlalchemy import Select, select

ModelT = TypeVar("ModelT")


def tenant_select(model: type[ModelT], organization_id: uuid.UUID) -> Select:
    if not hasattr(model, "organization_id"):
        raise TypeError(f"{model.__name__} is not tenant-scoped (missing organization_id column)")
    conditions = [model.organization_id == organization_id]  # type: ignore[attr-defined]
    deleted_at = getattr(model, "deleted_at", None)
    if deleted_at is not None:
        conditions.append(deleted_at.is_(None))
    return select(model).where(*conditions)
