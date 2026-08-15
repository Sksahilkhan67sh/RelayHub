import pytest

from tests.conftest import make_platform_admin, register_and_get_token


@pytest.mark.asyncio
async def test_admin_content_routes_reject_non_admin(client, unique_email):
    token = await register_and_get_token(client, unique_email)
    resp = await client.get("/v1/admin/content/blog-posts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_create_and_list_blog_post(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/v1/admin/content/blog-posts",
        json={
            "slug": "my-first-post",
            "title": "My First Post",
            "excerpt": "An excerpt",
            "category": "Engineering",
            "author_name": "Jane Doe",
            "author_role": "Engineering",
            "read_minutes": 4,
            "body": ["Paragraph one.", "Paragraph two."],
            "status": "draft",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    post = resp.json()
    assert post["slug"] == "my-first-post"
    assert post["status"] == "draft"
    assert post["body"] == ["Paragraph one.", "Paragraph two."]

    resp = await client.get("/v1/admin/content/blog-posts", headers=headers)
    assert resp.status_code == 200
    assert any(p["slug"] == "my-first-post" for p in resp.json())


@pytest.mark.asyncio
async def test_draft_post_hidden_from_public_but_visible_to_admin(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/v1/admin/content/blog-posts",
        json={
            "slug": "draft-post",
            "title": "Draft Post",
            "excerpt": "Not public yet",
            "category": "Engineering",
            "author_name": "Jane Doe",
            "author_role": "Engineering",
            "body": [],
            "status": "draft",
        },
        headers=headers,
    )

    # Public list: draft is invisible
    resp = await client.get("/v1/content/blog-posts")
    assert resp.status_code == 200
    assert not any(p["slug"] == "draft-post" for p in resp.json())

    # Public get-by-slug: 404
    resp = await client.get("/v1/content/blog-posts/draft-post")
    assert resp.status_code == 404

    # Admin list: still visible
    resp = await client.get("/v1/admin/content/blog-posts", headers=headers)
    assert any(p["slug"] == "draft-post" for p in resp.json())


@pytest.mark.asyncio
async def test_publishing_a_post_makes_it_publicly_visible(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/v1/admin/content/blog-posts",
        json={
            "slug": "soon-to-publish",
            "title": "Soon To Publish",
            "excerpt": "excerpt",
            "category": "Engineering",
            "author_name": "Jane Doe",
            "author_role": "Engineering",
            "body": ["Body."],
            "status": "draft",
        },
        headers=headers,
    )
    post_id = resp.json()["id"]

    resp = await client.get("/v1/content/blog-posts/soon-to-publish")
    assert resp.status_code == 404

    resp = await client.patch(
        f"/v1/admin/content/blog-posts/{post_id}", json={"status": "published"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"

    resp = await client.get("/v1/content/blog-posts/soon-to-publish")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Soon To Publish"


@pytest.mark.asyncio
async def test_duplicate_slug_rejected(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "slug": "duplicate-slug",
        "title": "First",
        "excerpt": "excerpt",
        "category": "Engineering",
        "author_name": "Jane Doe",
        "author_role": "Engineering",
        "body": [],
    }
    resp = await client.post("/v1/admin/content/blog-posts", json=payload, headers=headers)
    assert resp.status_code == 201

    resp = await client.post("/v1/admin/content/blog-posts", json={**payload, "title": "Second"}, headers=headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_invalid_slug_format_rejected(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/v1/admin/content/blog-posts",
        json={
            "slug": "Not A Valid Slug!",
            "title": "Title",
            "excerpt": "excerpt",
            "category": "Engineering",
            "author_name": "Jane Doe",
            "author_role": "Engineering",
            "body": [],
        },
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_delete_blog_post_removes_from_both_lists(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/v1/admin/content/blog-posts",
        json={
            "slug": "to-be-deleted",
            "title": "To Be Deleted",
            "excerpt": "excerpt",
            "category": "Engineering",
            "author_name": "Jane Doe",
            "author_role": "Engineering",
            "body": [],
            "status": "published",
        },
        headers=headers,
    )
    post_id = resp.json()["id"]

    resp = await client.delete(f"/v1/admin/content/blog-posts/{post_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get("/v1/content/blog-posts")
    assert not any(p["slug"] == "to-be-deleted" for p in resp.json())

    resp = await client.get("/v1/admin/content/blog-posts", headers=headers)
    assert not any(p["slug"] == "to-be-deleted" for p in resp.json())


@pytest.mark.asyncio
async def test_admin_can_create_update_and_delete_job_posting(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/v1/admin/content/job-postings",
        json={"title": "Backend Engineer", "team": "Engineering", "location": "Remote", "description": "Build things."},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    posting_id = resp.json()["id"]
    assert resp.json()["is_active"] is True

    # Publicly visible while active
    resp = await client.get("/v1/content/job-postings")
    assert any(p["id"] == posting_id for p in resp.json())

    # Deactivate -- disappears from public list, stays in admin list
    resp = await client.patch(f"/v1/admin/content/job-postings/{posting_id}", json={"is_active": False}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    resp = await client.get("/v1/content/job-postings")
    assert not any(p["id"] == posting_id for p in resp.json())

    resp = await client.get("/v1/admin/content/job-postings", headers=headers)
    assert any(p["id"] == posting_id for p in resp.json())

    # Delete -- disappears from admin list too
    resp = await client.delete(f"/v1/admin/content/job-postings/{posting_id}", headers=headers)
    assert resp.status_code == 204

    resp = await client.get("/v1/admin/content/job-postings", headers=headers)
    assert not any(p["id"] == posting_id for p in resp.json())


@pytest.mark.asyncio
async def test_job_postings_public_route_requires_no_auth(client, unique_email, db_session):
    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/v1/admin/content/job-postings",
        json={"title": "Support Engineer", "team": "Support", "location": "Remote (US)"},
        headers=headers,
    )

    resp = await client.get("/v1/content/job-postings")
    assert resp.status_code == 200
    assert any(p["title"] == "Support Engineer" for p in resp.json())


@pytest.mark.asyncio
async def test_updating_nonexistent_blog_post_404s(client, unique_email, db_session):
    import uuid

    token = await register_and_get_token(client, unique_email)
    await make_platform_admin(client, db_session, token)
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.patch(
        f"/v1/admin/content/blog-posts/{uuid.uuid4()}", json={"title": "New Title"}, headers=headers
    )
    assert resp.status_code == 404
