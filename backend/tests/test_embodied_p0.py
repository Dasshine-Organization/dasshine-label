"""具身 P0：真值关节、VLA 字段、episode 导入。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.dataset_service import DatasetImportService
from app.services.embodied_episodes import normalize_episode
from app.services.embodied_service import build_export_json, get_vla_meta, resolve_joints_for_frame, set_vla_meta
from app.services.exporters import build_export


def test_normalize_episode_proprioception():
    ep = normalize_episode(
        {
            "case_id": "robot_a",
            "project_name": "demo",
            "fps": 10,
            "total_frames": 2,
            "clip_duration_sec": 0.2,
            "streams": [{"id": "cam", "label": "main", "src": "http://x/a.mp4"}],
            "instruction": "pick cup",
            "proprioception": [
                {
                    "index": 0,
                    "joints": [{"name": "j0", "position_rad": 1.5, "torque_nm": 0.2}],
                }
            ],
        }
    )
    assert ep["has_proprioception"] is True
    joints, src = resolve_joints_for_frame(ep, 0, 2)
    assert src == "episode"
    assert joints[0]["position_rad"] == 1.5
    joints2, src2 = resolve_joints_for_frame(ep, 1, 2)
    assert src2 == "mock"


def test_build_export_uses_vla_and_true_joints():
    ep = normalize_episode(
        {
            "case_id": "x",
            "project_name": "p",
            "fps": 10,
            "total_frames": 1,
            "clip_duration_sec": 0.1,
            "streams": [{"id": "c", "label": "c", "src": "http://x"}],
            "proprioception": [{"index": 0, "state": [0.1, 0.2, 0.3]}],
        }
    )
    task = SimpleNamespace(id=42, data={"embodied_vla": {}}, data_url=None, task_metadata={})
    set_vla_meta(
        task,
        instruction="place block",
        success="success",
        segments=[{"id": "s1", "start_frame": 0, "end_frame": 0, "action_id": "place"}],
    )
    ws = SimpleNamespace()
    state = {
        "action_labels": [{"id": "idle", "label": "待机"}, {"id": "place", "label": "放置"}],
        "frame_actions": {0: {"action_id": "place", "note": ""}},
        "committed_frames": [0],
        "instruction": "place block",
        "success": "success",
        "segments": [{"id": "s1", "start_frame": 0, "end_frame": 0, "action_id": "place"}],
    }
    doc = build_export_json(task, ws, state, ep)
    assert doc["schema"] == "dasshine.embodied_sequence.v7"
    assert doc["instruction"] == "place block"
    assert doc["success"] == "success"
    assert doc["joints_source"] == "episode"
    assert doc["frames"][0]["joints_source"] == "episode"


def test_import_embodied_episodes(monkeypatch):
    db = MagicMock()
    project = SimpleNamespace(id=1, total_items=0)
    db.query.return_value.filter.return_value.first.return_value = project

    created = []

    class FakeTask:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            created.append(self)

    monkeypatch.setattr("app.services.dataset_service.Task", FakeTask)
    svc = DatasetImportService(db)
    payload = {
        "episodes": [
            {
                "case_id": "e1",
                "fps": 12,
                "total_frames": 3,
                "clip_duration_sec": 0.25,
                "instruction": "open drawer",
                "streams": [{"id": "cam", "label": "cam", "src": "http://v.mp4"}],
            }
        ]
    }
    result = svc.import_embodied_episodes(1, payload, priority=3)
    assert result.errors == [], result.errors
    assert result.success == 1
    assert len(created) == 1
    assert created[0].data["embodied_vla"]["instruction"] == "open drawer"
    assert project.total_items == 1


def test_project_lerobot_export_includes_instruction():
    payload = {
        "schema": "dasshine.embodied_sequence.v4",
        "task_db_id": 9,
        "instruction": "fold towel",
        "success": "fail",
        "segments": [],
        "frames": [
            {
                "index": 0,
                "timestamp_ms": 0,
                "action": {"id": "fold", "label": "折叠"},
                "joints": [{"name": "j1", "position_rad": 0.1, "torque_nm": 1.2}],
                "joints_source": "episode",
                "note": "",
            }
        ],
    }
    task = SimpleNamespace(
        id=9,
        data={},
        data_url=None,
        annotations=[SimpleNamespace(is_latest=True, data=payload, annotator_id=1, version=1, work_time=1)],
        status=SimpleNamespace(value="approved"),
        is_golden=False,
    )
    art = build_export("embodied", "lerobot_jsonl", [task], "proj", [])
    row = json.loads(art.content.decode("utf-8").strip().splitlines()[0])
    assert row["instruction"] == "fold towel"
    assert row["success"] == "fail"
    assert row["joints_source"] == "episode"
