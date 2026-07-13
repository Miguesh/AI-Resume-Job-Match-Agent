from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class InMemoryRateLimiter:
    """Single-process safety net; production deployments should also rate-limit at the edge."""

    def __init__(self, requests_per_minute: int) -> None:
        if requests_per_minute <= 0:
            raise ValueError("Rate limit must be positive")
        self._limit = requests_per_minute
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - 60
        async with self._lock:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= self._limit:
                retry_after = max(1, int(60 - (now - timestamps[0])))
                return False, retry_after
            timestamps.append(now)
            if len(self._requests) > 10_000:
                self._remove_empty(cutoff)
            return True, 0

    def _remove_empty(self, cutoff: float) -> None:
        for key in list(self._requests)[:1_000]:
            timestamps = self._requests[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if not timestamps:
                del self._requests[key]
