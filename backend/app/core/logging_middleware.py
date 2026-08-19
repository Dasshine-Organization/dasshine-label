"""
请求观测：结构化访问日志 + 耗时。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("dasshine.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """为每个请求打一条 JSON 访问日志（含 duration_ms、status、path）。"""

    SKIP_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/uploads", "/metrics", "/api/v1/media/")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return await call_next(request)

        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            logger.exception(
                json.dumps(
                    {
                        "event": "request_error",
                        "request_id": request_id,
                        "method": request.method,
                        "path": path,
                        "query": str(request.url.query or ""),
                    },
                    ensure_ascii=False,
                )
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            payload = {
                "event": "http_access",
                "request_id": request_id,
                "method": request.method,
                "path": path,
                "status": status_code,
                "duration_ms": duration_ms,
                "client": request.client.host if request.client else None,
            }
            # 慢请求 / 失败更显眼
            if status_code >= 500 or duration_ms >= 2000:
                logger.warning(json.dumps(payload, ensure_ascii=False))
            else:
                logger.info(json.dumps(payload, ensure_ascii=False))
