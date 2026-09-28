"""
Minimal in-memory rate limiter for sensitive endpoints (login/register).
Per-process only: with multiple workers each keeps its own counters, which
still bounds brute-force attempts. Use a Redis-backed limiter to share limits.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, request: Request) -> None:
        forwarded = request.headers.get("x-forwarded-for", "")
        client_ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
        key = f"{request.url.path}:{client_ip}"
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()
        if len(hits) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts. Please wait a minute and try again.",
            )
        hits.append(now)
        if len(self._hits) > 10_000:
            # Drop idle keys so memory stays bounded.
            for k in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window_seconds]:
                del self._hits[k]


auth_rate_limit = RateLimiter(max_requests=10, window_seconds=60)
