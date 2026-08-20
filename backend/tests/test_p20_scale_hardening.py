"""P20 契约：Range、点云采样、Prometheus 路径、全模态默认导出非空。"""

from __future__ import annotations

import struct
from pathlib import Path

from app.core.metrics import COLLAB_WS_CONNECTIONS, observe_claim, render_metrics
from app.core.metrics_middleware import _claim_kind, _export_kind
from app.core.rate_limit_middleware import RateLimitMiddleware
from app.services.media_range import parse_range, pointcloud_chunk, sample_kitti_bin, sample_pcd_ascii
from tests.helpers_modality_smoke import CATEGORIES, all_category_export_smokes, export_smoke


def test_parse_range_suffix_and_open_end():
    assert parse_range("bytes=0-3", 10) == (0, 3)
    assert parse_range("bytes=8-", 10) == (8, 9)
    assert parse_range("bytes=-2", 10) == (8, 9)
    assert parse_range("bytes=99-100", 10) is None
    assert parse_range(None, 10) is None


def test_sample_pcd_ascii(tmp_path: Path):
    pcd = tmp_path / "tiny.pcd"
    pcd.write_text(
        "\n".join(
            [
                "VERSION 0.7",
                "FIELDS x y z",
                "SIZE 4 4 4",
                "TYPE F F F",
                "COUNT 1 1 1",
                "WIDTH 3",
                "HEIGHT 1",
                "POINTS 3",
                "DATA ascii",
                "1 0 0",
                "0 1 0",
                "0 0 1",
                "",
            ]
        ),
        encoding="utf-8",
    )
    pts = sample_pcd_ascii(pcd, max_points=10)
    assert pts.shape == (3, 3)
    chunk = pointcloud_chunk(pcd, chunk=0, points_per_chunk=2)
    assert chunk["total_points"] == 3
    assert chunk["total_chunks"] == 2
    assert chunk["count"] == 2


def test_sample_kitti_bin(tmp_path: Path):
    path = tmp_path / "scan.bin"
    path.write_bytes(struct.pack("<ffff", 1.0, 0.0, 0.0, 1.0) + struct.pack("<ffff", 0.0, 1.0, 0.0, 1.0))
    pts = sample_kitti_bin(path, max_points=10)
    assert pts.shape[0] == 2
    assert abs(pts[0][0] - 1.0) < 1e-5


def test_metrics_render_contains_claim_and_collab():
    observe_claim("claim_next", "ok")
    COLLAB_WS_CONNECTIONS.inc()
    body, ctype = render_metrics()
    text = body.decode("utf-8")
    assert "dasshine_claim_total" in text
    assert "dasshine_export_total" in text
    assert "dasshine_collab_ws_connections" in text
    assert "text/plain" in ctype


def test_metrics_middleware_path_match():
    assert _claim_kind("/api/v1/tasks/claim-next") == "claim_next"
    assert _claim_kind("/api/v1/tasks/42/claim") == "claim"
    assert _claim_kind("/api/v1/tasks/42") is None
    assert _export_kind("GET", "/api/v1/export/9") == "sync"
    assert _export_kind("POST", "/api/v1/export/9/jobs") == "async"
    assert _export_kind("GET", "/api/v1/export/9/stats") is None


def test_claim_next_uses_claim_rate_bucket():
    mw = RateLimitMiddleware(app=None)  # type: ignore[arg-type]
    assert mw._resolve_bucket("POST", "/api/v1/tasks/claim-next")[1] == "claim"
    assert mw._resolve_bucket("POST", "/api/v1/tasks/1/claim")[1] == "claim"


def test_each_category_default_export_nonempty():
    rows = all_category_export_smokes()
    assert {c for c, _, _ in rows} == set(CATEGORIES)
    for cat, fmt, nbytes in rows:
        assert nbytes > 8, cat
        assert export_smoke(cat, fmt)


def test_demo_flag_is_explicit_setting():
    from app.core.config import settings

    assert hasattr(settings, "DEMO_ENTRIES_ENABLED")
    assert hasattr(settings, "METRICS_ENABLED")
    assert settings.DEMO_ENTRIES_ENABLED is False or settings.DEMO_ENTRIES_ENABLED is True
