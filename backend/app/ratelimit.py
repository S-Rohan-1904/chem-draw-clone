"""Per-client token bucket for the expensive endpoints. In-process only,
which is fine for a single instance."""

from __future__ import annotations

import os
import threading
import time

from fastapi import HTTPException, Request, status

RATE = float(os.environ.get("RATE_LIMIT_PER_MIN", "30"))  # sustained requests per minute
BURST = int(os.environ.get("RATE_LIMIT_BURST", "10"))

_lock = threading.Lock()
_buckets: dict[str, tuple[float, float]] = {}  # ip -> (tokens, last_ts)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check(request: Request) -> None:
    """FastAPI dependency: raise 429 when the client's bucket is empty."""
    if RATE <= 0:
        return
    ip = client_ip(request)
    now = time.monotonic()
    with _lock:
        tokens, last = _buckets.get(ip, (float(BURST), now))
        tokens = min(BURST, tokens + (now - last) * RATE / 60.0)
        if tokens < 1.0:
            retry = int((1.0 - tokens) * 60.0 / RATE) + 1
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests, slow down a little.",
                headers={"Retry-After": str(retry)},
            )
        _buckets[ip] = (tokens - 1.0, now)
        if len(_buckets) > 10000:  # crude eviction
            for k in list(_buckets)[:5000]:
                del _buckets[k]
