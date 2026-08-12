import pytest

from app.common.rate_limiter import InMemoryRateLimiter


@pytest.mark.asyncio
async def test_allows_requests_up_to_limit():
    limiter = InMemoryRateLimiter()
    for i in range(5):
        result = await limiter.check("k1", limit=5, window_seconds=60)
        assert result.allowed is True, f"request {i+1} of 5 should be allowed"


@pytest.mark.asyncio
async def test_blocks_request_exceeding_limit():
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        await limiter.check("k1", limit=5, window_seconds=60)
    sixth = await limiter.check("k1", limit=5, window_seconds=60)
    assert sixth.allowed is False
    assert sixth.remaining == 0


@pytest.mark.asyncio
async def test_different_keys_are_independent():
    limiter = InMemoryRateLimiter()
    for _ in range(5):
        await limiter.check("key-a", limit=5, window_seconds=60)
    result = await limiter.check("key-b", limit=5, window_seconds=60)
    assert result.allowed is True


@pytest.mark.asyncio
async def test_old_entries_fall_out_of_the_window(monkeypatch):
    import app.common.rate_limiter as rl_module

    fake_now = [1000.0]
    monkeypatch.setattr(rl_module.time, "time", lambda: fake_now[0])

    limiter = InMemoryRateLimiter()
    for _ in range(5):
        await limiter.check("k1", limit=5, window_seconds=10)

    blocked = await limiter.check("k1", limit=5, window_seconds=10)
    assert blocked.allowed is False

    fake_now[0] += 11
    result = await limiter.check("k1", limit=5, window_seconds=10)
    assert result.allowed is True, "requests should be allowed again once old entries age out of the window"


@pytest.mark.asyncio
async def test_remaining_decreases_correctly():
    limiter = InMemoryRateLimiter()
    r1 = await limiter.check("k1", limit=3, window_seconds=60)
    assert r1.remaining == 2
    r2 = await limiter.check("k1", limit=3, window_seconds=60)
    assert r2.remaining == 1
    r3 = await limiter.check("k1", limit=3, window_seconds=60)
    assert r3.remaining == 0
