"""P19 契约：manifest、版本递增、入池、中位数、空项目分析。"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.export_snapshots import build_manifest, next_version
from app.services.project_analytics import _median, get_project_analytics


def test_build_manifest():
    tasks = [
        SimpleNamespace(id=1, canonical_annotation_id="ann_a"),
        SimpleNamespace(id=2, canonical_annotation_id=None),
    ]
    m = build_manifest(tasks)
    assert m[0]["task_id"] == 1
    assert m[0]["canonical_annotation_id"] == "ann_a"
    assert m[1]["canonical_annotation_id"] is None


def test_next_version_increments():
    class Db:
        def query(self, *a):
            return self

        def filter(self, *a):
            return self

        def scalar(self):
            return 2

    assert next_version(Db(), 1) == 3


def test_sync_pool_marks_low_confidence():
    from app.models.task import TaskStatus
    from app.services.active_learning import sync_pool

    project = SimpleNamespace(id=1, quality_config={"active_learning_threshold": 0.7})
    low = SimpleNamespace(
        id=10,
        pre_label_confidence=0.4,
        status=TaskStatus.PENDING,
        assignee_id=None,
        task_metadata={},
    )
    high = SimpleNamespace(
        id=11,
        pre_label_confidence=0.95,
        status=TaskStatus.PENDING,
        assignee_id=None,
        task_metadata={"active_learning_pool": True},
    )

    class Db:
        def query(self, model):
            return self

        def filter(self, *a):
            return self

        def all(self):
            return [low, high]

        def flush(self):
            pass

    out = sync_pool(Db(), project)
    assert out["added"] == 1
    assert out["removed"] == 1
    assert low.task_metadata.get("active_learning_pool") is True
    assert "active_learning_pool" not in high.task_metadata


def test_median_helper():
    assert _median([1.0, 2.0, 9.0]) == 2.0
    assert _median([]) is None


def test_analytics_empty_project():
    project = SimpleNamespace(id=1, quality_config={}, annotation_schema={"price_per_task": 1.5})

    class Db:
        def query(self, *a):
            return self

        def filter(self, *a):
            return self

        def group_by(self, *a):
            return self

        def order_by(self, *a):
            return self

        def all(self):
            return []

        def scalar(self):
            return 0

    data = get_project_analytics(Db(), project, days=7)
    assert data["summary"]["total_tasks"] == 0
    assert data["summary"]["approved_in_window"] == 0
    assert data["price_per_task"] == 1.5
    assert data["daily_throughput"] == []
