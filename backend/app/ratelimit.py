"""Per-client token buckets. In-process only, which is fine for a single
instance.

Three buckets with separate budgets:
  check   expensive work: building a new molecule, conformers, spectra, lookups
  typing  calls the name box makes while the user types
  auth    login and register (each attempt hashes a password)
"""

from __future__ import annotations

import os
import threading
import time

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

# How many reverse proxies sit in front of the app and append to
# X-Forwarded-For. 0 (the default) ignores the header, since a client can put
# anything in it. Behind one proxy (Render) set 1: the client's address is then
# the last entry, the one the proxy added.
TRUSTED_PROXY_HOPS = int(os.environ.get("TRUSTED_PROXY_HOPS", "0"))


def client_ip(request: Request) -> str:
    if TRUSTED_PROXY_HOPS > 0:
        hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
        if len(hops) >= TRUSTED_PROXY_HOPS:
            return hops[-TRUSTED_PROXY_HOPS]
    return request.client.host if request.client else "unknown"


class Limiter:
    """Token bucket per client IP. Use the instance as a FastAPI dependency,
    or call take() inside a handler to charge only when work is actually done."""

    def __init__(self, per_min: float, burst: int):
        self.per_min = per_min
        self.burst = burst
        self._lock = threading.Lock()
        self._buckets: dict[str, tuple[float, float]] = {}  # ip -> (tokens, last_ts)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def take(self, request: Request) -> None:
        """Raise 429 when the client's bucket is empty."""
        if self.per_min <= 0:
            return
        ip = client_ip(request)
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(ip, (float(self.burst), now))
            tokens = min(self.burst, tokens + (now - last) * self.per_min / 60.0)
            if tokens < 1.0:
                retry = int((1.0 - tokens) * 60.0 / self.per_min) + 1
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "Too many requests, slow down a little.",
                    headers={"Retry-After": str(retry)},
                )
            self._buckets[ip] = (tokens - 1.0, now)
            if len(self._buckets) > 10000:  # crude eviction
                for k in list(self._buckets)[:5000]:
                    del self._buckets[k]

    def __call__(self, request: Request) -> None:
        self.take(request)


def _env(name: str, default: str) -> float:
    return float(os.environ.get(name, default))


check = Limiter(_env("RATE_LIMIT_PER_MIN", "30"), int(_env("RATE_LIMIT_BURST", "10")))
typing = Limiter(_env("TYPING_RATE_LIMIT_PER_MIN", "120"), int(_env("TYPING_RATE_LIMIT_BURST", "30")))
auth = Limiter(_env("AUTH_RATE_LIMIT_PER_MIN", "10"), int(_env("AUTH_RATE_LIMIT_BURST", "5")))


def charge_unbuilt(request: Request, db: Session, smiles: str) -> None:
    """Charge the expensive bucket only if this molecule is not cached yet.
    The analysis cards all refetch the built molecule, and those hits are cheap."""
    from . import cache

    if not cache.is_built(db, smiles):
        check.take(request)
