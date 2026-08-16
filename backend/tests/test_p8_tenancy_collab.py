"""P8：组织 slug、租户作用域过滤约定、任务占用锁冲突语义。"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.organization_service import OrganizationService, _slugify
from app.services.task_lock_service import TaskLockService


def test_slugify_basic():
    assert _slugify("Acme Corp!") == "acme-corp"
    assert _slugify("  ") == "org"


def test_org_to_dict():
    org = SimpleNamespace(id=1, name="Acme", slug="acme", created_by_id=9, quota=None)
    d = OrganizationService.to_dict(org)
    assert d["id"] == 1
    assert d["name"] == "Acme"
    assert d["slug"] == "acme"
    assert d["created_by_id"] == 9
    assert "quota" in d
    assert d["quota"]["max_projects"] == 50


def test_list_all_accepts_org_id_kw():
    """ProjectService.list_all 支持 org_id 作用域参数。"""
    from app.services.project_service import ProjectService
    import inspect

    sig = inspect.signature(ProjectService.list_all)
    assert "org_id" in sig.parameters


def test_lock_status_unlocked():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    st = TaskLockService(db).status(42)
    assert st == {"locked": False, "task_id": 42}


def test_lock_acquire_conflict():
    now = datetime.now(timezone.utc)
    holder_lock = SimpleNamespace(
        task_id=7,
        user_id=1,
        expires_at=now + timedelta(seconds=60),
        heartbeat_at=now,
    )
    db = MagicMock()
    # with_for_update().first() -> existing lock
    q = MagicMock()
    db.query.return_value = q
    q.filter.return_value = q
    q.with_for_update.return_value = q
    q.first.return_value = holder_lock

    holder = SimpleNamespace(id=1, username="alice")
    # second query for User
    def query_side(model):
        m = MagicMock()
        m.filter.return_value.first.return_value = holder
        return m

    db.query.side_effect = [
        q,  # TaskAnnotationLock
        MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=holder)))),
    ]

    task = SimpleNamespace(id=7)
    other = SimpleNamespace(id=2, username="bob")
    # Reset to simpler path: rebuild service call carefully
    db2 = MagicMock()
    chain = db2.query.return_value.filter.return_value.with_for_update.return_value
    chain.first.return_value = holder_lock
    db2.query.return_value.filter.return_value.first.return_value = holder

    result = TaskLockService(db2).acquire(task, other)
    assert result["acquired"] is False
    assert result["locked"] is True
    assert result["holder_user_id"] == 1
    assert result["holder_username"] == "alice"


def test_lock_acquire_same_user_renews():
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(
        task_id=7,
        user_id=2,
        expires_at=now + timedelta(seconds=10),
        heartbeat_at=now,
    )
    db = MagicMock()
    chain = db.query.return_value.filter.return_value.with_for_update.return_value
    chain.first.return_value = row
    user = SimpleNamespace(id=2, username="bob")
    task = SimpleNamespace(id=7)
    result = TaskLockService(db, ttl_seconds=120).acquire(task, user)
    assert result["acquired"] is True
    assert result["holder_user_id"] == 2
    db.commit.assert_called()
