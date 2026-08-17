"""限流与 JWT 默认有效期契约。"""

from app.core.config import settings
from app.core.rate_limit import _MemoryFixedWindow, check_rate_limit


def test_access_token_default_is_twelve_hours():
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60 * 12


def test_memory_fixed_window_blocks_over_limit():
    store = _MemoryFixedWindow()
    key = "test:unit:auth"
    for _ in range(3):
        ok, remaining, _ = store.hit(key, limit=3, window_seconds=60)
        assert ok is True
    ok, remaining, retry = store.hit(key, limit=3, window_seconds=60)
    assert ok is False
    assert remaining == 0
    assert retry >= 1


def test_check_rate_limit_uses_memory_without_redis():
    # 强制走内存：不传 redis_url
    key = "test:unit:api:unique"
    ok, rem, _ = check_rate_limit(key, limit=2, window_seconds=60, redis_url=None)
    assert ok and rem == 1
    ok, rem, _ = check_rate_limit(key, limit=2, window_seconds=60, redis_url=None)
    assert ok and rem == 0
    ok, rem, _ = check_rate_limit(key, limit=2, window_seconds=60, redis_url=None)
    assert not ok


def test_rate_limit_middleware_bucket_resolution():
    from app.core.rate_limit_middleware import RateLimitMiddleware

    mw = RateLimitMiddleware(app=None)  # type: ignore[arg-type]
    assert mw._resolve_bucket("POST", "/api/v1/auth/login")[1] == "auth"
    assert mw._resolve_bucket("POST", "/api/v1/auth/register")[1] == "auth"
    assert mw._resolve_bucket("POST", "/api/v1/tasks/1/claim")[1] == "claim"
    assert mw._resolve_bucket("POST", "/api/v1/projects/1/import/zip")[1] == "import"
    assert mw._resolve_bucket("GET", "/api/v1/projects")[1] == "api"
