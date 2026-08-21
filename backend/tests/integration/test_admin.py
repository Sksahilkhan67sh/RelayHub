import uuid

import httpx
import pytest

from app.modules.delivery import executor as executor_module
from app.modules.delivery.executor import execute_delivery_job
from tests.conftest import (
    create_api_key,
    create_endpoint,
    make_platform_admin,
    register_and_get_token,
    upgrade_to_pro,
)


@pytest.fixture(autouse=True)
def patch_connect_time_resolution(monkeypatch):
    async def _fake_resolve(url: str) -> str:
        return "93.184.216.34"

    monkeypatch.setattr(executor_module, "resolve_and_validate", _fake_resolve)


@pytest.mark.asyncio
async def test_admin_routes_reject_non_admin(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.get("/v1/admin/organizations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_routes_reject_unauthenticated(client):
    resp = await client.get("/v1/admin/organizations")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_organizations_includes_counts(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    await make_platform_admin(client, db_session, token)

    resp = await client.get("/v1/admin/organizations", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    orgs = resp.json()
    assert len(orgs) >= 1
    mine = next(o for o in orgs if o["endpoint_count"] == 1)
    assert mine["member_count"] == 1
    assert mine["plan_tier"] == "free"


@pytest.mark.asyncio
async def test_suspend_and_unsuspend_organization(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me_resp.json()["organization"]["id"]

    suspend_resp = await client.post(
        f"/v1/admin/organizations/{org_id}/suspend", json={"reason": "suspected abuse"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert suspend_resp.status_code == 200
    assert suspend_resp.json()["is_suspended"] is True
    assert suspend_resp.json()["suspension_reason"] == "suspected abuse"

    unsuspend_resp = await client.post(
        f"/v1/admin/organizations/{org_id}/unsuspend", headers={"Authorization": f"Bearer {token}"}
    )
    assert unsuspend_resp.status_code == 200
    assert unsuspend_resp.json()["status"] == "unsuspended"


@pytest.mark.asyncio
async def test_suspend_nonexistent_org_returns_404(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)

    resp = await client.post(
        f"/v1/admin/organizations/{uuid.uuid4()}/suspend", json={"reason": "x"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_impersonation_issues_short_lived_token_and_audit_logs(client, unique_email, db_session):
    from sqlalchemy import select

    from app.modules.audit.models import AuditLog

    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me_resp.json()["organization"]["id"]
    owner_email = me_resp.json()["user"]["email"]

    resp = await client.post(f"/v1/admin/organizations/{org_id}/impersonate", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["impersonated_user_email"] == owner_email
    assert body["expires_in"] == 300

    whoami = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert whoami.status_code == 200
    assert whoami.json()["user"]["email"] == owner_email

    audit_rows = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "admin.impersonation_started"))
    ).scalars().all()
    assert len(audit_rows) == 1


@pytest.mark.asyncio
async def test_queue_depth_reflects_real_job_states(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    await make_platform_admin(client, db_session, token)

    await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )

    resp = await client.get("/v1/admin/queues", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["queued"] >= 1


@pytest.mark.asyncio
async def test_system_health_reports_db_ok_and_queue_depth(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)

    resp = await client.get("/v1/admin/system-health", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["database_ok"] is True
    assert "queue_depth" in body


@pytest.mark.asyncio
async def test_billing_overview_aggregates_correctly(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    await upgrade_to_pro(client, db_session, token)

    resp = await client.get("/v1/admin/billing-overview", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_organizations"] >= 1
    assert body["organizations_by_tier"].get("pro", 0) >= 1
    assert body["mrr_cents"] >= 9900


@pytest.mark.asyncio
async def test_force_retry_delivery_job_works_on_any_status(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    await make_platform_admin(client, db_session, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = resp.json()["delivery_jobs"][0]["id"]

    retry_resp = await client.post(f"/v1/admin/delivery-jobs/{job_id}/force-retry", headers={"Authorization": f"Bearer {token}"})
    assert retry_resp.status_code == 200
    assert retry_resp.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_force_retry_survives_queue_dispatch_failure(client, unique_email, db_session):
    """
    Regression test: a broker outage during the admin force-retry's enqueue() call
    must not fail the request -- the job's status is already durably reset to
    `queued` in the same transaction, and reconciliation is the backstop for the
    dispatch itself.
    """
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    await make_platform_admin(client, db_session, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = resp.json()["delivery_jobs"][0]["id"]

    async def _broken_enqueue(job_id):
        raise ConnectionError("simulated broker outage")

    client.fake_queue.enqueue = _broken_enqueue  # type: ignore[method-assign]

    retry_resp = await client.post(f"/v1/admin/delivery-jobs/{job_id}/force-retry", headers={"Authorization": f"Bearer {token}"})
    assert retry_resp.status_code == 200, retry_resp.text
    assert retry_resp.json()["status"] == "queued"


@pytest.mark.asyncio
async def test_force_cancel_delivery_job(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await create_endpoint(client, token)
    api_key = await create_api_key(client, token)
    await make_platform_admin(client, db_session, token)

    resp = await client.post(
        "/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": api_key}
    )
    job_id = resp.json()["delivery_jobs"][0]["id"]

    cancel_resp = await client.post(f"/v1/admin/delivery-jobs/{job_id}/force-cancel", headers={"Authorization": f"Bearer {token}"})
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_admin_global_logs_spans_organizations(client, unique_email, db_session):
    token_a = await register_and_get_token(client, f"a-{uuid.uuid4().hex[:8]}@example.com")
    await create_endpoint(client, token_a)
    key_a = await create_api_key(client, token_a)
    await client.post("/v1/events", json={"event": "payment.success", "payload": {}}, headers={"X-RelayHub-Api-Key": key_a})

    token_b = await register_and_get_token(client, f"b-{uuid.uuid4().hex[:8]}@example.com")
    await create_endpoint(client, token_b)
    key_b = await create_api_key(client, token_b)
    await client.post("/v1/events", json={"event": "order.created", "payload": {}}, headers={"X-RelayHub-Api-Key": key_b})

    await make_platform_admin(client, db_session, token_a)

    resp = await client.get("/v1/admin/logs", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    org_ids_seen = {row["organization_id"] for row in resp.json()}
    assert len(org_ids_seen) == 2


@pytest.mark.asyncio
async def test_feature_flag_crud_and_evaluation(client, unique_email, db_session):
    from app.modules.admin import service as admin_service

    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)

    create_resp = await client.post(
        "/v1/admin/feature-flags",
        json={"key": "new-analytics-ui", "description": "rollout", "is_enabled_globally": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 200
    assert create_resp.json()["is_enabled_globally"] is False

    duplicate_resp = await client.post(
        "/v1/admin/feature-flags",
        json={"key": "new-analytics-ui", "is_enabled_globally": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert duplicate_resp.status_code == 409

    update_resp = await client.patch(
        "/v1/admin/feature-flags/new-analytics-ui", json={"is_enabled_globally": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["is_enabled_globally"] is True

    enabled = await admin_service.is_feature_enabled(db_session, key="new-analytics-ui")
    assert enabled is True


@pytest.mark.asyncio
async def test_feature_flag_per_org_override_takes_precedence(client, unique_email, db_session):
    from app.modules.admin import service as admin_service

    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me_resp.json()["organization"]["id"]

    await client.post(
        "/v1/admin/feature-flags",
        json={"key": "beta-feature", "is_enabled_globally": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    override_resp = await client.post(
        "/v1/admin/feature-flags/beta-feature/override",
        json={"organization_id": org_id, "is_enabled": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert override_resp.status_code == 200

    enabled_for_org = await admin_service.is_feature_enabled(db_session, key="beta-feature", organization_id=uuid.UUID(org_id))
    assert enabled_for_org is False

    enabled_globally_elsewhere = await admin_service.is_feature_enabled(db_session, key="beta-feature", organization_id=uuid.uuid4())
    assert enabled_globally_elsewhere is True


@pytest.mark.asyncio
async def test_list_feature_flag_overrides(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me_resp.json()["organization"]["id"]
    org_name = me_resp.json()["organization"]["name"]

    await client.post(
        "/v1/admin/feature-flags", json={"key": "overrides-listing", "is_enabled_globally": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    empty_resp = await client.get("/v1/admin/feature-flags/overrides-listing/overrides", headers={"Authorization": f"Bearer {token}"})
    assert empty_resp.status_code == 200
    assert empty_resp.json() == []

    await client.post(
        "/v1/admin/feature-flags/overrides-listing/override",
        json={"organization_id": org_id, "is_enabled": False},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.get("/v1/admin/feature-flags/overrides-listing/overrides", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    overrides = resp.json()
    assert len(overrides) == 1
    assert overrides[0]["organization_id"] == org_id
    assert overrides[0]["organization_name"] == org_name
    assert overrides[0]["is_enabled"] is False


@pytest.mark.asyncio
async def test_feature_flag_overrides_require_platform_admin(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.get("/v1/admin/feature-flags/anything/overrides", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_abuse_report_lifecycle(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    me_resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    org_id = me_resp.json()["organization"]["id"]

    create_resp = await client.post(
        "/v1/admin/abuse-reports", json={"organization_id": org_id, "reason": "excessive rate limit violations"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == 200
    assert create_resp.json()["status"] == "open"
    report_id = create_resp.json()["id"]

    list_resp = await client.get("/v1/admin/abuse-reports?status=open", headers={"Authorization": f"Bearer {token}"})
    assert len(list_resp.json()) == 1

    resolve_resp = await client.patch(
        f"/v1/admin/abuse-reports/{report_id}",
        json={"status": "resolved", "resolution_notes": "false positive, customer contacted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["status"] == "resolved"
    assert resolve_resp.json()["resolved_at"] is not None

    open_list_resp = await client.get("/v1/admin/abuse-reports?status=open", headers={"Authorization": f"Bearer {token}"})
    assert open_list_resp.json() == []
