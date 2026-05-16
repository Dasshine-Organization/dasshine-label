"""
具身标注业务逻辑：任务解析、工作区、导出
"""

from __future__ import annotations

import csv
import io
import json
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.annotation import Annotation, AnnotationStatus, AnnotationType
from app.models.embodied import EmbodiedFrameAnnotation, EmbodiedWorkspace
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.embodied_episodes import (
    DEFAULT_ACTION_LABELS,
    JOINT_NAMES,
    episode_for_slug,
    resolve_episode,
)


def _round(x: float, d: int) -> float:
    p = 10**d
    return round(x * p) / p


def joint_states_for_frame(frame: int, total_frames: int) -> List[Dict[str, Any]]:
    tf = max(1, total_frames)
    f = frame % tf
    t = f * 0.12
    out: List[Dict[str, Any]] = []
    for j, name in enumerate(JOINT_NAMES):
        position_rad = math.sin(t + j * 0.55) * 1.1 + (j - 2.5) * 0.08
        torque_nm = math.cos(t * 1.3 + j * 0.7) * 3.2 + math.sin(f * 0.21 + j) * 0.4
        out.append(
            {
                "name": name,
                "position_rad": _round(position_rad, 4),
                "torque_nm": _round(torque_nm, 3),
            }
        )
    return out


def frame_to_time_sec(frame: int, total_frames: int, clip_duration_sec: float) -> float:
    if total_frames <= 1:
        return 0.0
    clamped = max(0, min(total_frames - 1, frame))
    return (clamped / (total_frames - 1)) * clip_duration_sec


def get_task_ref(task: Task) -> str:
    meta = task.task_metadata or {}
    slug = meta.get("embodied_slug")
    if slug:
        return str(slug)
    data = task.data or {}
    if data.get("embodied_slug"):
        return str(data["embodied_slug"])
    return str(task.id)


def resolve_task(db: Session, task_ref: str) -> Optional[Task]:
    if task_ref.isdigit():
        by_id = db.query(Task).filter(Task.id == int(task_ref)).first()
        if by_id:
            return by_id
    for t in db.query(Task).all():
        meta = t.task_metadata or {}
        data = t.data or {}
        if meta.get("embodied_slug") == task_ref or data.get("embodied_slug") == task_ref:
            return t
    return None


def get_episode_dict(task: Task) -> Dict[str, Any]:
    meta = task.task_metadata or {}
    data = task.data or {}
    slug = meta.get("embodied_slug") or data.get("embodied_slug")
    if not slug and get_task_ref(task).isdigit():
        slug = "demo"
    return resolve_episode(task.data, str(slug) if slug else "demo")


def get_or_create_workspace(db: Session, task: Task, user: User) -> EmbodiedWorkspace:
    row = (
        db.query(EmbodiedWorkspace)
        .filter(EmbodiedWorkspace.task_id == task.id, EmbodiedWorkspace.user_id == user.id)
        .first()
    )
    if row:
        return row
    ep = get_episode_dict(task)
    total = int(ep.get("total_frames", 24))
    row = EmbodiedWorkspace(
        task_id=task.id,
        user_id=user.id,
        action_labels=list(DEFAULT_ACTION_LABELS),
        committed_frames=[],
    )
    db.add(row)
    db.flush()
    for i in range(total):
        db.add(
            EmbodiedFrameAnnotation(
                workspace_id=row.id,
                frame_index=i,
                action_id="idle",
                note=None,
                is_committed=False,
            )
        )
    db.commit()
    db.refresh(row)
    return row


def workspace_to_state(
    db: Session, task: Task, workspace: EmbodiedWorkspace
) -> Dict[str, Any]:
    frames = (
        db.query(EmbodiedFrameAnnotation)
        .filter(EmbodiedFrameAnnotation.workspace_id == workspace.id)
        .order_by(EmbodiedFrameAnnotation.frame_index)
        .all()
    )
    frame_actions: Dict[int, Dict[str, Any]] = {}
    committed: List[int] = []
    for fr in frames:
        frame_actions[fr.frame_index] = {
            "action_id": fr.action_id,
            "note": fr.note or "",
        }
        if fr.is_committed:
            committed.append(fr.frame_index)
    if workspace.committed_frames:
        committed = sorted(set(committed) | set(workspace.committed_frames))
    return {
        "task_id": task.id,
        "task_ref": get_task_ref(task),
        "user_id": workspace.user_id,
        "action_labels": workspace.action_labels or list(DEFAULT_ACTION_LABELS),
        "frame_actions": frame_actions,
        "committed_frames": sorted(committed),
        "updated_at": workspace.updated_at,
    }


def apply_workspace_put(
    db: Session,
    workspace: EmbodiedWorkspace,
    action_labels: List[Dict[str, str]],
    frame_actions: Dict[int, Dict[str, Any]],
    committed_frames: List[int],
) -> None:
    if not action_labels:
        raise ValueError("至少保留一个动作标签")
    if not any(l.get("id") == "idle" for l in action_labels):
        raise ValueError("必须保留 id=idle 的「待机」标签")
    names = [l.get("label", "").strip() for l in action_labels]
    if len(names) != len(set(names)):
        raise ValueError("标签名称不能重复")

    workspace.action_labels = action_labels
    workspace.committed_frames = sorted(set(int(x) for x in committed_frames))
    committed_set = set(workspace.committed_frames)

    frames = {
        fr.frame_index: fr
        for fr in db.query(EmbodiedFrameAnnotation)
        .filter(EmbodiedFrameAnnotation.workspace_id == workspace.id)
        .all()
    }
    for idx, ann in frame_actions.items():
        i = int(idx)
        fr = frames.get(i)
        if not fr:
            fr = EmbodiedFrameAnnotation(workspace_id=workspace.id, frame_index=i)
            db.add(fr)
            frames[i] = fr
        fr.action_id = ann.get("action_id") or "idle"
        fr.note = ann.get("note") or None
        fr.is_committed = i in committed_set
    for i in committed_set:
        if i in frames:
            frames[i].is_committed = True
    db.commit()


def patch_frame(
    db: Session,
    workspace: EmbodiedWorkspace,
    frame_index: int,
    action_id: Optional[str],
    note: Optional[str],
    commit: Optional[bool],
) -> EmbodiedFrameAnnotation:
    fr = (
        db.query(EmbodiedFrameAnnotation)
        .filter(
            EmbodiedFrameAnnotation.workspace_id == workspace.id,
            EmbodiedFrameAnnotation.frame_index == frame_index,
        )
        .first()
    )
    if not fr:
        fr = EmbodiedFrameAnnotation(
            workspace_id=workspace.id, frame_index=frame_index, action_id="idle"
        )
        db.add(fr)
    if action_id is not None:
        fr.action_id = action_id
    if note is not None:
        fr.note = note or None
    if commit is True:
        fr.is_committed = True
        committed = set(workspace.committed_frames or [])
        committed.add(frame_index)
        workspace.committed_frames = sorted(committed)
    elif commit is False:
        fr.is_committed = False
        committed = [x for x in (workspace.committed_frames or []) if x != frame_index]
        workspace.committed_frames = committed
    db.commit()
    db.refresh(fr)
    return fr


def label_text(labels: List[Dict[str, str]], action_id: str) -> str:
    for l in labels:
        if l.get("id") == action_id:
            return l.get("label", action_id)
    return action_id


def build_export_json(
    task: Task,
    workspace: EmbodiedWorkspace,
    state: Dict[str, Any],
    episode: Dict[str, Any],
) -> Dict[str, Any]:
    labels = state["action_labels"]
    committed = set(state["committed_frames"])
    total_frames = int(episode["total_frames"])
    clip_duration_sec = float(episode["clip_duration_sec"])
    fps = int(episode["fps"])
    frame_actions = state["frame_actions"]

    frames_out: List[Dict[str, Any]] = []
    for i in range(total_frames):
        ann = frame_actions.get(i) or frame_actions.get(str(i)) or {"action_id": "idle", "note": ""}
        action_id = ann.get("action_id", "idle")
        joints = joint_states_for_frame(i, total_frames)
        frames_out.append(
            {
                "index": i,
                "timestamp_ms": round(
                    (i / max(1, total_frames - 1)) * clip_duration_sec * 1000
                ),
                "action": {"id": action_id, "label": label_text(labels, action_id)},
                "note": ann.get("note") or "",
                "annotation_saved": i in committed,
                "joints": [
                    {
                        "name": j["name"],
                        "position_rad": j["position_rad"],
                        "position_deg": _round((j["position_rad"] * 180) / math.pi, 2),
                        "torque_nm": j["torque_nm"],
                    }
                    for j in joints
                ],
            }
        )

    streams = episode.get("streams") or []
    return {
        "schema": "dasshine.embodied_sequence.v3",
        "task_id": get_task_ref(task),
        "task_db_id": task.id,
        "case_id": episode.get("case_id"),
        "project": episode.get("project_name"),
        "clip_duration_sec": clip_duration_sec,
        "fps": fps,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "action_labels": labels,
        "committed_frames": sorted(committed),
        "streams": [
            {"id": s.get("id"), "label": s.get("label"), "src": s.get("src")}
            for s in streams
        ],
        "attribution": episode.get("attribution"),
        "frames": frames_out,
    }


def build_torque_csv(state: Dict[str, Any], episode: Dict[str, Any]) -> str:
    total_frames = int(episode["total_frames"])
    clip_duration_sec = float(episode["clip_duration_sec"])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["frame_index", "timestamp_ms", "joint", "torque_nm"])
    for i in range(total_frames):
        ts = round((i / max(1, total_frames - 1)) * clip_duration_sec * 1000)
        for j in joint_states_for_frame(i, total_frames):
            w.writerow([i, ts, j["name"], j["torque_nm"]])
    return buf.getvalue()


def submit_annotation(
    db: Session,
    task: Task,
    user: User,
    workspace: EmbodiedWorkspace,
    work_time: int,
) -> Annotation:
    episode = get_episode_dict(task)
    state = workspace_to_state(db, task, workspace)
    payload = build_export_json(task, workspace, state, episode)

    existing = (
        db.query(Annotation)
        .filter(
            Annotation.task_id == task.id,
            Annotation.annotator_id == user.id,
            Annotation.annotation_type == AnnotationType.ROBOT_ACTION,
            Annotation.is_latest.is_(True),
        )
        .first()
    )
    if existing:
        existing.data = payload
        existing.work_time = work_time
        existing.version += 1
        ann = existing
    else:
        ann = Annotation(
            id=str(uuid.uuid4()),
            task_id=task.id,
            data_id=get_task_ref(task),
            annotation_type=AnnotationType.ROBOT_ACTION,
            data=payload,
            status=AnnotationStatus.COMPLETED,
            annotator_id=user.id,
            work_time=work_time,
            is_latest=True,
        )
        db.add(ann)

    task.status = TaskStatus.SUBMITTED
    task.submitted_at = datetime.now(timezone.utc)
    task.work_time = work_time
    db.commit()
    db.refresh(ann)
    return ann
