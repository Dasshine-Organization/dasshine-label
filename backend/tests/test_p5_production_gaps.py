"""P5 产线缺口：OCR modality、质控契约、审核 ACL、modality 预览。"""

from types import SimpleNamespace

from app.models.user import UserRole
from app.services.modality_workspace import default_payload, resolve_modality
from app.services.project_acl import can_review_project
from app.services.quality_control import QualityControlService


class _FakeDb:
    def __init__(self, member):
        self._member = member

    def query(self, *_a, **_k):
        return self

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self._member


def test_resolve_modality_ocr():
    assert resolve_modality("ocr", "ocr_text") == "ocr"
    assert resolve_modality("nlp", "ner") == "text"
    assert resolve_modality(None, "ocr_layout") == "ocr"


def test_ocr_default_payload_has_spans():
    p = default_payload("ocr", "ocr_text")
    assert p["modality"] == "ocr"
    assert p["spans"] == []


def test_platform_reviewer_member_can_review():
    project = SimpleNamespace(id=1, created_by_id=99)
    user = SimpleNamespace(id=5, role=UserRole.REVIEWER)
    member = SimpleNamespace(role="annotator", user_id=5, project_id=1)
    assert can_review_project(_FakeDb(member), project, user) is True


def test_platform_reviewer_without_membership_cannot_review():
    project = SimpleNamespace(id=1, created_by_id=99)
    user = SimpleNamespace(id=5, role=UserRole.REVIEWER)
    assert can_review_project(_FakeDb(None), project, user) is False


def test_extract_result_key_spans_and_bbox():
    svc = QualityControlService(db=None)  # type: ignore[arg-type]
    key = svc._extract_result_key({
        "modality": "ocr",
        "spans": [
            {"label": "text", "text": "Hello", "bbox": [1, 2, 3, 4]},
            {"label": "title", "text": "Hi", "bbox": [0, 0, 10, 10]},
        ],
    })
    assert "Hello" in key and "title" in key


def test_extract_result_key_unwraps_golden_data():
    svc = QualityControlService(db=None)  # type: ignore[arg-type]
    nested = svc._extract_result_key({"data": {"label": "cat"}, "source": "expert"})
    flat = svc._extract_result_key({"label": "cat"})
    assert nested == flat
