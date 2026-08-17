"""
简单限流：固定窗口（优先 Redis，回退进程内存）。
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

logger = logging.getLogger("dasshine.ratelimit")


class _MemoryFixedWindow:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: Dict[str, Tuple[int, int]] = {}  # key -> (window_start, count)

    def hit(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int, int]:
        """
        Returns (allowed, remaining, retry_after_seconds).
        """
        now = int(time.time())
        window = now - (now % window_seconds)
        with self._lock:
            # prune occasionally
            if len(self._buckets) > 50_000:
                cutoff = now - window_seconds * 2
                self._buckets = {k: v for k, v in self._buckets.items() if v[0] >= cutoff}
            start, count = self._buckets.get(key, (window, 0))
            if start != window:
                start, count = window, 0
            count += 1
            self._buckets[key] = (start, count)
            if count > limit:
                return False, 0, window_seconds - (now - window)
            return True, max(0, limit - count), 0


class _RedisFixedWindow:
    def __init__(self, redis_url: str) -> None:
        import redis

        self._r = redis.from_url(str(redis_url), decode_responses=True)

    def hit(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int, int]:
        now = int(time.time())
        window = now - (now % window_seconds)
        rk = f"rl:{key}:{window}"
        pipe = self._r.pipeline()
        pipe.incr(rk)
        pipe.expire(rk, window_seconds + 1)
        count, _ = pipe.execute()
        count = int(count)
        if count > limit:
            return False, 0, window_seconds - (now - window)
        return True, max(0, limit - count), 0


_memory = _MemoryFixedWindow()
_redis: Optional[_RedisFixedWindow] = None
_redis_failed = False


def get_limiter(redis_url: Optional[str] = None):
    global _redis, _redis_failed
    if redis_url and not _redis_failed:
        if _redis is None:
            try:
                _redis = _RedisFixedWindow(redis_url)
                # ping
                _redis._r.ping()
                logger.info("rate_limit backend=redis")
            except Exception as e:
                logger.warning("rate_limit redis unavailable, fallback memory: %s", e)
                _redis = None
                _redis_failed = True
        if _redis is not None:
            return _redis
    return _memory


def check_rate_limit(
    key: str,
    *,
    limit: int,
    window_seconds: int = 60,
    redis_url: Optional[str] = None,
) -> Tuple[bool, int, int]:
    return get_limiter(redis_url).hit(key, limit, window_seconds)
