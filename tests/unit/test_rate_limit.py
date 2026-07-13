from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from resume_matcher.infrastructure import rate_limit
from resume_matcher.infrastructure.rate_limit import InMemoryRateLimiter


async def test_rate_limiter_blocks_after_limit_and_returns_retry_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    moments = iter((0.0, 1.0, 10.0))
    monkeypatch.setattr(rate_limit, "time", SimpleNamespace(monotonic=lambda: next(moments)))
    limiter = InMemoryRateLimiter(2)

    assert await limiter.check("client") == (True, 0)
    assert await limiter.check("client") == (True, 0)
    assert await limiter.check("client") == (False, 50)


async def test_rate_limiter_expires_requests_at_exact_window_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    moments = iter((100.0, 160.0))
    monkeypatch.setattr(rate_limit, "time", SimpleNamespace(monotonic=lambda: next(moments)))
    limiter = InMemoryRateLimiter(1)

    assert await limiter.check("client") == (True, 0)
    assert await limiter.check("client") == (True, 0)


async def test_rate_limiter_tracks_clients_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "time", SimpleNamespace(monotonic=lambda: 100.0))
    limiter = InMemoryRateLimiter(1)

    assert await limiter.check("client-a") == (True, 0)
    assert await limiter.check("client-a") == (False, 60)
    assert await limiter.check("client-b") == (True, 0)


async def test_rate_limiter_enforces_limit_atomically_under_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rate_limit, "time", SimpleNamespace(monotonic=lambda: 100.0))
    limiter = InMemoryRateLimiter(7)

    outcomes = await asyncio.gather(*(limiter.check("shared") for _ in range(50)))

    assert sum(allowed for allowed, _ in outcomes) == 7
    assert all(retry == 60 for allowed, retry in outcomes if not allowed)


def test_rate_limiter_rejects_non_positive_limits() -> None:
    with pytest.raises(ValueError, match="positive"):
        InMemoryRateLimiter(0)
