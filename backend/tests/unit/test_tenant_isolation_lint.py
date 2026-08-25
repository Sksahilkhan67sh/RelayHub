"""
G-3 (Phase 4B): tenant isolation structural hardening.

Two things this file proves:
  1. The real codebase currently has zero unscoped/unexplained raw
     `select(<tenant-scoped model>)` calls (test_no_unscoped_tenant_queries_in_codebase).
  2. The checker actually *works* -- it isn't just a no-op that always passes. We
     prove this by writing a deliberately unsafe file into a temp copy of
     app/modules, running the checker against it, and asserting it's caught
     (test_checker_detects_an_injected_unscoped_query). This is the "regression
     test proving an unsafe tenant query is detected" the remediation brief asked
     for.
"""

from __future__ import annotations

import shutil
import textwrap

from app.db import tenant_isolation_check


def test_no_unscoped_tenant_queries_in_codebase():
    violations = tenant_isolation_check.find_violations()
    assert violations == [], "Unscoped tenant-model queries found:\n" + "\n".join(str(v) for v in violations)


def test_checker_detects_an_injected_unscoped_query(tmp_path, monkeypatch):
    # Copy the real app/modules tree so the checker still sees real models.py
    # files (it needs those to know which model names are tenant-scoped), then
    # inject one deliberately-unsafe file and confirm the checker flags exactly it.
    real_modules_dir = tenant_isolation_check.APP_MODULES_DIR
    fake_modules_dir = tmp_path / "modules"
    shutil.copytree(real_modules_dir, fake_modules_dir)

    unsafe_service = fake_modules_dir / "endpoints" / "unsafe_injected_for_test.py"
    unsafe_service.write_text(
        textwrap.dedent(
            """
            from sqlalchemy import select
            from app.modules.endpoints.models import Endpoint


            async def leaky_get_all_endpoints(db):
                # No organization_id filter anywhere -- this is exactly the bug
                # class G-3 is about: returns every organization's endpoints.
                result = await db.execute(select(Endpoint))
                return result.scalars().all()
            """
        )
    )

    monkeypatch.setattr(tenant_isolation_check, "APP_MODULES_DIR", fake_modules_dir)
    violations = tenant_isolation_check.find_violations()

    matches = [v for v in violations if v.model_name == "Endpoint" and "unsafe_injected_for_test.py" in str(v.path)]
    assert len(matches) == 1, f"expected the injected violation to be caught, got: {violations}"


def test_exemption_marker_on_call_line_is_honored(tmp_path, monkeypatch):
    """A raw select() with an explicit `# tenant-scope: safe - ...` marker on the
    call line itself must NOT be flagged -- this is the escape hatch for
    legitimate cross-tenant queries (admin tooling, internal workers, etc.)."""
    real_modules_dir = tenant_isolation_check.APP_MODULES_DIR
    fake_modules_dir = tmp_path / "modules"
    shutil.copytree(real_modules_dir, fake_modules_dir)

    exempt_service = fake_modules_dir / "endpoints" / "exempt_injected_for_test.py"
    exempt_service.write_text(
        textwrap.dedent(
            """
            from sqlalchemy import select
            from app.modules.endpoints.models import Endpoint


            async def admin_get_all_endpoints(db):
                result = await db.execute(select(Endpoint))  # tenant-scope: safe - platform admin tool, intentionally cross-org
                return result.scalars().all()
            """
        )
    )

    monkeypatch.setattr(tenant_isolation_check, "APP_MODULES_DIR", fake_modules_dir)
    violations = tenant_isolation_check.find_violations()

    matches = [v for v in violations if "exempt_injected_for_test.py" in str(v.path)]
    assert matches == [], f"exempted query should not be flagged, got: {matches}"
