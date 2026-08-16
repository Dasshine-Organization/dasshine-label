"""具身 P3：RLDS-lite、远端视频下载、策略 HTTP、格式注册。"""

from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.embodied_episodes import normalize_episode
from app.services.embodied_service import (
    _download_remote_video,
    apply_policy_prelabel,
    build_lerobot_dataset_zip,
    build_rlds_dataset_zip,
    set_vla_meta,
)
from app.services.exporters import list_formats


def test_embodied_primary_formats_p3():
    ids = [f.id for f in list_formats("embodied", include_raw=False)]
    assert ids == ["json", "lerobot_dataset", "tfrecord"]


def test_rlds_zip_layout():
    doc = {
        "schema": "dasshine.embodied_sequence.v6",
        "task_db_id": 5,
        "instruction": "pick cup",
        "success": "success",
        "fps": 10,
        "segments": [],
        "grasps": [],
        "trajectory": [],
        "preferences": [],
        "streams": [{"id": "cam", "src": "http://x/a.mp4"}],
        "frames": [
            {
                "index": 0,
                "timestamp_ms": 0,
                "action": {"id": "reach", "label": "伸手"},
                "joints": [{"name": "j0", "position_rad": 0.1, "torque_nm": 0.2}],
                "force": {"fx": 0, "fy": 0, "fz": -1, "tx": 0, "ty": 0, "tz": 0},
                "tactile": {"pads": [{"name": "p", "pressure": 0.4}]},
            },
            {
                "index": 1,
                "timestamp_ms": 100,
                "action": {"id": "grasp", "label": "抓"},
                "joints": [{"name": "j0", "position_rad": 0.2, "torque_nm": 0.1}],
                "force": {"fx": 0, "fy": 0, "fz": -2, "tx": 0, "ty": 0, "tz": 0},
                "tactile": {"pads": [{"name": "p", "pressure": 0.8}]},
            },
        ],
    }
    raw = build_rlds_dataset_zip([doc], "demo")
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "dataset_info.json" in names
        assert "episodes/episode_000005/steps.jsonl" in names
        assert "episodes/episode_000005/meta.json" in names
        info = json.loads(zf.read("dataset_info.json"))
        assert info["schema"] == "dasshine.rlds_lite.v1"
        assert info["total_steps"] == 2
        lines = zf.read("episodes/episode_000005/steps.jsonl").decode("utf-8").strip().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        last = json.loads(lines[1])
        assert first["is_first"] is True
        assert last["is_last"] is True
        assert last["reward"] == 1.0
        assert first["language_instruction"] == "pick cup"


def test_download_remote_video_respects_disable():
    with patch("app.core.config.settings") as settings:
        settings.EMBODIED_VIDEO_DOWNLOAD = False
        assert _download_remote_video("https://example.com/a.mp4") is None


def test_download_remote_video_success():
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.headers = {"content-type": "video/mp4"}
    fake_resp.iter_bytes = lambda n=65536: [b"abc", b"def"]

    class _StreamCM:
        def __enter__(self):
            return fake_resp

        def __exit__(self, *a):
            return False

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, *a, **k):
            return _StreamCM()

    with patch("app.core.config.settings") as settings:
        settings.EMBODIED_VIDEO_DOWNLOAD = True
        settings.EMBODIED_VIDEO_DOWNLOAD_MAX_MB = 1
        settings.EMBODIED_VIDEO_DOWNLOAD_TIMEOUT = 5
        with patch("httpx.Client", return_value=_Client()):
            out = _download_remote_video("https://example.com/clip.mp4")
    assert out is not None
    data, ext = out
    assert data == b"abcdef"
    assert ext == ".mp4"


def test_lerobot_zip_schema_v3():
    doc = {
        "task_db_id": 1,
        "instruction": "x",
        "success": "unknown",
        "fps": 12,
        "frames": [
            {
                "index": 0,
                "timestamp_ms": 0,
                "action": {"id": "idle"},
                "joints": [],
                "force": {},
                "tactile": {"pads": []},
            }
        ],
        "streams": [],
        "grasps": [],
        "trajectory": [],
        "segments": [],
        "preferences": [],
    }
    raw = build_lerobot_dataset_zip([doc], "p")
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        info = json.loads(zf.read("meta/info.json"))
        assert info["dasshine"]["schema"] == "dasshine.lerobot_dataset.v3"


def test_policy_http_then_fallback_demo():
    ep = normalize_episode(
        {
            "case_id": "p",
            "project_name": "Proj",
            "fps": 10,
            "total_frames": 6,
            "clip_duration_sec": 0.6,
            "streams": [{"id": "c", "label": "c", "src": "http://x"}],
        }
    )
    task = SimpleNamespace(id=99, data={"embodied_episode": ep, "embodied_vla": {}}, data_url=None, task_metadata={})
    ws = SimpleNamespace(
        id=1,
        action_labels=[{"id": "idle", "label": "待机"}, {"id": "reach", "label": "伸手"}],
        committed_frames=[],
        updated_at=None,
        user_id=1,
    )

    class _DB:
        def query(self, *a, **k):
            class _Q:
                def filter(self, *a, **k):
                    return self

                def order_by(self, *a, **k):
                    return self

                def all(self):
                    return []

            return _Q()

        def commit(self):
            return None

        def refresh(self, *a, **k):
            return None

    from app.services import embodied_service as svc

    orig_ep = svc.get_episode_dict
    orig_ws = svc.workspace_to_state
    svc.get_episode_dict = lambda t: ep  # noqa: ARG005
    svc.workspace_to_state = lambda db, t, w: {  # noqa: ARG005
        "task_id": 99,
        "task_ref": "99",
        "user_id": 1,
        "action_labels": ws.action_labels,
        "frame_actions": {i: {"action_id": "idle", "note": ""} for i in range(6)},
        "committed_frames": [],
        "instruction": "",
        "success": "unknown",
        "segments": [],
        "grasps": [],
        "trajectory": [],
        "preferences": [],
        "updated_at": None,
    }
    try:
        with patch.object(svc, "_try_policy_http", return_value=None):
            result = apply_policy_prelabel(_DB(), task, ws, model="embodied_policy_http")
        assert result["model"] == "embodied_policy_demo"
        assert result.get("http_fallback") is True
        assert result["instruction"]

        with patch.object(
            svc,
            "_try_policy_http",
            return_value={
                "instruction": "from-http",
                "success": "success",
                "segments": [{"id": "s", "start_frame": 0, "end_frame": 1, "action_id": "reach"}],
                "grasps": [],
                "trajectory": [],
                "preferences": [],
            },
        ):
            result2 = apply_policy_prelabel(_DB(), task, ws, model="auto")
        assert result2["model"] == "embodied_policy_http"
        assert result2["instruction"] == "from-http"
    finally:
        svc.get_episode_dict = orig_ep
        svc.workspace_to_state = orig_ws


def test_set_vla_meta_still_works():
    task = SimpleNamespace(data={})
    set_vla_meta(task, instruction="hi", preferences=[])
    assert task.data["embodied_vla"]["instruction"] == "hi"
