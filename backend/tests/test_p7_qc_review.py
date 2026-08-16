"""P7：黄金题盲测剥离、点云审核 preview。"""

from types import SimpleNamespace

from app.api.v1.quality import _extract_pointcloud_preview
from app.models.user import UserRole
from app.services.golden_blind import (
    can_see_golden,
    maybe_attach_golden_fields,
    strip_golden_from_task_payload,
)
from app.services.project_acl import can_review_project


class _FakeDb:
    def __init__(self, member):
        self._member = member

    def query(self, *_a, **_k):
        return self

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self._member


def test_strip_golden_fields():
    payload = {"task_id": 1, "is_golden": True, "golden_answer": {"data": {}}, "x": 1}
    out = strip_golden_from_task_payload(payload)
    assert "is_golden" not in out
    assert "golden_answer" not in out
    assert out["x"] == 1


def test_annotator_cannot_see_golden():
    project = SimpleNamespace(id=1, created_by_id=99)
    user = SimpleNamespace(id=4, role=UserRole.ANNOTATOR, is_admin=False)
    member = SimpleNamespace(role="annotator", user_id=4, project_id=1)
    task = SimpleNamespace(project=project, is_golden=True, golden_answer={"data": {"a": 1}})
    assert can_see_golden(_FakeDb(member), task, user) is False
    attached = maybe_attach_golden_fields(
        _FakeDb(member), task, user, {"task_id": 1, "is_golden": True, "golden_answer": {}}
    )
    assert "is_golden" not in attached
    assert "golden_answer" not in attached


def test_reviewer_can_see_golden():
    project = SimpleNamespace(id=1, created_by_id=99)
    user = SimpleNamespace(id=3, role=UserRole.ANNOTATOR, is_admin=False)
    member = SimpleNamespace(role="reviewer", user_id=3, project_id=1)
    task = SimpleNamespace(
        project=project,
        is_golden=True,
        golden_answer={"data": {"label": "ok"}, "source": "expert"},
    )
    assert can_review_project(_FakeDb(member), project, user) is True
    assert can_see_golden(_FakeDb(member), task, user) is True
    attached = maybe_attach_golden_fields(_FakeDb(member), task, user, {"task_id": 1})
    assert attached["is_golden"] is True
    assert attached["has_golden_answer"] is True


def test_extract_pointcloud_preview():
    ann = SimpleNamespace(
        data={
            "schema": "dasshine.pointcloud_export.v1",
            "session": {
                "boxes3d": [
                    {
                        "id": "b1",
                        "label": "car",
                        "center": {"x": 0, "y": 0, "z": 0},
                        "size": {"x": 1, "y": 1, "z": 1},
                    }
                ]
            },
        }
    )
    task = SimpleNamespace(data_url="/cloud.pcd", data={})
    preview = _extract_pointcloud_preview(task, ann)
    assert preview is not None
    assert preview["point_cloud_url"] == "/cloud.pcd"
    assert preview["box_count"] == 1
    assert preview["boxes3d"][0]["label"] == "car"
