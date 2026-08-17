"""
HTTP 限流中间件：登录 / 领取 / 通用 API 分层配额。
"""

from __future__ import annotations

import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.core.rate_limit import check_rate_limit

logger = logging.getLogger("dasshine.ratelimit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    SKIP_PREFIXES = (
        "/health",
        "/ready",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/uploads",
        "/api/v1/billing/stripe/webhook",
    )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return await call_next(request)

        # 仅限制 API
        if not path.startswith("/api/"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        limit, bucket = self._resolve_bucket(request.method, path)
        key = f"{bucket}:{client}"
        allowed, remaining, retry_after = check_rate_limit(
            key,
            limit=limit,
            window_seconds=60,
            redis_url=str(settings.REDIS_URL) if settings.REDIS_URL else None,
        )
        if not allowed:
            logger.warning(
                "rate_limited path=%s client=%s bucket=%s limit=%s",
                path,
                client,
                bucket,
                limit,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
                headers={
                    "Retry-After": str(max(1, retry_after)),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    def _resolve_bucket(self, method: str, path: str) -> tuple[int, str]:
        # 认证：更严
        if path.startswith("/api/v1/auth/login") or path.startswith("/api/v1/auth/register"):
            return int(settings.RATE_LIMIT_AUTH_PER_MINUTE), "auth"
        # 领取任务
        if method == "POST" and path.rstrip("/").endswith("/claim"):
            return int(settings.RATE_LIMIT_CLAIM_PER_MINUTE), "claim"
        # 导入（含异步 job）
        if "/import/" in path and method == "POST":
            return int(settings.RATE_LIMIT_IMPORT_PER_MINUTE), "import"
        return int(settings.RATE_LIMIT_API_PER_MINUTE), "api"
