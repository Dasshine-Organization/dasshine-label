"""具身 P2：parquet/HDF5、力觉触觉、偏好对、策略预标注。"""

from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace

import h5py
import pandas as pd

from app.services.embodied_episodes import normalize_episode
from app.services.embodied_service import (
    apply_policy_prelabel,
    build_export_json,
    build_hdf5,
    build_lerobot_dataset_zip,
    resolve_force_tactile_for_frame,
    set_vla_meta,
)
from app.services.exporters import build_export, list_formats


def test_embodied_primary_formats_p2():
    ids = [f.id for f in list_formats("embodied", include_raw=False)]
    assert ids == ["json", "lerobot_dataset", "tfrecord"]


def test_force_tactile_from_episode():
    ep = normalize_episode(
        {
            "case_id": "f",
            "project_name": "p",
            "fps": 10,
            "total_frames": 2,
            "clip_duration_sec": 0.2,
            "streams": [{"id": "c", "label": "c", "src": "http://x"}],
            "proprioception": [
                {
                    "index": 0,
                    "joints": [{"name": "j0", "position_rad": 0.1, "torque_nm": 0.2}],
                    "force": {"fx": 1, "fy": 2, "fz": 3, "tx": 0.1, "ty": 0.2, "tz": 0.3},
                    "tactile": {"pads": [{"name": "pad0", "pressure": 0.9}]},
                }
            ],
        }
    )
    force, fsrc, tactile, tsrc = resolve_force_tactile_for_frame(ep, 0, 2)
    assert fsrc == "episode"
    assert tsrc == "episode"
    assert force["fx"] == 1
    assert tactile["pads"][0]["pressure"] == 0.9
    _, fsrc1, _, tsrc1 = resolve_force_tactile_for_frame(ep, 1, 2)
    assert fsrc1 == "mock"
    assert tsrc1 == "mock"


def test_lerobot_dataset_includes_parquet():
    doc = {
        "schema": "dasshine.embodied_sequence.v7",
        "task_db_id": 9,
        "instruction": "pick",
        "success": "success",
        "fps": 12,
        "preferences": [{"id": "p1", "prompt": "q", "chosen": "a", "rejected": "b", "winner": "a"}],
        "grasps": [],
        "trajectory": [],
        "segments": [],
        "streams": [{"id": "cam_high", "label": "high", "src": "http://x/a.mp4"}],
        "frames": [
            {
                "index": 0,
                "timestamp_ms": 0,
                "action": {"id": "pick", "label": "抓"},
                "joints": [{"name": "j0", "position_rad": 0.1, "torque_nm": 0.2}],
                "joints_source": "episode",
                "force": {"fx": 0, "fy": 0, "fz": -1, "tx": 0, "ty": 0, "tz": 0},
                "force_source": "mock",
                "tactile": {"pads": [{"name": "pad0", "pressure": 0.5}]},
                "tactile_source": "mock",
            }
        ],
    }
    raw = build_lerobot_dataset_zip([doc], "demo")
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "data/chunk-000/episode_000009.parquet" in names
        assert "data/chunk-000/episode_000009.jsonl" in names
        info = json.loads(zf.read("meta/info.json"))
        assert info["dasshine"]["schema"] == "dasshine.lerobot_dataset.v3"
        df = pd.read_parquet(io.BytesIO(zf.read("data/chunk-000/episode_000009.parquet")))
        assert len(df) == 1
        assert "observation.force" in df.columns


def test_export_v6_includes_force_preferences():
    ep = normalize_episode(
        {
            "case_id": "x",
            "project_name": "p",
            "fps": 10,
            "total_frames": 1,
            "clip_duration_sec": 0.1,
            "streams": [{"id": "c", "label": "c", "src": "http://x"}],
            "proprioception": [
                {
                    "index": 0,
                    "joints": [{"name": "j0", "position_rad": 0.2, "torque_nm": 0.1}],
                    "force": {"fx": 9, "fy": 0, "fz": 0, "tx": 0, "ty": 0, "tz": 0},
                    "tactile": [0.1, 0.2],
                }
            ],
        }
    )
    task = SimpleNamespace(id=11, data={"embodied_vla": {}}, data_url=None, task_metadata={})
    set_vla_meta(
        task,
        instruction="lift",
        preferences=[{"id": "p1", "prompt": "better?", "chosen": "smooth", "rejected": "jerky", "winner": "a"}],
    )
    state = {
        "action_labels": [{"id": "idle", "label": "待机"}],
        "frame_actions": {0: {"action_id": "idle", "note": ""}},
        "committed_frames": [],
        "instruction": "lift",
        "success": "unknown",
        "segments": [],
        "grasps": [],
        "trajectory": [],
        "preferences": task.data["embodied_vla"]["preferences"],
    }
    ws = SimpleNamespace(id=1)
    doc = build_export_json(task, ws, state, ep)
    assert doc["schema"] == "dasshine.embodied_sequence.v7"
    assert doc["force_source"] == "episode"
    assert doc["frames"][0]["force"]["fx"] == 9
    assert doc["preferences"][0]["winner"] == "a"


def test_hdf5_export_shape():
    ep = normalize_episode(
        {
            "case_id": "h",
            "project_name": "p",
            "fps": 10,
            "total_frames": 2,
            "clip_duration_sec": 0.2,
            "streams": [{"id": "c", "label": "c", "src": "/tmp/nope.mp4"}],
        }
    )
    task = SimpleNamespace(id=12, data={"embodied_vla": {}}, data_url=None, task_metadata={})
    set_vla_meta(task, instruction="go", success="success")
    state = {
        "action_labels": [{"id": "idle", "label": "待机"}],
        "frame_actions": {
            0: {"action_id": "idle", "note": ""},
            1: {"action_id": "reach", "note": ""},
        },
        "committed_frames": [],
        "instruction": "go",
        "success": "success",
        "segments": [],
        "grasps": [],
        "trajectory": [],
        "preferences": [],
    }
    raw = build_hdf5(task, SimpleNamespace(id=1), state, ep)
    with h5py.File(io.BytesIO(raw), "r") as hf:
        assert hf.attrs["schema"] == "dasshine.embodied_hdf5.v1"
        assert hf["observations/qpos"].shape[0] == 2
        assert hf["observations/force"].shape == (2, 6)
        assert hf.attrs["instruction"] == "go"


def test_policy_prelabel_fills_empty_vla():
    ep = normalize_episode(
        {
            "case_id": "pre",
            "project_name": "Demo project",
            "fps": 10,
            "total_frames": 9,
            "clip_duration_sec": 0.9,
            "streams": [{"id": "c", "label": "c", "src": "http://x"}],
        }
    )
    task = SimpleNamespace(id=13, data={"embodied_episode": ep, "embodied_vla": {}}, data_url=None, task_metadata={})
    ws = SimpleNamespace(
        id=1,
        action_labels=[{"id": "idle", "label": "待机"}, {"id": "reach", "label": "伸手"}, {"id": "grasp", "label": "抓"}],
        committed_frames=[],
        updated_at=None,
        user_id=1,
    )

    class _Q:
        def filter(self, *a, **k):
            return self

        def order_by(self, *a, **k):
            return self

        def all(self):
            return []

    class _DB:
        def query(self, *a, **k):
            return _Q()

        def commit(self):
            return None

        def refresh(self, *a, **k):
            return None

    # patch get_episode_dict / workspace_to_state via monkeypatch style: call set path only
    from app.services import embodied_service as svc

    orig_ep = svc.get_episode_dict
    orig_ws = svc.workspace_to_state
    svc.get_episode_dict = lambda t: ep  # noqa: ARG005
    svc.workspace_to_state = lambda db, t, w: {  # noqa: ARG005
        "task_id": 13,
        "task_ref": "13",
        "user_id": 1,
        "action_labels": ws.action_labels,
        "frame_actions": {i: {"action_id": "idle", "note": ""} for i in range(9)},
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
        result = apply_policy_prelabel(_DB(), task, ws)
    finally:
        svc.get_episode_dict = orig_ep
        svc.workspace_to_state = orig_ws
    assert result["instruction"]
    assert result["segments"]
    assert result["grasps"]
    assert task.data["embodied_vla"]["instruction"]


def test_project_hdf5_exporter_single():
    task = SimpleNamespace(
        id=21,
        annotations=[
            SimpleNamespace(
                is_latest=True,
                data={
                    "schema": "dasshine.embodied_sequence.v7",
                    "task_db_id": 21,
                    "instruction": "x",
                    "success": "unknown",
                    "fps": 10,
                    "frames": [
                        {
                            "index": 0,
                            "action": {"id": "idle"},
                            "joints": [{"name": "j0", "position_rad": 0.1}],
                            "force": {"fx": 0, "fy": 0, "fz": 0, "tx": 0, "ty": 0, "tz": 0},
                            "tactile": {"pads": [{"name": "p", "pressure": 0.1}]},
                        }
                    ],
                    "segments": [],
                    "preferences": [],
                    "grasps": [],
                },
            )
        ],
    )
    art = build_export("embodied", "hdf5", [task], "proj")
    assert art.media_type == "application/x-hdf5"
    with h5py.File(io.BytesIO(art.content), "r") as hf:
        assert hf["observations/qpos"].shape[0] == 1
