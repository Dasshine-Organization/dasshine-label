"""具身 P1：LeRobot dataset ZIP、抓取/轨迹、审核预览抽取。"""

from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace

from app.api.v1.quality import _extract_embodied_preview
from app.services.embodied_service import build_export_json, build_lerobot_dataset_zip, set_vla_meta
from app.services.embodied_episodes import normalize_episode
from app.services.exporters import build_export, list_formats


def test_embodied_primary_formats_include_lerobot_dataset():
    ids = [f.id for f in list_formats("embodied", include_raw=False)]
    assert ids == ["json", "lerobot_dataset", "tfrecord"]


def test_lerobot_dataset_zip_layout():
    doc = {
        "schema": "dasshine.embodied_sequence.v5",
        "task_db_id": 3,
        "instruction": "pick",
        "success": "success",
        "fps": 12,
        "grasps": [{"id": "g1", "frame": 0, "position": {"x": 1, "y": 0, "z": 0}, "orientation": {"roll": 0, "pitch": 0, "yaw": 0}, "width": 0.08, "label": "grasp"}],
        "trajectory": [{"frame": 0, "ee": {"x": 0, "y": 0, "z": 0, "roll": 0, "pitch": 0, "yaw": 0}, "gripper": 0}],
        "segments": [],
        "streams": [{"id": "cam_high", "label": "high", "src": "http://x/a.mp4"}],
        "frames": [
            {
                "index": 0,
                "timestamp_ms": 0,
                "action": {"id": "pick", "label": "抓"},
                "joints": [{"name": "j0", "position_rad": 0.1, "torque_nm": 0.2}],
                "joints_source": "episode",
            }
        ],
    }
    raw = build_lerobot_dataset_zip([doc], "demo")
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = set(zf.namelist())
        assert "meta/info.json" in names
        assert "meta/episodes.jsonl" in names
        assert "data/chunk-000/episode_000003.jsonl" in names
        assert "videos_urls/episode_000003/cam_high.txt" in names
        info = json.loads(zf.read("meta/info.json"))
        assert info["total_episodes"] == 1
        assert info["dasshine"]["schema"] == "dasshine.lerobot_dataset.v3"
        assert "data/chunk-000/episode_000003.parquet" in names


def test_export_includes_grasps_trajectory():
    ep = normalize_episode(
        {
            "case_id": "x",
            "project_name": "p",
            "fps": 10,
            "total_frames": 1,
            "clip_duration_sec": 0.1,
            "streams": [{"id": "c", "label": "c", "src": "http://x"}],
        }
    )
    task = SimpleNamespace(id=7, data={"embodied_vla": {}}, data_url=None, task_metadata={})
    set_vla_meta(
        task,
        instruction="grasp bottle",
        success="unknown",
        grasps=[{"id": "g1", "frame": 0, "position": {"x": 0.1, "y": 0.2, "z": 0.3}, "orientation": {"roll": 0, "pitch": 0, "yaw": 1}, "width": 0.05, "label": "grasp"}],
        trajectory=[{"frame": 0, "ee": {"x": 1, "y": 2, "z": 3, "roll": 0, "pitch": 0, "yaw": 0}, "gripper": 0.5}],
    )
    state = {
        "action_labels": [{"id": "idle", "label": "待机"}],
        "frame_actions": {0: {"action_id": "idle", "note": ""}},
        "committed_frames": [],
        "instruction": "grasp bottle",
        "success": "unknown",
        "segments": [],
        "grasps": task.data["embodied_vla"]["grasps"],
        "trajectory": task.data["embodied_vla"]["trajectory"],
    }
    doc = build_export_json(task, SimpleNamespace(), state, ep)
    assert doc["grasps"][0]["position"]["x"] == 0.1
    assert doc["trajectory"][0]["gripper"] == 0.5

    art = build_export(
        "embodied",
        "lerobot_dataset",
        [
            SimpleNamespace(
                id=7,
                data={},
                data_url=None,
                annotations=[SimpleNamespace(is_latest=True, data=doc)],
                status=SimpleNamespace(value="approved"),
                is_golden=False,
            )
        ],
        "proj",
        [],
    )
    assert art.media_type == "application/zip"
    assert art.filename_suffix.endswith(".zip")


def test_embodied_review_preview_extract():
    task = SimpleNamespace(
        id=1,
        data_url=None,
        data={
            "embodied_episode": {
                "streams": [{"id": "cam", "label": "main", "src": "http://v.mp4"}],
                "instruction": "from ep",
            },
            "embodied_vla": {},
        },
    )
    ann = SimpleNamespace(
        data={
            "schema": "dasshine.embodied_sequence.v5",
            "instruction": "do task",
            "success": "fail",
            "segments": [{"start_frame": 0, "end_frame": 2, "action_id": "grasp"}],
            "grasps": [{"id": "g"}],
            "trajectory": [{}, {}],
            "streams": [{"id": "cam", "label": "main", "src": "http://v.mp4"}],
            "joints_source": "episode",
            "frames": [{}, {}, {}],
        }
    )
    preview = _extract_embodied_preview(task, ann)
    assert preview is not None
    assert preview["instruction"] == "do task"
    assert preview["success"] == "fail"
    assert len(preview["streams"]) == 1
    assert preview["trajectory_points"] == 2
