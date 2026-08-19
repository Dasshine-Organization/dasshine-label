"""P16：/auto-label 不再 501；LLM/Whisper/OCR HTTP 适配器 + demo 启发式。"""

from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.auto_label import AutoLabelService, merge_ai_into_payload
from app.services.auto_label_adapters import (
    AutoLabelConfigError,
    AutoLabelUnsupportedError,
    _bbox_xywh,
    demo_ner,
    demo_sentiment,
    infer,
    llm_text,
    ocr_http,
    whisper_asr,
)


def _demo_on(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "AUTO_LABEL_ALLOW_DEMO", True)
    monkeypatch.setattr(settings, "AUTO_LABEL_ENABLED", True)
    monkeypatch.setattr(settings, "AUTO_LABEL_LLM_BASE_URL", None)
    monkeypatch.setattr(settings, "AUTO_LABEL_WHISPER_ENDPOINT", None)
    monkeypatch.setattr(settings, "AUTO_LABEL_OCR_ENDPOINT", None)
    monkeypatch.setattr(settings, "AUTO_LABEL_AUTO_SUBMIT", False)


def test_api_and_celery_no_longer_501():
    from app.api.v1 import auto_label as api_mod
    from app.tasks import auto_label_tasks as task_mod

    api_src = inspect.getsource(api_mod.process_single_task) + inspect.getsource(api_mod.batch_process)
    assert "501" not in api_src
    svc_src = inspect.getsource(AutoLabelService.process_task)
    assert "NotImplementedError" not in svc_src
    task_src = inspect.getsource(task_mod)
    assert "not_implemented" not in task_src


def test_demo_ner_known_entities():
    r = demo_ner("马斯克在上海创立了特斯拉。")
    labels = {h.label for h in r.hits}
    texts = {h.text for h in r.hits}
    assert "PER" in labels and "ORG" in labels and "LOC" in labels
    assert "马斯克" in texts and "特斯拉" in texts
    assert r.overall_confidence >= 0.8
    assert r.payload_patch["spans"]


def test_demo_sentiment_positive():
    r = demo_sentiment("这次体验非常好，很满意。")
    assert r.payload_patch["sentiment"] == "positive"
    assert r.overall_confidence >= 0.8


def test_infer_nlp_demo(monkeypatch):
    _demo_on(monkeypatch)
    r = infer(modality="text", ann_type="ner", content={"text": "马斯克在上海。"})
    assert r.adapter == "demo"
    assert r.payload_patch["spans"]


def test_infer_asr_demo(monkeypatch):
    _demo_on(monkeypatch)
    r = infer(modality="audio", ann_type="asr", content={"text": "你好世界", "audio_url": ""})
    assert r.payload_patch["transcript"]
    assert r.payload_patch["segments"]


def test_infer_ocr_demo(monkeypatch):
    _demo_on(monkeypatch)
    r = infer(modality="ocr", ann_type="ocr_text", content={"image_url": "http://x/a.png"})
    assert r.payload_patch["spans"][0]["bbox"] == [20, 20, 240, 48]


def test_infer_image_2d_points_to_prelabel(monkeypatch):
    _demo_on(monkeypatch)
    with pytest.raises(AutoLabelUnsupportedError, match="prelabel"):
        infer(modality="image_2d", ann_type="bbox_2d", content={"image_url": "http://x"})


def test_infer_requires_endpoint_without_demo(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(settings, "AUTO_LABEL_ALLOW_DEMO", False)
    monkeypatch.setattr(settings, "AUTO_LABEL_ENABLED", True)
    monkeypatch.setattr(settings, "AUTO_LABEL_LLM_BASE_URL", None)
    with pytest.raises(AutoLabelConfigError):
        infer(modality="text", ann_type="ner", content={"text": "hello"})


def test_llm_ner_parses_chat_completions(monkeypatch):
    monkeypatch.setattr(settings, "AUTO_LABEL_LLM_BASE_URL", "http://llm.local/v1")
    monkeypatch.setattr(settings, "AUTO_LABEL_LLM_API_KEY", "sk-test")
    monkeypatch.setattr(settings, "AUTO_LABEL_LLM_MODEL", "gpt-test")

    def fake_post(url, body, headers=None, timeout=None):
        assert url.endswith("/chat/completions")
        assert body["messages"]
        payload = {
            "spans": [
                {"start": 0, "end": 3, "label": "PER", "text": "马斯克", "confidence": 0.93},
            ]
        }
        return {"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]}

    monkeypatch.setattr("app.services.auto_label_adapters.post_json", fake_post)
    r = llm_text("ner", "马斯克在上海", [{"id": "PER"}, {"id": "LOC"}])
    assert r.adapter == "llm"
    assert r.payload_patch["spans"][0]["text"] == "马斯克"
    assert r.overall_confidence >= 0.9


def test_whisper_http_segments(monkeypatch):
    monkeypatch.setattr(settings, "AUTO_LABEL_WHISPER_ENDPOINT", "http://asr.local/v1/transcribe")

    def fake_post(url, body, headers=None, timeout=None):
        assert body["audio_url"] == "http://x/a.wav"
        return {
            "text": "你好",
            "confidence": 0.91,
            "segments": [{"start": 0.0, "end": 1.2, "text": "你好", "speaker": "A"}],
        }

    monkeypatch.setattr("app.services.auto_label_adapters.post_json", fake_post)
    r = whisper_asr("http://x/a.wav")
    assert r.adapter == "whisper"
    assert r.payload_patch["transcript"] == "你好"
    assert r.payload_patch["segments"][0]["end_ms"] == 1200


def test_ocr_http_paddle_quad(monkeypatch):
    monkeypatch.setattr(settings, "AUTO_LABEL_OCR_ENDPOINT", "http://ocr.local/v1")

    def fake_post(url, body, headers=None, timeout=None):
        return {
            "results": [[[[10, 10], [110, 10], [110, 40], [10, 40]], ("发票", 0.97)]],
        }

    monkeypatch.setattr("app.services.auto_label_adapters.post_json", fake_post)
    r = ocr_http("http://x/a.png")
    assert r.payload_patch["spans"][0]["text"] == "发票"
    bbox = r.payload_patch["spans"][0]["bbox"]
    assert bbox[0] == 10 and bbox[2] == 100


def test_bbox_xywh_passthrough():
    assert _bbox_xywh([20, 20, 240, 48]) == [20, 20, 240, 48]


def test_merge_fills_empty_and_skips_overlap():
    base = {"spans": [{"id": "h", "start": 0, "end": 2, "label": "PER", "text": "ab"}], "summary": ""}
    patch = {
        "spans": [
            {"id": "ai1", "start": 0, "end": 2, "label": "PER", "text": "ab"},
            {"id": "ai2", "start": 5, "end": 7, "label": "LOC", "text": "cd"},
        ],
        "summary": "hello",
    }
    out = merge_ai_into_payload(base, patch, meta={"model": "x"})
    ids = {s["id"] for s in out["spans"]}
    assert "h" in ids and "ai2" in ids and "ai1" not in ids
    assert out["summary"] == "hello"
    assert out["_auto_label"]["model"] == "x"


def test_process_task_writes_draft_and_pre_label(monkeypatch):
    _demo_on(monkeypatch)

    project = SimpleNamespace(
        id=1,
        name="ner-demo",
        category="nlp",
        ann_type="ner",
        annotation_schema={
            "category": "nlp",
            "ann_type": "ner",
            "label_classes": [{"id": "PER"}, {"id": "ORG"}, {"id": "LOC"}],
        },
        auto_label_model="demo",
        auto_label_threshold=0.8,
    )
    task = SimpleNamespace(
        id=11,
        project_id=1,
        project=project,
        data={"text": "马斯克在上海创立了特斯拉。"},
        data_url=None,
        assignee_id=7,
        pre_label_result=None,
        pre_label_confidence=None,
    )
    user = SimpleNamespace(id=7, username="ann")
    written = {}

    class Q:
        def __init__(self, val):
            self.val = val

        def filter(self, *a, **k):
            return self

        def first(self):
            return self.val

    class Db:
        def query(self, model):
            name = getattr(model, "__name__", "")
            table = getattr(model, "__tablename__", "")
            if table == "tasks" or name == "Task":
                return Q(task)
            if table == "users" or name == "User":
                return Q(user)
            return Q(None)

        def commit(self):
            pass

        def refresh(self, obj):
            pass

    def fake_save(db, t, u, payload):
        written["payload"] = payload
        return SimpleNamespace(payload=payload, task_id=t.id, user_id=u.id)

    monkeypatch.setattr("app.services.auto_label.save_workspace", fake_save)
    out = AutoLabelService(Db()).process_task(11, user_id=7)
    assert out.draft_written is True
    assert out.adapter == "demo"
    assert task.pre_label_confidence >= 0.8
    assert task.pre_label_result["schema"] == "dasshine.auto_label.v1"
    assert written["payload"]["spans"]
    assert out.recommended is True


def test_process_task_asr_end_to_end(monkeypatch):
    _demo_on(monkeypatch)
    project = SimpleNamespace(
        id=2,
        name="asr",
        category="audio",
        ann_type="asr",
        annotation_schema={"category": "audio", "ann_type": "asr"},
        auto_label_model="demo",
        auto_label_threshold=0.8,
    )
    task = SimpleNamespace(
        id=22,
        project_id=2,
        project=project,
        data={"text": "今天天气不错"},
        data_url="http://x/a.wav",
        assignee_id=1,
        pre_label_result=None,
        pre_label_confidence=None,
    )
    user = SimpleNamespace(id=1)
    written = {}

    class Q:
        def __init__(self, val):
            self.val = val

        def filter(self, *a, **k):
            return self

        def first(self):
            return self.val

    class Db:
        def query(self, model):
            table = getattr(model, "__tablename__", "")
            if table == "tasks":
                return Q(task)
            if table == "users":
                return Q(user)
            return Q(None)

        def commit(self):
            pass

        def refresh(self, obj):
            pass

    def fake_save(db, t, u, payload):
        written["payload"] = payload
        return SimpleNamespace(payload=payload)

    monkeypatch.setattr("app.services.auto_label.save_workspace", fake_save)
    out = AutoLabelService(Db()).process_task(22, user_id=1)
    assert written["payload"]["transcript"]
    assert written["payload"]["segments"]
    assert task.pre_label_result["modality"] == "audio"
    assert out.adapter == "demo"
