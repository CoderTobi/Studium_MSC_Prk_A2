"""Per-user rate limiting, kept in the backend's memory.

There is exactly one backend instance, so memory is enough (see ``database.md`` §6).
The counters reset when the backend restarts.

Each bucket is a fixed window of 60 seconds per ``uid``. A request may count against
several buckets (``POST /recommendations`` counts against ``ai`` and ``general``); it
is only accepted if *all* of them have capacity left, and only then is it counted.
"""

import math
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from fastapi import Depends, Request

from shopping_list.auth import get_current_uid
from shopping_list.errors import ApiError, ErrorCode

WINDOW_SECONDS = 60

# Key under which the decision is stored in the request state. RequestContextMiddleware
# reads it to add the RateLimit-* headers to the response.
STATE_KEY = "rate_limit"


class Bucket(StrEnum):
    GENERAL = "general"
    AI = "ai"


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_seconds: int


@dataclass(slots=True)
class _Window:
    started_at: float
    count: int


class RateLimiter:
    def __init__(
        self,
        limits: Mapping[Bucket, int],
        window_seconds: float = WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limits = dict(limits)
        self._window = window_seconds
        self._clock = clock
        self._windows: dict[tuple[Bucket, str], _Window] = {}
        self._lock = threading.Lock()
        self._last_cleanup = clock()

    def hit(self, uid: str, buckets: Iterable[Bucket]) -> RateLimitDecision:
        """Count one request of ``uid`` against ``buckets``, if all have capacity.

        Returns the state of the most restrictive bucket (fewest remaining requests).
        """
        with self._lock:
            now = self._clock()
            self._cleanup(now)
            windows = [(bucket, self._current_window(bucket, uid, now)) for bucket in buckets]
            exhausted = [(b, w) for b, w in windows if w.count >= self._limits[b]]

            if exhausted:
                # Report the bucket that stays blocked the longest.
                bucket, window = max(exhausted, key=lambda bw: bw[1].started_at)
                return RateLimitDecision(
                    allowed=False,
                    limit=self._limits[bucket],
                    remaining=0,
                    reset_seconds=self._reset_seconds(window, now),
                )

            for _, window in windows:
                window.count += 1
            bucket, window = min(windows, key=lambda bw: self._limits[bw[0]] - bw[1].count)
            return RateLimitDecision(
                allowed=True,
                limit=self._limits[bucket],
                remaining=self._limits[bucket] - window.count,
                reset_seconds=self._reset_seconds(window, now),
            )

    def _current_window(self, bucket: Bucket, uid: str, now: float) -> _Window:
        key = (bucket, uid)
        window = self._windows.get(key)
        if window is None or now - window.started_at >= self._window:
            window = _Window(started_at=now, count=0)
            self._windows[key] = window
        return window

    def _reset_seconds(self, window: _Window, now: float) -> int:
        return max(1, math.ceil(window.started_at + self._window - now))

    def _cleanup(self, now: float) -> None:
        """Drop expired windows once per window length, so memory doesn't grow forever."""
        if now - self._last_cleanup < self._window:
            return
        self._last_cleanup = now
        expired = [k for k, w in self._windows.items() if now - w.started_at >= self._window]
        for key in expired:
            del self._windows[key]


def rate_limited(*buckets: Bucket) -> Callable[..., None]:
    """Create a dependency that counts the request against ``buckets`` for the current user."""

    def dependency(request: Request, uid: str = Depends(get_current_uid)) -> None:
        limiter: RateLimiter = request.app.state.rate_limiter
        decision = limiter.hit(uid, buckets)
        setattr(request.state, STATE_KEY, decision)
        if not decision.allowed:
            raise ApiError(
                ErrorCode.RATE_LIMIT_EXCEEDED, retry_after_seconds=decision.reset_seconds
            )

    return dependency
