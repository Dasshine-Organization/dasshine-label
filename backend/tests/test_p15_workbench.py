"""P15 工作台诚实化：MOT 插值、默认 payload、导出、创建向导类型。"""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.api.v1.projects import _meta_categories
from app.api.v1.quality import _extract_modality_preview
from app.services.exporters import build_export
from app.services.image_annotation import _payload_has_work
from app.services.modality_workspace import default_payload
from app.services.video_tracks import interpolate_bbox, sampled_track_boxes


def test_interpolate_bbox_lerp():
    kfs = [
        {"t": 0, "bbox": [0, 0, 10, 10]},
        {"t": 2, "bbox": [10, 0, 10, 10]},
    ]
    box = interpolate_bbox(kfs, 1)
    assert box is not None
    assert abs(box[0] - 5) < 1e-6


def test_sampled_track_boxes_nonempty():
    track = {
        "track_id": 1,
        "label": "person",
        "keyframes": [
            {"t": 0, "bbox": [0.1, 0.1, 0.2, 0.2]},
            {"t": 1, "bbox": [0.3, 0.1, 0.2, 0.2]},
        ],
    }
    samples = sampled_track_boxes(track, fps=5)
    assert len(samples) >= 5
    assert samples[0]["track_id"] == 1


def test_default_payloads_p15_fields():
    v = default_payload("video", "video_tracking")
    assert v["tracks"] == []
    a = default_payload("audio", "emotion_audio")
    assert "emotion" in a
    m = default_payload("multimodal", "rlhf")
    assert m["preferences"] == []
    o = default_payload("ocr", "ocr_table")
    assert o["spans"] == []


def test_payload_has_work_classification_and_points():
    assert _payload_has_work({"classificationLabels": ["cat"]})
    assert _payload_has_work({"pointLabels": {"0": "road"}})
    assert not _payload_has_work({"frames": {"0": []}})


def test_preview_unwraps_nested_annotation():
    ann = SimpleNamespace(
        data={
            "schema": "dasshine.modality_export.v1",
            "modality": "video",
            "annotation": {
                "modality": "video",
                "clips": [{"start_sec": 1, "end_sec": 2, "label": "run"}],
                "tracks": [{"track_id": 1, "label": "person", "keyframes": []}],
            },
        }
    )
    preview = _extract_modality_preview(ann, "video", "video_tracking")
    assert preview is not None
    assert preview["track_count"] == 1
    assert preview["clips"][0]["start"] == 1


def test_video_jsonl_includes_tracks():
    payload = {
        "annotation": {
            "clips": [{"start_sec": 1.0, "end_sec": 2.5, "label": "run"}],
            "tracks": [
                {
                    "track_id": 1,
                    "label": "person",
                    "keyframes": [
                        {"t": 0, "bbox": [0.1, 0.1, 0.2, 0.3]},
                        {"t": 1, "bbox": [0.2, 0.1, 0.2, 0.3]},
                    ],
                }
            ],
        }
    }
    task = SimpleNamespace(
        id=2,
        data={},
        data_url="http://x/a.mp4",
        annotations=[SimpleNamespace(id="a1", annotator_id=1, version=1, work_time=1, is_latest=True, data=payload)],
        status=SimpleNamespace(value="approved"),
        is_golden=False,
        task_metadata={},
    )
    artifact = build_export("video", "jsonl", [task], "v", [])
    row = json.loads(artifact.content.decode("utf-8").strip().splitlines()[0])
    assert row["tracks"][0]["track_id"] == 1
    assert row["tracks"][0]["sampled"]


def test_mm_jsonl_preferences():
    payload = {
        "annotation": {
            "caption": "",
            "preferences": [{"id": "p1", "prompt": "better?", "response_a": "a", "response_b": "b", "winner": "a"}],
        }
    }
    task = SimpleNamespace(
        id=3,
        data={},
        data_url="http://img",
        annotations=[SimpleNamespace(id="a1", annotator_id=1, version=1, work_time=1, is_latest=True, data=payload)],
        status=SimpleNamespace(value="approved"),
        is_golden=False,
        task_metadata={},
    )
    artifact = build_export("multimodal", "jsonl", [task], "m", [])
    row = json.loads(artifact.content.decode("utf-8").strip().splitlines()[0])
    assert row["preferences"][0]["winner"] == "a"


def test_meta_categories_honest():
    cats = {c["id"]: c for c in _meta_categories()}
    video_ids = {t["id"] for t in cats["video"]["types"]}
    assert "video_tracking" in video_ids
    image_ids = {t["id"] for t in cats["image_2d"]["types"]}
    assert "classification" in image_ids
    assert "keypoint" in image_ids
    pc_ids = {t["id"] for t in cats["pointcloud_3d"]["types"]}
    assert "lidar_seg" in pc_ids
    assert "lane_3d" not in pc_ids
    mm_ids = {t["id"] for t in cats["multimodal"]["types"]}
    assert "rlhf" in mm_ids
    ocr_ids = {t["id"] for t in cats["ocr"]["types"]}
    assert "ocr_layout" in ocr_ids and "ocr_table" in ocr_ids
