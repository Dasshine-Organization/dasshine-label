"""P9：canonical 裁决、导出真源、审核多版本契约。"""

from types import SimpleNamespace

from app.services.consensus import latest_annotations, resolve_canonical_annotation, set_canonical
from app.services.exporters.common import primary_payload


def test_latest_annotations_sorted():
    a1 = SimpleNamespace(id="a1", is_latest=True, updated_at=1, created_at=1)
    a2 = SimpleNamespace(id="a2", is_latest=True, updated_at=3, created_at=2)
    a3 = SimpleNamespace(id="a3", is_latest=False, updated_at=9, created_at=9)
    task = SimpleNamespace(annotations=[a1, a2, a3], canonical_annotation_id=None)
    ids = [a.id for a in latest_annotations(task)]
    assert ids == ["a2", "a1"]


def test_resolve_canonical_prefers_id():
    a1 = SimpleNamespace(id="a1", is_latest=True, updated_at=1, created_at=1, data={"x": 1})
    a2 = SimpleNamespace(id="a2", is_latest=True, updated_at=3, created_at=2, data={"x": 2})
    task = SimpleNamespace(annotations=[a1, a2], canonical_annotation_id="a1")
    assert resolve_canonical_annotation(task).id == "a1"


def test_set_canonical():
    class FakeQ:
        def __init__(self, ann):
            self._ann = ann

        def filter(self, *a, **k):
            return self

        def first(self):
            return self._ann

    class FakeDb:
        def __init__(self, ann):
            self._ann = ann

        def query(self, *_a):
            return FakeQ(self._ann)

        def flush(self):
            pass

    ann = SimpleNamespace(id="ann-9", task_id=1)
    task = SimpleNamespace(id=1, canonical_annotation_id=None)
    assert set_canonical(FakeDb(ann), task, "ann-9") is True
    assert task.canonical_annotation_id == "ann-9"
    assert set_canonical(FakeDb(None), task, "missing") is False


def test_primary_payload_uses_canonical():
    a1 = SimpleNamespace(id="a1", is_latest=True, data={"v": 1})
    a2 = SimpleNamespace(id="a2", is_latest=True, data={"v": 2})
    task = SimpleNamespace(annotations=[a1, a2], canonical_annotation_id="a2")
    assert primary_payload(task) == {"v": 2}


def test_review_request_accepts_canonical_field():
    from app.api.v1.quality import ReviewRequest

    req = ReviewRequest(
        task_id=1,
        decision="approved",
        canonical_annotation_id="uuid-1",
    )
    assert req.canonical_annotation_id == "uuid-1"
