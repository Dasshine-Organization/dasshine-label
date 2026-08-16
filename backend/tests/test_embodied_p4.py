"""具身 P4：TFRecord、内外参、质量摘要、策略权重桩。"""

from __future__ import annotations

import io
import json
import struct
import zipfile
from pathlib import Path

from app.services.embodied_episodes import normalize_episode
from app.services.embodied_policy_weights import (
    activate_policy_weight,
    list_policy_weights,
    save_policy_weight,
)
from app.services.embodied_quality import compute_embodied_quality
from app.services.embodied_service import build_export_json, build_tfrecord_zip
from app.services.exporters import list_formats
from app.services.exporters.tfrecord_lite import (
    crc32c,
    encode_example,
    example_from_step,
    masked_crc32c,
    write_tfrecord_bytes,
)


def test_embodied_primary_formats_p4():
    ids = [f.id for f in list_formats("embodied", include_raw=False)]
    assert ids == ["json", "lerobot_dataset", "tfrecord"]


def test_tfrecord_crc_and_roundtrip_layout(tmp_path, monkeypatch):
    assert crc32c(b"123456789") == 0xE3069283  # known CRC32C vector
    raw = encode_example({"x": {"float_list": [1.0, 2.0]}, "y": {"bytes_list": [b"hi"]}})
    assert isinstance(raw, (bytes, bytearray)) and len(raw) > 0
    blob = write_tfrecord_bytes([raw])
    # length + crc + data + crc
    (length,) = struct.unpack_from("<Q", blob, 0)
    assert length == len(raw)
    assert struct.unpack_from("<I", blob, 8)[0] == masked_crc32c(struct.pack("<Q", length))

    doc = {
        "task_db_id": 3,
        "instruction": "pick",
        "success": "success",
        "frames": [
            {
                "index": 0,
                "timestamp_ms": 0,
                "action": {"id": "reach", "label": "伸手"},
                "joints": [{"name": "j0", "position_rad": 0.1, "torque_nm": 0.2}],
                "force": {"fx": 0, "fy": 0, "fz": -1, "tx": 0, "ty": 0, "tz": 0},
                "tactile": {"pads": [{"name": "p", "pressure": 0.5}]},
            }
        ],
        "streams": [],
        "segments": [],
        "grasps": [],
    }
    z = build_tfrecord_zip([doc], "demo")
    with zipfile.ZipFile(io.BytesIO(z)) as zf:
        names = set(zf.namelist())
        assert "dataset_info.json" in names
        assert "episodes/episode_000003.tfrecord" in names
        info = json.loads(zf.read("dataset_info.json"))
        assert info["schema"] == "dasshine.tfrecord.v1"
        assert len(zf.read("episodes/episode_000003.tfrecord")) > 0


def test_normalize_streams_extrinsics():
    ep = normalize_episode(
        {
            "case_id": "c",
            "project_name": "p",
            "fps": 10,
            "total_frames": 2,
            "clip_duration_sec": 0.2,
            "streams": [
                {
                    "id": "cam",
                    "label": "cam",
                    "src": "http://x/a.mp4",
                    "intrinsics": {"fx": 500, "fy": 500, "cx": 320, "cy": 240, "width": 640, "height": 480},
                    "extrinsics": {
                        "position": {"x": 0.1, "y": 0.2, "z": 0.3},
                        "orientation": {"roll": 0, "pitch": 0, "yaw": 1.57},
                    },
                }
            ],
        }
    )
    s = ep["streams"][0]
    assert s["intrinsics"]["fx"] == 500
    assert s["extrinsics"]["position"]["z"] == 0.3


def test_export_v7_passes_camera_calibration():
    from types import SimpleNamespace

    ep = normalize_episode(
        {
            "case_id": "c",
            "project_name": "p",
            "fps": 10,
            "total_frames": 1,
            "clip_duration_sec": 0.1,
            "streams": [
                {
                    "id": "cam",
                    "label": "cam",
                    "src": "http://x",
                    "extrinsics": {"position": {"x": 1, "y": 0, "z": 0}, "orientation": {"roll": 0, "pitch": 0, "yaw": 0}},
                }
            ],
        }
    )
    task = SimpleNamespace(id=1, data={"embodied_vla": {}}, data_url=None, task_metadata={})
    state = {
        "action_labels": [{"id": "idle", "label": "待机"}],
        "frame_actions": {0: {"action_id": "idle", "note": ""}},
        "committed_frames": [],
        "instruction": "hi",
        "success": "unknown",
        "segments": [],
        "grasps": [],
        "trajectory": [],
        "preferences": [],
    }
    doc = build_export_json(task, SimpleNamespace(id=1), state, ep)
    assert doc["schema"] == "dasshine.embodied_sequence.v7"
    assert doc["streams"][0]["extrinsics"]["position"]["x"] == 1


def test_embodied_quality_summary():
    q = compute_embodied_quality(
        {
            "instruction": "",
            "success": "success",
            "segments": [{"start_frame": 0, "end_frame": 4}],
            "grasps": [{"frame": 2}, {"frame": 99}],
            "trajectory": [{"frame": 0}],
            "preferences": [{"id": "p"}],
            "frames": [{} for _ in range(10)],
            "committed_frames": [0, 1],
        }
    )
    assert q["instruction_empty"] is True
    assert q["segment_coverage"] == 0.5
    assert q["grasp_out_of_bounds"] == 1
    assert q["preference_count"] == 1


def test_policy_weights_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.embodied_policy_weights.settings.EMBODIED_POLICY_WEIGHTS_DIR",
        str(tmp_path / "weights"),
    )
    item = save_policy_weight(filename="policy.pt", content=b"abc", name="demo")
    assert item["id"]
    reg = list_policy_weights()
    assert reg["active_id"] == item["id"]
    item2 = save_policy_weight(filename="other.pt", content=b"xyz", name="other")
    activate_policy_weight(item2["id"])
    assert list_policy_weights()["active_id"] == item2["id"]
    assert Path(item["path"]).is_file()


def test_example_from_step_bytes():
    raw = example_from_step(
        {
            "observation": {"state": [0.1], "force": [0, 0, 0, 0, 0, 0], "tactile": [0.2]},
            "action": {"label": "grasp", "label_text": "抓"},
            "reward": 1,
            "is_first": True,
            "is_last": True,
            "language_instruction": "pick",
            "timestamp": 0.1,
        },
        episode_id="ep",
        step_index=0,
    )
    assert b"language_instruction" in raw or len(raw) > 20
