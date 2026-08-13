"""审核权限冒烟。"""

from types import SimpleNamespace

from app.models.user import UserRole
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


def test_admin_can_review():
    project = SimpleNamespace(id=1, created_by_id=99)
    admin = SimpleNamespace(id=2, role=UserRole.ADMIN)
    assert can_review_project(_FakeDb(None), project, admin) is True


def test_reviewer_member_can_review():
    project = SimpleNamespace(id=1, created_by_id=99)
    user = SimpleNamespace(id=3, role=UserRole.ANNOTATOR)
    member = SimpleNamespace(role="reviewer", user_id=3, project_id=1)
    assert can_review_project(_FakeDb(member), project, user) is True


def test_annotator_member_cannot_review():
    project = SimpleNamespace(id=1, created_by_id=99)
    user = SimpleNamespace(id=4, role=UserRole.ANNOTATOR)
    member = SimpleNamespace(role="annotator", user_id=4, project_id=1)
    assert can_review_project(_FakeDb(member), project, user) is False
