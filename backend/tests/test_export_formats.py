"""全模态导出冒烟测试。"""

from __future__ import annotations

import io
import json
import zipfile
from types import SimpleNamespace

from app.services.exporters import build_export, default_format_for, list_formats
from app.services.exporters.registry import FORMATS_BY_CATEGORY


def _ann(data):
    return SimpleNamespace(
        id="a1",
        annotator_id=1,
        version=1,
        work_time=10,
        is_latest=True,
        data=data,
    )


def _task(task_id: int, data=None, anns=None, data_url=None):
    return SimpleNamespace(
        id=task_id,
        data=data or {},
        data_url=data_url or f"http://localhost/{task_id}",
        annotations=anns or [],
        status=SimpleNamespace(value="approved"),
        is_golden=False,
        task_metadata={},
    )


def test_each_category_has_three_primary_formats():
    for cat, formats in FORMATS_BY_CATEGORY.items():
        assert len(formats) == 3, cat
        assert default_format_for(cat) == formats[0].id
        listed = list_formats(cat, include_raw=True)
        assert listed[-1].id == "raw_json"
        assert len([f for f in listed if f.primary]) == 3


def test_image_yolo_and_voc_zip():
    session = {
        "schema": "dasshine.image_export.v1",
        "session": {
            "frames": {
                "0": [
                    {
                        "type": "bbox",
                        "label": "person",
                        "points": [{"x": 0, "y": 0}, {"x": 10, "y": 20}],
                    }
                ]
            }
        },
    }
    tasks = [_task(1, {"file_name": "1.jpg", "width": 100, "height": 80}, [_ann(session)])]
    yolo = build_export("image_2d", "yolo", tasks, "demo", [{"name": "person"}])
    assert yolo.media_type == "application/zip"
    with zipfile.ZipFile(io.BytesIO(yolo.content)) as zf:
        names = zf.namelist()
        assert "classes.txt" in names
        assert any(n.startswith("labels/") for n in names)
    voc = build_export("image_2d", "voc", tasks, "demo", [])
    with zipfile.ZipFile(io.BytesIO(voc.content)) as zf:
        names = zf.namelist()
        assert any(n.startswith("Annotations/") for n in names)
        xml = zf.read(names[0]).decode("utf-8")
        assert "person" in xml


def test_pointcloud_kitti_openpcdet():
    payload = {
        "schema": "dasshine.pointcloud_export.v1",
        "session": {
            "boxes3d": [
                {
                    "label": "Car",
                    "center": {"x": 1, "y": 2, "z": 3},
                    "size": {"x": 4, "y": 1.5, "z": 2},
                    "rotation": {"z": 0.1},
                }
            ]
        },
    }
    tasks = [_task(7, {"file_name": "000007.bin"}, [_ann(payload)])]
    kitti = build_export("pointcloud_3d", "kitti", tasks, "pc", [])
    with zipfile.ZipFile(io.BytesIO(kitti.content)) as zf:
        content = zf.read("label_2/000007.txt").decode("utf-8")
        assert content.startswith("Car ")
    op = build_export("pointcloud_3d", "openpcdet", tasks, "pc", [])
    doc = json.loads(op.content.decode("utf-8"))
    assert doc["infos"][0]["annos"]["name"] == ["Car"]


def test_nlp_jsonl_conll():
    payload = {
        "schema": "dasshine.modality_export.v1",
        "content": {"text": "Alice lives in Paris"},
        "annotation": {
            "schema": "dasshine.modality.v1",
            "spans": [{"start": 0, "end": 5, "label": "PER", "text": "Alice"}],
        },
    }
    tasks = [_task(3, {"text": "Alice lives in Paris"}, [_ann(payload)])]
    jl = build_export("nlp", "jsonl", tasks, "nlp", [])
    row = json.loads(jl.content.decode("utf-8").strip().splitlines()[0])
    assert row["spans"][0]["label"] == "PER"
    conll = build_export("nlp", "conll", tasks, "nlp", [])
    assert "B-PER" in conll.content.decode("utf-8")


def test_audio_rttm_and_video_webvtt():
    audio = {
        "annotation": {
            "segments": [{"start_ms": 0, "end_ms": 1500, "speaker": "A", "text": "hi"}],
            "transcript": "hi",
        }
    }
    video = {
        "annotation": {
            "clips": [{"start_sec": 1.0, "end_sec": 2.5, "label": "run"}],
            "caption": "demo",
        }
    }
    a = build_export("audio", "rttm", [_task(1, {}, [_ann(audio)], "http://x/a.wav")], "a", [])
    assert "SPEAKER" in a.content.decode("utf-8")
    v = build_export("video", "webvtt", [_task(2, {}, [_ann(video)])], "v", [])
    assert v.content.decode("utf-8").startswith("WEBVTT")


def test_ocr_and_multimodal_and_embodied():
    ocr = {
        "annotation": {
            "spans": [{"text": "发票", "bbox": [1, 2, 30, 10]}],
        }
    }
    o = build_export("ocr", "paddleocr", [_task(1, {"file_name": "r.jpg"}, [_ann(ocr)])], "o", [])
    assert "发票" in o.content.decode("utf-8")

    mm = {
        "annotation": {
            "caption": "a cat",
            "vqa": {"question": "what?", "answer": "cat"},
        }
    }
    s = build_export("multimodal", "sharegpt", [_task(2, {}, [_ann(mm)], "http://img")], "m", [])
    row = json.loads(s.content.decode("utf-8").strip().splitlines()[0])
    assert row["conversations"]

    emb = {
        "schema": "dasshine.embodied_sequence.v3",
        "task_db_id": 9,
        "frames": [
            {
                "index": 0,
                "timestamp_ms": 0,
                "action": {"id": "pick", "label": "抓取"},
                "joints": [{"name": "j1", "position_rad": 0.1, "torque_nm": 1.2}],
            }
        ],
    }
    lr = build_export("embodied", "lerobot_jsonl", [_task(9, {}, [_ann(emb)])], "e", [])
    line = json.loads(lr.content.decode("utf-8").strip().splitlines()[0])
    assert line["action"] == "pick"
