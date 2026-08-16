"""租户硬隔离：org_scope 契约。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.user import UserRole
from app.services.org_scope import (
    project_visible_in_active_org,
    user_can_access_org_project,
)


class _FakeOrgSvc:
    def __init__(self, in_org=True):
        self._in_org = in_org

    def ensure_personal_org(self, user):
        if user.active_org_id is None:
            user.active_org_id = 1

    def user_in_org(self, user_id, org_id):
        return self._in_org


def test_project_visible_active_org_blocks_other():
    user = SimpleNamespace(id=2, is_admin=False, active_org_id=1, role=UserRole.ANNOTATOR)
    project = SimpleNamespace(id=9, organization_id=99, created_by_id=9)
    db = MagicMock()

    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "app.services.org_scope.OrganizationService", return_value=_FakeOrgSvc()
    ):
        assert project_visible_in_active_org(db, project, user) is False
        project.organization_id = 1
        assert project_visible_in_active_org(db, project, user) is True


def test_admin_without_active_org_sees_all_for_claim_scope():
    user = SimpleNamespace(id=1, is_admin=True, active_org_id=None, role=UserRole.ADMIN)
    project = SimpleNamespace(id=9, organization_id=99)
    db = MagicMock()
    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "app.services.org_scope.OrganizationService", return_value=_FakeOrgSvc()
    ):
        assert project_visible_in_active_org(db, project, user) is True


def test_user_can_access_requires_org_membership():
    user = SimpleNamespace(id=2, is_admin=False, active_org_id=1, role=UserRole.ANNOTATOR)
    project = SimpleNamespace(id=9, organization_id=5, created_by_id=2)
    db = MagicMock()

    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "app.services.org_scope.OrganizationService", return_value=_FakeOrgSvc(in_org=False)
    ), __import__("unittest.mock", fromlist=["patch"]).patch(
        "app.services.org_scope.get_project_member", return_value=None
    ):
        # creator but not in org → deny
        assert user_can_access_org_project(db, project, user) is False

    with __import__("unittest.mock", fromlist=["patch"]).patch(
        "app.services.org_scope.OrganizationService", return_value=_FakeOrgSvc(in_org=True)
    ), __import__("unittest.mock", fromlist=["patch"]).patch(
        "app.services.org_scope.get_project_member", return_value=None
    ):
        # creator + in org → allow
        assert user_can_access_org_project(db, project, user) is True
