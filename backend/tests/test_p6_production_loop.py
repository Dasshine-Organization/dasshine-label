"""P6：多人共标门闩、共标 ACL、导出 job 入队契约。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.task import TaskStatus
from app.services.project_acl import cross_submit_progress, is_task_assignee
from app.services.task_completion import apply_cross_submit_gate, required_annotator_count


def test_is_task_assignee_primary_and_co():
    task = SimpleNamespace(
        assignee_id=1,
        task_metadata={"assignee_ids": [1, 2], "co_assignee_ids": [2], "cross_validate_count": 2},
    )
    assert is_task_assignee(task, SimpleNamespace(id=1)) is True
    assert is_task_assignee(task, SimpleNamespace(id=2)) is True
    assert is_task_assignee(task, SimpleNamespace(id=3)) is False


def test_required_annotator_count():
    task = SimpleNamespace(task_metadata={"cross_validate_count": 3})
    assert required_annotator_count(task) == 3
    task2 = SimpleNamespace(task_metadata=None)
    assert required_annotator_count(task2) == 1


def test_apply_cross_submit_gate_partial_then_full():
    task = SimpleNamespace(
        id=10,
        status=TaskStatus.ASSIGNED,
        task_metadata={"cross_validate_count": 2, "assignee_ids": [1, 2]},
        started_at=None,
        work_time=0,
        submitted_at=None,
    )

    # First annotator
    db = MagicMock()
    db.query.return_value.filter.return_value.distinct.return_value.all.return_value = [(1,)]
    p1 = apply_cross_submit_gate(db, task, 1, work_time=5)
    assert p1["fully_submitted"] is False
    assert p1["done"] == 1
    assert task.status == TaskStatus.ANNOTATING

    # Second annotator
    db2 = MagicMock()
    db2.query.return_value.filter.return_value.distinct.return_value.all.return_value = [
        (1,),
        (2,),
    ]
    p2 = apply_cross_submit_gate(db2, task, 2, work_time=8)
    assert p2["fully_submitted"] is True
    assert p2["done"] == 2
    assert task.status == TaskStatus.SUBMITTED


def test_cross_submit_progress_helper():
    task = SimpleNamespace(
        assignee_id=1,
        task_metadata={
            "cross_validate_count": 2,
            "submitted_annotator_ids": [1],
            "assignee_ids": [1, 2],
        },
    )
    prog = cross_submit_progress(task)
    assert prog["need"] == 2
    assert prog["done"] == 1
