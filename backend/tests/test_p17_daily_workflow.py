"""P17：标注规范、驳回定位、一致率自动过审、领取暂停、跳过。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.guidelines import (
    ack_guidelines,
    ensure_guidelines_acked,
    guidelines_payload,
    update_guidelines,
)
from app.services.task_completion import maybe_auto_approve_on_agreement
from app.services.quality_control import QualityControlService


def test_update_and_ack_guidelines():
    project = SimpleNamespace(
        id=1,
        created_by_id=9,
        quality_config={},
    )
    update_guidelines(project, markdown="# 规范\n画框要对齐", must_read=True, bump=True)
    assert project.quality_config["guidelines_version"] == 1
    assert "画框" in project.quality_config["guidelines_md"]

    user = SimpleNamespace(id=3, is_admin=False)
    member = SimpleNamespace(project_id=1, user_id=3, meta={})

    class Db:
        def add(self, obj):
            self.added = obj

        def flush(self):
            pass

    from app.services import guidelines as g

    def fake_member(db, pid, uid):
        return member

    # monkey via assignment
    orig = g.get_project_member
    g.get_project_member = fake_member  # type: ignore
    try:
        st = guidelines_payload(project, user, Db())
        assert st["needs_ack"] is True
        ok, payload = ack_guidelines(Db(), project, user)
        assert ok
        assert member.meta["guideline_ack_version"] == 1
        assert payload["needs_ack"] is False
        assert ensure_guidelines_acked(Db(), project, user) is None
    finally:
        g.get_project_member = orig  # type: ignore


def test_owner_skips_ack():
    project = SimpleNamespace(
        id=1,
        created_by_id=3,
        quality_config={"guidelines_md": "x", "guidelines_version": 2, "guidelines_must_read": True},
    )
    user = SimpleNamespace(id=3, is_admin=False)
    st = guidelines_payload(project, user, MagicMock())
    assert st["needs_ack"] is False


def test_auto_approve_respects_flag(monkeypatch):
    project = SimpleNamespace(quality_config={"auto_approve_on_agreement": False})
    task = SimpleNamespace(project=project, id=1, task_metadata={"cross_validate_count": 2})
    out = maybe_auto_approve_on_agreement(MagicMock(), task)
    assert out["auto_approved"] is False


def test_auto_approve_on_high_agreement(monkeypatch):
    from app.models.task import TaskStatus

    project = SimpleNamespace(
        quality_config={"auto_approve_on_agreement": True, "min_agreement": 0.8}
    )
    task = SimpleNamespace(
        id=7,
        project=project,
        status=TaskStatus.SUBMITTED,
        task_metadata={"cross_validate_count": 2},
        canonical_annotation_id=None,
    )

    class Agr:
        agreement_rate = 0.95

    monkeypatch.setattr(
        QualityControlService,
        "calculate_cross_validation",
        lambda self, tid: Agr(),
    )
    monkeypatch.setattr(
        "app.services.task_completion.latest_annotations",
        lambda t: [SimpleNamespace(id="a1")],
        raising=False,
    )

    # patch imports used inside function
    import app.services.task_completion as tc

    monkeypatch.setattr(
        "app.services.consensus.latest_annotations",
        lambda t: [SimpleNamespace(id="a1")],
    )
    monkeypatch.setattr("app.services.consensus.set_canonical", lambda db, t, aid: True)

    out = tc.maybe_auto_approve_on_agreement(MagicMock(), task)
    assert out["auto_approved"] is True
    assert task.status == TaskStatus.APPROVED


def test_review_request_accepts_targets():
    from app.api.v1.quality import ReviewRequest

    req = ReviewRequest(
        task_id=1,
        decision="rejected",
        feedback="框偏了",
        targets=[{"object_id": "box_1", "label": "car", "note": "偏右"}],
    )
    assert req.targets[0]["object_id"] == "box_1"


def test_notification_to_dict():
    from datetime import datetime, timezone

    from app.services.notifications import to_dict

    row = SimpleNamespace(
        id=1,
        type="task_rejected",
        title="驳回",
        body="请修改",
        payload={"task_id": 9},
        read_at=None,
        created_at=datetime.now(timezone.utc),
    )
    d = to_dict(row)
    assert d["read"] is False
    assert d["payload"]["task_id"] == 9
