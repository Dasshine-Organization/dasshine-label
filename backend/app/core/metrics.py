"""Prometheus 指标：领取 / 导出 / 共编 WS。"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator, Optional

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from app.core.config import settings

logger = logging.getLogger("dasshine.metrics")

REGISTRY = CollectorRegistry()

CLAIM_TOTAL = Counter(
    "dasshine_claim_total",
    "Task claim attempts",
    ["kind", "status"],
    registry=REGISTRY,
)
EXPORT_TOTAL = Counter(
    "dasshine_export_total",
    "Project export attempts",
    ["kind", "status"],
    registry=REGISTRY,
)
EXPORT_SECONDS = Histogram(
    "dasshine_export_duration_seconds",
    "Export duration",
    ["kind"],
    registry=REGISTRY,
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 15, 30, 60, 120),
)
COLLAB_WS_CONNECTIONS = Gauge(
    "dasshine_collab_ws_connections",
    "Open collab websocket connections",
    registry=REGISTRY,
)
COLLAB_WS_MESSAGES = Counter(
    "dasshine_collab_ws_messages_total",
    "Collab websocket messages",
    ["type"],
    registry=REGISTRY,
)


def metrics_enabled() -> bool:
    return bool(getattr(settings, "METRICS_ENABLED", True))


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def observe_claim(kind: str, status: str) -> None:
    if not metrics_enabled():
        return
    CLAIM_TOTAL.labels(kind=kind, status=status).inc()


def observe_export(kind: str, status: str, seconds: Optional[float] = None) -> None:
    if not metrics_enabled():
        return
    EXPORT_TOTAL.labels(kind=kind, status=status).inc()
    if seconds is not None:
        EXPORT_SECONDS.labels(kind=kind).observe(seconds)


@contextmanager
def export_timer(kind: str) -> Iterator[None]:
    started = time.perf_counter()
    ok = False
    try:
        yield
        ok = True
    finally:
        observe_export(kind, "ok" if ok else "error", time.perf_counter() - started)


def collab_ws_open() -> None:
    if metrics_enabled():
        COLLAB_WS_CONNECTIONS.inc()


def collab_ws_close() -> None:
    if metrics_enabled():
        try:
            COLLAB_WS_CONNECTIONS.dec()
        except Exception:
            logger.debug("collab gauge dec skipped", exc_info=True)


def collab_ws_message(mtype: str) -> None:
    if metrics_enabled():
        COLLAB_WS_MESSAGES.labels(type=mtype or "unknown").inc()
