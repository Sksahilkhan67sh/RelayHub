"""
G-4 (Phase 4C): newsletter subscribe endpoint. Public, unauthenticated, backed by
its own table (see app/modules/newsletter/models.py for why this isn't a fake ESP
integration).
"""

import pytest
from sqlalchemy import select

from app.modules.newsletter.models import NewsletterSubscriber


@pytest.mark.asyncio
async def test_subscribe_creates_a_real_row(client, db_session):
    resp = await client.post("/v1/newsletter/subscribe", json={"email": "reader@example.com"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "subscribed"

    row = (
        await db_session.execute(select(NewsletterSubscriber).where(NewsletterSubscriber.email == "reader@example.com"))
    ).scalar_one()
    assert row.unsubscribed_at is None


@pytest.mark.asyncio
async def test_subscribe_is_idempotent_not_an_error(client):
    first = await client.post("/v1/newsletter/subscribe", json={"email": "twice@example.com"})
    assert first.status_code == 200
    assert first.json()["status"] == "subscribed"

    second = await client.post("/v1/newsletter/subscribe", json={"email": "twice@example.com"})
    assert second.status_code == 200
    assert second.json()["status"] == "already_subscribed"


@pytest.mark.asyncio
async def test_subscribe_normalizes_email_case_and_whitespace(client, db_session):
    resp = await client.post("/v1/newsletter/subscribe", json={"email": "  Mixed.Case@Example.com  "})
    assert resp.status_code == 200

    row = (
        await db_session.execute(select(NewsletterSubscriber).where(NewsletterSubscriber.email == "mixed.case@example.com"))
    ).scalar_one()
    assert row is not None


@pytest.mark.asyncio
async def test_subscribe_rejects_invalid_email(client):
    resp = await client.post("/v1/newsletter/subscribe", json={"email": "not-an-email"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_resubscribe_after_unsubscribe(db_session):
    from app.modules.newsletter import service

    status1, _ = await service.subscribe(db_session, email="churner@example.com")
    assert status1 == "subscribed"

    unsubscribed = await service.unsubscribe(db_session, email="churner@example.com")
    assert unsubscribed is True

    status2, _ = await service.subscribe(db_session, email="churner@example.com")
    assert status2 == "resubscribed"


@pytest.mark.asyncio
async def test_newsletter_rate_limited_after_many_attempts_from_same_ip(client):
    for i in range(5):
        resp = await client.post("/v1/newsletter/subscribe", json={"email": f"bulk{i}@example.com"})
        assert resp.status_code == 200, f"attempt {i + 1} should succeed, not yet rate limited"

    blocked = await client.post("/v1/newsletter/subscribe", json={"email": "bulk-final@example.com"})
    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers
    assert blocked.json()["error"]["code"] == "rate_limited"
