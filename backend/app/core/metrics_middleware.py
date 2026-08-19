"""从 HTTP 路径打点 claim / export（不侵入业务函数）。"""

from __future__ import annotations

import re
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.metrics import metrics_enabled, observe_claim, observe_export

_CLAIM_NEXT = re.compile(r"^/api/v1/tasks/claim-next/?$")
_CLAIM_ONE = re.compile(r"^/api/v1/tasks/\d+/claim/?$")
_EXPORT_SYNC = re.compile(r"^/api/v1/export/\d+/?$")
_EXPORT_JOB = re.compile(r"^/api/v1/export/\d+/jobs/?$")


def _claim_kind(path: str) -> str | None:
    if _CLAIM_NEXT.match(path):
        return "claim_next"
    if _CLAIM_ONE.match(path):
        return "claim"
    return None


def _export_kind(method: str, path: str) -> str | None:
    if method == "GET" and _EXPORT_SYNC.match(path):
        return "sync"
    if method == "POST" and _EXPORT_JOB.match(path):
        return "async"
    return None


def _status_bucket(code: int) -> str:
    if 200 <= code < 300:
        return "ok"
    if code in (404, 400):
        return "empty"
    return "error"


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not metrics_enabled():
            return await call_next(request)

        path = request.url.path
        method = request.method.upper()
        claim_kind = _claim_kind(path) if method == "POST" else None
        export_kind = _export_kind(method, path)
        if not claim_kind and not export_kind:
            return await call_next(request)

        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            bucket = _status_bucket(status_code)
            if claim_kind:
                observe_claim(claim_kind, bucket)
            if export_kind:
                observe_export(export_kind, bucket, time.perf_counter() - started)
