"""P10：组织配额、导入 job 契约、黄金轮换配置。"""

from types import SimpleNamespace

from app.services.org_quota import (
    DEFAULT_QUOTA,
    check_can_add_member,
    check_can_add_project,
    check_can_add_tasks,
    normalize_quota,
    org_usage,
)


def test_normalize_quota_defaults():
    assert normalize_quota(None) == DEFAULT_QUOTA
    assert normalize_quota({"max_projects": 3})["max_projects"] == 3
    assert normalize_quota({"max_projects": 3})["max_tasks"] == DEFAULT_QUOTA["max_tasks"]


def test_check_can_add_project_at_limit():
    org = SimpleNamespace(id=1, quota={"max_projects": 1, "max_tasks": 100, "max_members": 10})

    class FakeDb:
        def query(self, model):
            return self

        def filter(self, *a, **k):
            return self

        def all(self):
            # one project already
            return [SimpleNamespace(id=9)]

        def count(self):
            return 1

    ok, msg = check_can_add_project(FakeDb(), org)
    assert ok is False
    assert "上限" in msg


def test_check_can_add_tasks_allows_when_under():
    org = SimpleNamespace(id=1, quota={"max_projects": 10, "max_tasks": 5, "max_members": 10})

    class FakeDb:
        def query(self, model):
            self._model = model
            return self

        def filter(self, *a, **k):
            return self

        def all(self):
            return [SimpleNamespace(id=1), SimpleNamespace(id=2)]

        def count(self):
            # members or tasks
            name = getattr(self._model, "__name__", "")
            if name == "Task":
                return 2
            return 1

    ok, _ = check_can_add_tasks(FakeDb(), org, add_count=2)
    assert ok is True
    ok2, msg = check_can_add_tasks(FakeDb(), org, add_count=4)
    assert ok2 is False
    assert "任务" in msg


def test_check_can_add_member():
    org = SimpleNamespace(id=1, quota={"max_projects": 10, "max_tasks": 100, "max_members": 1})

    class FakeDb:
        def query(self, model):
            return self

        def filter(self, *a, **k):
            return self

        def all(self):
            return []

        def count(self):
            return 1

    ok, msg = check_can_add_member(FakeDb(), org)
    assert ok is False
    assert "成员" in msg


def test_org_usage_shape_with_empty():
    class FakeDb:
        def query(self, model):
            return self

        def filter(self, *a, **k):
            return self

        def all(self):
            return []

        def count(self):
            return 0

    u = org_usage(FakeDb(), 1)
    assert u == {"projects": 0, "tasks": 0, "members": 0}


def test_import_task_module_importable():
    from app.tasks import import_tasks

    assert hasattr(import_tasks, "import_project_archive")


def test_rotate_golden_task_registered():
    from app.tasks.quality_tasks import rotate_golden_tasks

    assert callable(rotate_golden_tasks)
