"""
具身标注业务逻辑：任务解析、工作区、导出
"""

from __future__ import annotations

import csv
import io
import json
import math
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.annotation import Annotation, AnnotationStatus, AnnotationType
from app.models.embodied import EmbodiedFrameAnnotation, EmbodiedWorkspace
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.services.embodied_episodes import (
    DEFAULT_ACTION_LABELS,
    JOINT_NAMES,
    resolve_episode,
)

TACTILE_PAD_NAMES = ("pad_thumb", "pad_index", "pad_middle", "pad_palm")


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


def resolve_joints_for_frame(episode: Dict[str, Any], frame: int, total_frames: int) -> Tuple[List[Dict[str, Any]], str]:
    """优先 episode.proprioception 真值，否则 mock。返回 (joints, source)。"""
    by_idx = episode.get("_proprio_by_index")
    if not isinstance(by_idx, dict):
        by_idx = {}
        prop = episode.get("proprioception") or []
        if isinstance(prop, list):
            for row in prop:
                if isinstance(row, dict):
                    try:
                        idx = int(row.get("index", row.get("frame_index", -1)))
                    except (TypeError, ValueError):
                        continue
                    if idx >= 0:
                        by_idx[idx] = row
    row = by_idx.get(frame) or by_idx.get(str(frame))
    if isinstance(row, dict):
        joints = row.get("joints")
        if isinstance(joints, list) and joints:
            normalized = []
            for j in joints:
                if not isinstance(j, dict):
                    continue
                pos = j.get("position_rad")
                if pos is None and j.get("position") is not None:
                    pos = j.get("position")
                normalized.append(
                    {
                        "name": str(j.get("name") or "joint"),
                        "position_rad": float(pos or 0),
                        "torque_nm": float(j.get("torque_nm") or j.get("torque") or 0),
                    }
                )
            if normalized:
                return normalized, "episode"
        # state vector without names
        state = row.get("state") or row.get("observation.state")
        if isinstance(state, list) and state:
            joints = []
            for i, val in enumerate(state):
                name = JOINT_NAMES[i] if i < len(JOINT_NAMES) else f"j{i}"
                joints.append(
                    {
                        "name": name,
                        "position_rad": float(val),
                        "torque_nm": 0.0,
                    }
                )
            return joints, "episode"
    return joint_states_for_frame(frame, total_frames), "mock"


def force_wrench_for_frame(frame: int, total_frames: int) -> Dict[str, float]:
    tf = max(1, total_frames)
    f = frame % tf
    t = f * 0.12
    return {
        "fx": _round(math.sin(t) * 2.4, 4),
        "fy": _round(math.cos(t * 1.1) * 1.6, 4),
        "fz": _round(-4.5 + math.sin(t * 0.7) * 1.2, 4),
        "tx": _round(math.cos(t * 0.9) * 0.35, 4),
        "ty": _round(math.sin(t * 1.2) * 0.28, 4),
        "tz": _round(math.cos(t * 0.5) * 0.15, 4),
    }


def tactile_for_frame(frame: int, total_frames: int) -> Dict[str, Any]:
    tf = max(1, total_frames)
    f = frame % tf
    t = f * 0.15
    pads = []
    for i, name in enumerate(TACTILE_PAD_NAMES):
        pressure = max(0.0, math.sin(t + i * 0.8) * 0.55 + 0.35)
        pads.append({"name": name, "pressure": _round(pressure, 4)})
    return {"pads": pads}


def _normalize_force(raw: Any) -> Optional[Dict[str, float]]:
    if not isinstance(raw, dict):
        if isinstance(raw, (list, tuple)) and len(raw) >= 6:
            keys = ("fx", "fy", "fz", "tx", "ty", "tz")
            return {k: float(raw[i] or 0) for i, k in enumerate(keys)}
        return None
    out = {}
    for k in ("fx", "fy", "fz", "tx", "ty", "tz"):
        if k in raw:
            out[k] = float(raw.get(k) or 0)
        elif k[0] in raw:  # e.g. "f" misuse — ignore
            pass
    if len(out) == 6:
        return out
    # common aliases
    aliases = {
        "fx": ("force_x", "Fx", "x"),
        "fy": ("force_y", "Fy", "y"),
        "fz": ("force_z", "Fz", "z"),
        "tx": ("torque_x", "Tx"),
        "ty": ("torque_y", "Ty"),
        "tz": ("torque_z", "Tz"),
    }
    for k, alts in aliases.items():
        if k in out:
            continue
        for a in alts:
            if a in raw:
                out[k] = float(raw.get(a) or 0)
                break
        else:
            out[k] = 0.0
    return {k: float(out.get(k, 0) or 0) for k in ("fx", "fy", "fz", "tx", "ty", "tz")}


def _normalize_tactile(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        pads = raw.get("pads")
        if isinstance(pads, list) and pads:
            cleaned = []
            for i, p in enumerate(pads):
                if isinstance(p, dict):
                    cleaned.append(
                        {
                            "name": str(p.get("name") or f"pad{i}"),
                            "pressure": float(p.get("pressure", p.get("value", 0)) or 0),
                        }
                    )
                elif isinstance(p, (int, float)):
                    cleaned.append({"name": f"pad{i}", "pressure": float(p)})
            if cleaned:
                return {"pads": cleaned}
        # flat map name->pressure
        if raw and all(isinstance(v, (int, float)) for v in raw.values()):
            return {"pads": [{"name": str(k), "pressure": float(v)} for k, v in raw.items()]}
    if isinstance(raw, (list, tuple)) and raw:
        return {
            "pads": [
                {
                    "name": TACTILE_PAD_NAMES[i] if i < len(TACTILE_PAD_NAMES) else f"pad{i}",
                    "pressure": float(v if not isinstance(v, dict) else v.get("pressure", 0) or 0),
                }
                for i, v in enumerate(raw)
            ]
        }
    return None


def resolve_force_tactile_for_frame(
    episode: Dict[str, Any], frame: int, total_frames: int
) -> Tuple[Dict[str, float], str, Dict[str, Any], str]:
    by_idx = episode.get("_proprio_by_index")
    if not isinstance(by_idx, dict):
        by_idx = {}
    row = by_idx.get(frame) or by_idx.get(str(frame))
    force = None
    tactile = None
    if isinstance(row, dict):
        force = _normalize_force(row.get("force") or row.get("wrench") or row.get("ee_force"))
        tactile = _normalize_tactile(row.get("tactile") or row.get("touch"))
    force_src = "episode" if force else "mock"
    tactile_src = "episode" if tactile else "mock"
    if force is None:
        force = force_wrench_for_frame(frame, total_frames)
    if tactile is None:
        tactile = tactile_for_frame(frame, total_frames)
    return force, force_src, tactile, tactile_src


def get_vla_meta(task: Task, episode: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = task.data if isinstance(task.data, dict) else {}
    vla = data.get("embodied_vla") if isinstance(data.get("embodied_vla"), dict) else {}
    ep = episode or {}
    instruction = str(vla.get("instruction") if vla.get("instruction") is not None else ep.get("instruction") or "")
    success = str(vla.get("success") or ep.get("success") or "unknown")
    if success not in ("success", "fail", "unknown"):
        success = "unknown"
    segments = vla.get("segments") if isinstance(vla.get("segments"), list) else []
    if not segments and isinstance(ep.get("segments"), list):
        segments = ep.get("segments") or []
    grasps = vla.get("grasps") if isinstance(vla.get("grasps"), list) else []
    if not grasps and isinstance(ep.get("grasps"), list):
        grasps = ep.get("grasps") or []
    trajectory = vla.get("trajectory") if isinstance(vla.get("trajectory"), list) else []
    if not trajectory and isinstance(ep.get("trajectory"), list):
        trajectory = ep.get("trajectory") or []
    preferences = vla.get("preferences") if isinstance(vla.get("preferences"), list) else []
    if not preferences and isinstance(ep.get("preferences"), list):
        preferences = ep.get("preferences") or []
    return {
        "instruction": instruction,
        "success": success,
        "segments": segments,
        "grasps": grasps,
        "trajectory": trajectory,
        "preferences": preferences,
    }


def _clean_grasps(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for g in items:
        if not isinstance(g, dict):
            continue
        pos = g.get("position") if isinstance(g.get("position"), dict) else {}
        ori = g.get("orientation") if isinstance(g.get("orientation"), dict) else {}
        try:
            frame = int(g.get("frame", g.get("frame_index", 0)))
        except (TypeError, ValueError):
            frame = 0
        out.append(
            {
                "id": str(g.get("id") or f"grasp_{frame}_{len(out)}"),
                "frame": frame,
                "position": {
                    "x": float(pos.get("x", 0) or 0),
                    "y": float(pos.get("y", 0) or 0),
                    "z": float(pos.get("z", 0) or 0),
                },
                "orientation": {
                    "roll": float(ori.get("roll", 0) or 0),
                    "pitch": float(ori.get("pitch", 0) or 0),
                    "yaw": float(ori.get("yaw", 0) or 0),
                },
                "width": float(g.get("width", 0.08) or 0.08),
                "label": str(g.get("label") or "grasp"),
            }
        )
    return out


def _clean_trajectory(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for t in items:
        if not isinstance(t, dict):
            continue
        ee = t.get("ee") if isinstance(t.get("ee"), dict) else t.get("pose") if isinstance(t.get("pose"), dict) else {}
        try:
            frame = int(t.get("frame", t.get("frame_index", 0)))
        except (TypeError, ValueError):
            frame = 0
        out.append(
            {
                "frame": frame,
                "ee": {
                    "x": float(ee.get("x", 0) or 0),
                    "y": float(ee.get("y", 0) or 0),
                    "z": float(ee.get("z", 0) or 0),
                    "roll": float(ee.get("roll", 0) or 0),
                    "pitch": float(ee.get("pitch", 0) or 0),
                    "yaw": float(ee.get("yaw", 0) or 0),
                },
                "gripper": float(t.get("gripper", 0) or 0),
            }
        )
    out.sort(key=lambda r: r["frame"])
    return out


def _clean_preferences(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for p in items:
        if not isinstance(p, dict):
            continue
        winner = str(p.get("winner") or "tie")
        if winner not in ("a", "b", "tie"):
            winner = "tie"
        out.append(
            {
                "id": str(p.get("id") or f"pref_{len(out)}"),
                "prompt": str(p.get("prompt") or ""),
                "chosen": str(p.get("chosen") or p.get("response_a") or ""),
                "rejected": str(p.get("rejected") or p.get("response_b") or ""),
                "winner": winner,
            }
        )
    return out


def set_vla_meta(
    task: Task,
    *,
    instruction: Optional[str] = None,
    success: Optional[str] = None,
    segments: Optional[List[Dict[str, Any]]] = None,
    grasps: Optional[List[Dict[str, Any]]] = None,
    trajectory: Optional[List[Dict[str, Any]]] = None,
    preferences: Optional[List[Dict[str, Any]]] = None,
) -> None:
    data = dict(task.data) if isinstance(task.data, dict) else {}
    vla = dict(data.get("embodied_vla") or {}) if isinstance(data.get("embodied_vla"), dict) else {}
    if instruction is not None:
        vla["instruction"] = instruction
    if success is not None:
        vla["success"] = success if success in ("success", "fail", "unknown") else "unknown"
    if segments is not None:
        cleaned = []
        for s in segments:
            if not isinstance(s, dict):
                continue
            try:
                start = int(s.get("start_frame", 0))
                end = int(s.get("end_frame", start))
            except (TypeError, ValueError):
                continue
            if end < start:
                start, end = end, start
            cleaned.append(
                {
                    "id": str(s.get("id") or f"seg_{start}_{end}"),
                    "start_frame": start,
                    "end_frame": end,
                    "action_id": str(s.get("action_id") or "idle"),
                    "note": s.get("note") or "",
                }
            )
        vla["segments"] = cleaned
    if grasps is not None:
        vla["grasps"] = _clean_grasps(grasps)
    if trajectory is not None:
        vla["trajectory"] = _clean_trajectory(trajectory)
    if preferences is not None:
        vla["preferences"] = _clean_preferences(preferences)
    data["embodied_vla"] = vla
    task.data = data


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
    episode = get_episode_dict(task)
    vla = get_vla_meta(task, episode)
    return {
        "task_id": task.id,
        "task_ref": get_task_ref(task),
        "user_id": workspace.user_id,
        "action_labels": workspace.action_labels or list(DEFAULT_ACTION_LABELS),
        "frame_actions": frame_actions,
        "committed_frames": sorted(committed),
        "instruction": vla["instruction"],
        "success": vla["success"],
        "segments": vla["segments"],
        "grasps": vla.get("grasps") or [],
        "trajectory": vla.get("trajectory") or [],
        "preferences": vla.get("preferences") or [],
        "updated_at": workspace.updated_at,
    }


def apply_workspace_put(
    db: Session,
    task: Task,
    workspace: EmbodiedWorkspace,
    action_labels: List[Dict[str, str]],
    frame_actions: Dict[int, Dict[str, Any]],
    committed_frames: List[int],
    instruction: Optional[str] = None,
    success: Optional[str] = None,
    segments: Optional[List[Dict[str, Any]]] = None,
    grasps: Optional[List[Dict[str, Any]]] = None,
    trajectory: Optional[List[Dict[str, Any]]] = None,
    preferences: Optional[List[Dict[str, Any]]] = None,
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

    if any(
        x is not None
        for x in (instruction, success, segments, grasps, trajectory, preferences)
    ):
        set_vla_meta(
            task,
            instruction=instruction,
            success=success,
            segments=segments,
            grasps=grasps,
            trajectory=trajectory,
            preferences=preferences,
        )
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
    vla = get_vla_meta(task, episode)
    instruction = state.get("instruction") if state.get("instruction") is not None else vla["instruction"]
    success = state.get("success") or vla["success"]
    segments = state.get("segments") if state.get("segments") is not None else vla["segments"]
    grasps = state.get("grasps") if state.get("grasps") is not None else vla.get("grasps") or []
    trajectory = (
        state.get("trajectory") if state.get("trajectory") is not None else vla.get("trajectory") or []
    )
    preferences = (
        state.get("preferences")
        if state.get("preferences") is not None
        else vla.get("preferences") or []
    )

    frames_out: List[Dict[str, Any]] = []
    joints_source = "mock"
    force_source = "mock"
    tactile_source = "mock"
    for i in range(total_frames):
        ann = frame_actions.get(i) or frame_actions.get(str(i)) or {"action_id": "idle", "note": ""}
        action_id = ann.get("action_id", "idle")
        joints, src = resolve_joints_for_frame(episode, i, total_frames)
        force, fsrc, tactile, tsrc = resolve_force_tactile_for_frame(episode, i, total_frames)
        if src == "episode":
            joints_source = "episode"
        if fsrc == "episode":
            force_source = "episode"
        if tsrc == "episode":
            tactile_source = "episode"
        frames_out.append(
            {
                "index": i,
                "timestamp_ms": round(
                    (i / max(1, total_frames - 1)) * clip_duration_sec * 1000
                ),
                "action": {"id": action_id, "label": label_text(labels, action_id)},
                "note": ann.get("note") or "",
                "annotation_saved": i in committed,
                "joints_source": src,
                "joints": [
                    {
                        "name": j["name"],
                        "position_rad": j["position_rad"],
                        "position_deg": _round((j["position_rad"] * 180) / math.pi, 2),
                        "torque_nm": j["torque_nm"],
                    }
                    for j in joints
                ],
                "force_source": fsrc,
                "force": force,
                "tactile_source": tsrc,
                "tactile": tactile,
            }
        )

    streams = episode.get("streams") or []
    return {
        "schema": "dasshine.embodied_sequence.v7",
        "task_id": get_task_ref(task),
        "task_db_id": task.id,
        "case_id": episode.get("case_id"),
        "project": episode.get("project_name"),
        "instruction": instruction or "",
        "success": success or "unknown",
        "segments": segments or [],
        "grasps": grasps or [],
        "trajectory": trajectory or [],
        "preferences": preferences or [],
        "joints_source": joints_source,
        "force_source": force_source,
        "tactile_source": tactile_source,
        "clip_duration_sec": clip_duration_sec,
        "fps": fps,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "action_labels": labels,
        "committed_frames": sorted(committed),
        "streams": [
            {
                "id": s.get("id"),
                "label": s.get("label"),
                "src": s.get("src"),
                **({"intrinsics": s.get("intrinsics")} if s.get("intrinsics") else {}),
                **({"extrinsics": s.get("extrinsics")} if s.get("extrinsics") else {}),
            }
            for s in streams
            if isinstance(s, dict)
        ],
        "attribution": episode.get("attribution"),
        "frames": frames_out,
    }


def build_torque_csv(state: Dict[str, Any], episode: Dict[str, Any]) -> str:
    total_frames = int(episode["total_frames"])
    clip_duration_sec = float(episode["clip_duration_sec"])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["frame_index", "timestamp_ms", "joint", "torque_nm", "position_rad", "joints_source"])
    for i in range(total_frames):
        ts = round((i / max(1, total_frames - 1)) * clip_duration_sec * 1000)
        joints, src = resolve_joints_for_frame(episode, i, total_frames)
        for j in joints:
            w.writerow([i, ts, j["name"], j["torque_nm"], j["position_rad"], src])
    return buf.getvalue()


def build_lerobot_jsonl(
    task: Task,
    workspace: EmbodiedWorkspace,
    state: Dict[str, Any],
    episode: Dict[str, Any],
) -> str:
    doc = build_export_json(task, workspace, state, episode)
    lines = []
    for fr in doc.get("frames") or []:
        joints = fr.get("joints") or []
        lines.append(
            json.dumps(
                {
                    "episode_index": doc.get("task_db_id"),
                    "frame_index": fr.get("index"),
                    "timestamp": (fr.get("timestamp_ms") or 0) / 1000.0,
                    "task": doc.get("instruction") or doc.get("project"),
                    "instruction": doc.get("instruction") or "",
                    "success": doc.get("success"),
                    "action": (fr.get("action") or {}).get("id"),
                    "action_label": (fr.get("action") or {}).get("label"),
                    "observation.state": [j.get("position_rad") for j in joints],
                    "observation.torque": [j.get("torque_nm") for j in joints],
                    "joints_source": fr.get("joints_source"),
                    "note": fr.get("note") or "",
                    "segments": doc.get("segments") or [],
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines) + ("\n" if lines else "")


def build_lerobot_dataset_zip(docs: List[Dict[str, Any]], project_name: str) -> bytes:
    """
    LeRobot-inspired dataset layout v2：
    meta/info.json
    meta/episodes.jsonl
    data/chunk-000/episode_XXXXXX.parquet (+ .jsonl 兼容)
    videos_urls/… 或 videos/chunk-000/…（本地文件可打包）
    """
    import pandas as pd

    files: Dict[str, bytes] = {}
    episodes_meta = []
    total_frames = 0
    bundled_videos = 0
    for i, doc in enumerate(docs):
        ep_idx = int(doc.get("task_db_id") or i)
        ep_name = f"episode_{ep_idx:06d}"
        frames = doc.get("frames") or []
        n = len(frames)
        total_frames += n
        episodes_meta.append(
            {
                "episode_index": ep_idx,
                "length": n,
                "tasks": [doc.get("instruction") or project_name],
                "success": doc.get("success"),
                "grasps": doc.get("grasps") or [],
                "trajectory": doc.get("trajectory") or [],
                "segments": doc.get("segments") or [],
                "preferences": doc.get("preferences") or [],
            }
        )
        rows = []
        lines = []
        for fr in frames:
            if not isinstance(fr, dict):
                continue
            joints = fr.get("joints") or []
            force = fr.get("force") if isinstance(fr.get("force"), dict) else {}
            tactile = fr.get("tactile") if isinstance(fr.get("tactile"), dict) else {}
            pads = tactile.get("pads") if isinstance(tactile.get("pads"), list) else []
            row = {
                "episode_index": ep_idx,
                "frame_index": fr.get("index"),
                "timestamp": (fr.get("timestamp_ms") or 0) / 1000.0,
                "task": doc.get("instruction") or project_name,
                "action": (fr.get("action") or {}).get("id"),
                "observation.state": [j.get("position_rad") for j in joints if isinstance(j, dict)],
                "observation.torque": [j.get("torque_nm") for j in joints if isinstance(j, dict)],
                "observation.force": [
                    force.get("fx", 0),
                    force.get("fy", 0),
                    force.get("fz", 0),
                    force.get("tx", 0),
                    force.get("ty", 0),
                    force.get("tz", 0),
                ],
                "observation.tactile": [
                    float(p.get("pressure", 0) or 0) for p in pads if isinstance(p, dict)
                ],
                "joints_source": fr.get("joints_source"),
                "force_source": fr.get("force_source"),
                "tactile_source": fr.get("tactile_source"),
            }
            rows.append(row)
            lines.append(json.dumps(row, ensure_ascii=False))
        files[f"data/chunk-000/{ep_name}.jsonl"] = (
            "\n".join(lines) + ("\n" if lines else "")
        ).encode("utf-8")
        if rows:
            df = pd.DataFrame(rows)
            pq_buf = io.BytesIO()
            df.to_parquet(pq_buf, index=False)
            files[f"data/chunk-000/{ep_name}.parquet"] = pq_buf.getvalue()
        for s in doc.get("streams") or []:
            if not isinstance(s, dict):
                continue
            cam = str(s.get("id") or "cam")
            src = str(s.get("src") or "")
            files[f"videos_urls/{ep_name}/{cam}.txt"] = src.encode("utf-8")
            local = _maybe_local_video_path(src)
            if local is not None:
                dest = f"videos/chunk-000/{ep_name}/{cam}{local.suffix or '.mp4'}"
                try:
                    files[dest] = local.read_bytes()
                    bundled_videos += 1
                except OSError:
                    pass
            elif bundled_videos < _video_download_stream_budget():
                downloaded = _download_remote_video(src)
                if downloaded is not None:
                    data, ext = downloaded
                    files[f"videos/chunk-000/{ep_name}/{cam}{ext}"] = data
                    bundled_videos += 1

    info = {
        "codebase_version": "v2.1",
        "robot_type": "dasshine_embodied",
        "total_episodes": len(docs),
        "total_frames": total_frames,
        "fps": (docs[0].get("fps") if docs else 12) or 12,
        "chunks_size": 1000,
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "data_path_jsonl": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.jsonl",
        "video_path": "videos/chunk-000/episode_{episode_index:06d}/{video_key}.mp4",
        "video_url_path": "videos_urls/episode_{episode_index:06d}/{video_key}.txt",
        "features": {
            "observation.state": {"dtype": "float32", "shape": ["n_joints"]},
            "observation.force": {"dtype": "float32", "shape": [6]},
            "observation.tactile": {"dtype": "float32", "shape": ["n_pads"]},
            "action": {"dtype": "string"},
            "timestamp": {"dtype": "float32", "shape": [1]},
        },
        "dasshine": {
            "schema": "dasshine.lerobot_dataset.v3",
            "project": project_name,
            "bundled_videos": bundled_videos,
            "note": "Parquet primary; remote http(s) videos downloaded when under size/timeout limits",
        },
    }
    files["meta/info.json"] = json.dumps(info, ensure_ascii=False, indent=2).encode("utf-8")
    files["meta/episodes.jsonl"] = (
        "\n".join(json.dumps(e, ensure_ascii=False) for e in episodes_meta)
        + ("\n" if episodes_meta else "")
    ).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def _maybe_local_video_path(src: str) -> Optional[Path]:
    if not src:
        return None
    parsed = urlparse(src)
    if parsed.scheme in ("http", "https", "blob", "data"):
        return None
    path_str = parsed.path if parsed.scheme == "file" else src
    if path_str.startswith("file://"):
        path_str = path_str[7:]
    p = Path(path_str)
    if p.is_file():
        return p
    return None


def _video_download_stream_budget() -> int:
    try:
        from app.core.config import settings

        if not settings.EMBODIED_VIDEO_DOWNLOAD:
            return 0
        return max(0, int(settings.EMBODIED_VIDEO_DOWNLOAD_MAX_STREAMS))
    except Exception:
        return 8


def _download_remote_video(src: str) -> Optional[Tuple[bytes, str]]:
    """下载远端视频；超限或失败返回 None。"""
    if not src:
        return None
    parsed = urlparse(src)
    if parsed.scheme not in ("http", "https"):
        return None
    try:
        from app.core.config import settings

        if not settings.EMBODIED_VIDEO_DOWNLOAD:
            return None
        max_bytes = int(float(settings.EMBODIED_VIDEO_DOWNLOAD_MAX_MB) * 1024 * 1024)
        timeout = float(settings.EMBODIED_VIDEO_DOWNLOAD_TIMEOUT)
    except Exception:
        max_bytes = 32 * 1024 * 1024
        timeout = 15.0

    try:
        import httpx

        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            with client.stream("GET", src) as resp:
                if resp.status_code >= 400:
                    return None
                ctype = (resp.headers.get("content-type") or "").lower()
                chunks: List[bytes] = []
                total = 0
                for chunk in resp.iter_bytes(65536):
                    total += len(chunk)
                    if total > max_bytes:
                        return None
                    chunks.append(chunk)
                data = b"".join(chunks)
        path = parsed.path or ""
        ext = Path(path).suffix.lower()
        if ext not in (".mp4", ".webm", ".mov", ".mkv", ".avi"):
            if "webm" in ctype:
                ext = ".webm"
            else:
                ext = ".mp4"
        return data, ext
    except Exception:
        return None


def build_rlds_dataset_zip(docs: List[Dict[str, Any]], project_name: str) -> bytes:
    """
    RLDS-lite（无 TensorFlow）：
    dataset_info.json
    episodes/episode_XXXXXX/meta.json
    episodes/episode_XXXXXX/steps.jsonl
    """
    files: Dict[str, bytes] = {}
    episode_ids = []
    total_steps = 0
    for i, doc in enumerate(docs):
        ep_idx = int(doc.get("task_db_id") or i)
        ep_name = f"episode_{ep_idx:06d}"
        episode_ids.append(ep_name)
        frames = doc.get("frames") or []
        total_steps += len(frames)
        instruction = str(doc.get("instruction") or project_name)
        success = str(doc.get("success") or "unknown")
        reward_last = 1.0 if success == "success" else (0.0 if success == "fail" else 0.0)
        steps = []
        n = len(frames)
        for fi, fr in enumerate(frames):
            if not isinstance(fr, dict):
                continue
            joints = fr.get("joints") or []
            force = fr.get("force") if isinstance(fr.get("force"), dict) else {}
            tactile = fr.get("tactile") if isinstance(fr.get("tactile"), dict) else {}
            pads = tactile.get("pads") if isinstance(tactile.get("pads"), list) else []
            action = fr.get("action") if isinstance(fr.get("action"), dict) else {}
            step = {
                "observation": {
                    "state": [float(j.get("position_rad") or 0) for j in joints if isinstance(j, dict)],
                    "torque": [float(j.get("torque_nm") or 0) for j in joints if isinstance(j, dict)],
                    "force": [
                        float(force.get("fx", 0) or 0),
                        float(force.get("fy", 0) or 0),
                        float(force.get("fz", 0) or 0),
                        float(force.get("tx", 0) or 0),
                        float(force.get("ty", 0) or 0),
                        float(force.get("tz", 0) or 0),
                    ],
                    "tactile": [
                        float(p.get("pressure", 0) or 0) for p in pads if isinstance(p, dict)
                    ],
                },
                "action": {
                    "label": action.get("id") or "idle",
                    "label_text": action.get("label") or action.get("id") or "idle",
                },
                "reward": reward_last if fi == n - 1 else 0.0,
                "discount": 1.0,
                "is_first": fi == 0,
                "is_last": fi == n - 1,
                "is_terminal": fi == n - 1,
                "language_instruction": instruction,
                "timestamp": (fr.get("timestamp_ms") or 0) / 1000.0,
            }
            steps.append(step)
        files[f"episodes/{ep_name}/steps.jsonl"] = (
            "\n".join(json.dumps(s, ensure_ascii=False) for s in steps)
            + ("\n" if steps else "")
        ).encode("utf-8")
        meta = {
            "episode_id": ep_name,
            "episode_index": ep_idx,
            "num_steps": len(steps),
            "success": success,
            "language_instruction": instruction,
            "segments": doc.get("segments") or [],
            "grasps": doc.get("grasps") or [],
            "trajectory": doc.get("trajectory") or [],
            "preferences": doc.get("preferences") or [],
            "streams": doc.get("streams") or [],
        }
        files[f"episodes/{ep_name}/meta.json"] = json.dumps(meta, ensure_ascii=False, indent=2).encode(
            "utf-8"
        )

    info = {
        "name": project_name or "dasshine_embodied",
        "schema": "dasshine.rlds_lite.v1",
        "citation": "RLDS-compatible step dicts without TensorFlow dependency",
        "total_episodes": len(docs),
        "total_steps": total_steps,
        "episodes": episode_ids,
        "features": {
            "observation.state": {"dtype": "float32"},
            "observation.force": {"dtype": "float32", "shape": [6]},
            "action.label": {"dtype": "string"},
            "language_instruction": {"dtype": "string"},
            "reward": {"dtype": "float32"},
            "is_first": {"dtype": "bool"},
            "is_last": {"dtype": "bool"},
        },
    }
    files["dataset_info.json"] = json.dumps(info, ensure_ascii=False, indent=2).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def build_tfrecord_zip(docs: List[Dict[str, Any]], project_name: str) -> bytes:
    """
    TFRecord ZIP（无 TensorFlow）：
    dataset_info.json
    episodes/episode_XXXXXX.tfrecord
    """
    from app.services.exporters.tfrecord_lite import example_from_step, write_tfrecord_bytes

    files: Dict[str, bytes] = {}
    episode_ids = []
    total_steps = 0
    for i, doc in enumerate(docs):
        ep_idx = int(doc.get("task_db_id") or i)
        ep_name = f"episode_{ep_idx:06d}"
        episode_ids.append(ep_name)
        frames = doc.get("frames") or []
        instruction = str(doc.get("instruction") or project_name)
        success = str(doc.get("success") or "unknown")
        reward_last = 1.0 if success == "success" else 0.0
        examples = []
        n = len(frames)
        total_steps += n
        for fi, fr in enumerate(frames):
            if not isinstance(fr, dict):
                continue
            joints = fr.get("joints") or []
            force = fr.get("force") if isinstance(fr.get("force"), dict) else {}
            tactile = fr.get("tactile") if isinstance(fr.get("tactile"), dict) else {}
            pads = tactile.get("pads") if isinstance(tactile.get("pads"), list) else []
            action = fr.get("action") if isinstance(fr.get("action"), dict) else {}
            step = {
                "observation": {
                    "state": [float(j.get("position_rad") or 0) for j in joints if isinstance(j, dict)],
                    "torque": [float(j.get("torque_nm") or 0) for j in joints if isinstance(j, dict)],
                    "force": [
                        float(force.get("fx", 0) or 0),
                        float(force.get("fy", 0) or 0),
                        float(force.get("fz", 0) or 0),
                        float(force.get("tx", 0) or 0),
                        float(force.get("ty", 0) or 0),
                        float(force.get("tz", 0) or 0),
                    ],
                    "tactile": [
                        float(p.get("pressure", 0) or 0) for p in pads if isinstance(p, dict)
                    ],
                },
                "action": {
                    "label": action.get("id") or "idle",
                    "label_text": action.get("label") or action.get("id") or "idle",
                },
                "reward": reward_last if fi == n - 1 else 0.0,
                "discount": 1.0,
                "is_first": fi == 0,
                "is_last": fi == n - 1,
                "language_instruction": instruction,
                "timestamp": (fr.get("timestamp_ms") or 0) / 1000.0,
            }
            examples.append(example_from_step(step, episode_id=ep_name, step_index=fi))
        files[f"episodes/{ep_name}.tfrecord"] = write_tfrecord_bytes(examples)
        meta = {
            "episode_id": ep_name,
            "num_steps": n,
            "success": success,
            "language_instruction": instruction,
            "streams": doc.get("streams") or [],
            "segments": doc.get("segments") or [],
            "grasps": doc.get("grasps") or [],
        }
        files[f"episodes/{ep_name}.meta.json"] = json.dumps(meta, ensure_ascii=False, indent=2).encode(
            "utf-8"
        )

    info = {
        "name": project_name or "dasshine_embodied",
        "schema": "dasshine.tfrecord.v1",
        "citation": "tf.Example TFRecord without TensorFlow dependency",
        "total_episodes": len(docs),
        "total_steps": total_steps,
        "episodes": episode_ids,
    }
    files["dataset_info.json"] = json.dumps(info, ensure_ascii=False, indent=2).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def build_hdf5(
    task: Task,
    workspace: EmbodiedWorkspace,
    state: Dict[str, Any],
    episode: Dict[str, Any],
) -> bytes:
    """单 episode HDF5：observations/qpos|force|tactile + attrs。"""
    import h5py
    import numpy as np

    doc = build_export_json(task, workspace, state, episode)
    frames = doc.get("frames") or []
    qpos, force, tactile, actions = [], [], [], []
    for fr in frames:
        joints = fr.get("joints") or []
        qpos.append([float(j.get("position_rad") or 0) for j in joints if isinstance(j, dict)])
        f = fr.get("force") if isinstance(fr.get("force"), dict) else {}
        force.append(
            [
                float(f.get("fx", 0) or 0),
                float(f.get("fy", 0) or 0),
                float(f.get("fz", 0) or 0),
                float(f.get("tx", 0) or 0),
                float(f.get("ty", 0) or 0),
                float(f.get("tz", 0) or 0),
            ]
        )
        pads = ((fr.get("tactile") or {}).get("pads") if isinstance(fr.get("tactile"), dict) else []) or []
        tactile.append([float(p.get("pressure", 0) or 0) for p in pads if isinstance(p, dict)])
        actions.append(str((fr.get("action") or {}).get("id") or "idle"))

    buf = io.BytesIO()
    with h5py.File(buf, "w") as hf:
        hf.attrs["schema"] = "dasshine.embodied_hdf5.v1"
        hf.attrs["instruction"] = str(doc.get("instruction") or "")
        hf.attrs["success"] = str(doc.get("success") or "unknown")
        hf.attrs["task_id"] = str(doc.get("task_id") or "")
        hf.attrs["task_db_id"] = int(doc.get("task_db_id") or 0)
        hf.attrs["fps"] = int(doc.get("fps") or 12)
        hf.attrs["joints_source"] = str(doc.get("joints_source") or "mock")
        hf.attrs["force_source"] = str(doc.get("force_source") or "mock")
        hf.attrs["tactile_source"] = str(doc.get("tactile_source") or "mock")
        meta = hf.create_group("meta")
        meta.create_dataset(
            "segments_json",
            data=np.bytes_(json.dumps(doc.get("segments") or [], ensure_ascii=False)),
        )
        meta.create_dataset(
            "preferences_json",
            data=np.bytes_(json.dumps(doc.get("preferences") or [], ensure_ascii=False)),
        )
        meta.create_dataset(
            "grasps_json",
            data=np.bytes_(json.dumps(doc.get("grasps") or [], ensure_ascii=False)),
        )
        if qpos:
            # pad jagged rows
            max_j = max(len(r) for r in qpos)
            qpos_arr = np.zeros((len(qpos), max_j), dtype=np.float32)
            for i, r in enumerate(qpos):
                qpos_arr[i, : len(r)] = r
            hf.create_dataset("observations/qpos", data=qpos_arr)
        if force:
            hf.create_dataset("observations/force", data=np.asarray(force, dtype=np.float32))
        if tactile:
            max_p = max((len(r) for r in tactile), default=0)
            tac_arr = np.zeros((len(tactile), max(1, max_p)), dtype=np.float32)
            for i, r in enumerate(tactile):
                tac_arr[i, : len(r)] = r
            hf.create_dataset("observations/tactile", data=tac_arr)
        dt = h5py.string_dtype(encoding="utf-8")
        hf.create_dataset("actions/label", data=np.asarray(actions, dtype=dt))
    return buf.getvalue()


def apply_policy_prelabel(
    db: Session,
    task: Task,
    workspace: EmbodiedWorkspace,
    model: str = "auto",
) -> Dict[str, Any]:
    """
    策略预标注：model=embodied_policy_http|embodied_policy_demo|auto。
    auto：配置了 EMBODIED_POLICY_HTTP_ENDPOINT 则先试 HTTP，失败回退 demo。
    """
    episode = get_episode_dict(task)
    state = workspace_to_state(db, task, workspace)
    want = (model or "auto").strip().lower()
    if want in ("auto", "embodied_policy_http", "http"):
        http_result = _try_policy_http(task, episode, state)
        if http_result is not None:
            set_vla_meta(
                task,
                instruction=http_result.get("instruction"),
                success=http_result.get("success"),
                segments=http_result.get("segments"),
                grasps=http_result.get("grasps"),
                trajectory=http_result.get("trajectory"),
                preferences=http_result.get("preferences"),
            )
            db.commit()
            db.refresh(task)
            return {**http_result, "model": "embodied_policy_http"}
        if want in ("embodied_policy_http", "http"):
            # 强制 HTTP 但失败 → 仍回退 demo，并标记
            demo = _demo_policy_prelabel(task, episode, state)
            demo["model"] = "embodied_policy_demo"
            demo["http_fallback"] = True
            set_vla_meta(
                task,
                instruction=demo.get("instruction"),
                success=demo.get("success"),
                segments=demo.get("segments"),
                grasps=demo.get("grasps"),
                trajectory=demo.get("trajectory"),
                preferences=demo.get("preferences"),
            )
            db.commit()
            db.refresh(task)
            return demo

    demo = _demo_policy_prelabel(task, episode, state)
    set_vla_meta(
        task,
        instruction=demo.get("instruction"),
        success=demo.get("success"),
        segments=demo.get("segments"),
        grasps=demo.get("grasps"),
        trajectory=demo.get("trajectory"),
        preferences=demo.get("preferences"),
    )
    db.commit()
    db.refresh(task)
    return {**demo, "model": "embodied_policy_demo"}


def _try_policy_http(
    task: Task, episode: Dict[str, Any], state: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    try:
        from app.core.config import settings

        endpoint = (settings.EMBODIED_POLICY_HTTP_ENDPOINT or "").strip()
        if not endpoint:
            return None
        timeout = float(settings.EMBODIED_POLICY_HTTP_TIMEOUT or 30)
        headers = {"Content-Type": "application/json"}
        if settings.EMBODIED_POLICY_HTTP_API_KEY:
            headers["Authorization"] = f"Bearer {settings.EMBODIED_POLICY_HTTP_API_KEY}"
    except Exception:
        return None

    try:
        from app.services.embodied_policy_weights import get_active_weight

        active_weight = get_active_weight()
    except Exception:
        active_weight = None

    payload = {
        "task_id": task.id,
        "task_ref": get_task_ref(task),
        "active_weight": active_weight,
        "episode": {
            "case_id": episode.get("case_id"),
            "project_name": episode.get("project_name"),
            "fps": episode.get("fps"),
            "total_frames": episode.get("total_frames"),
            "instruction": episode.get("instruction"),
            "streams": [
                {"id": s.get("id"), "label": s.get("label"), "src": s.get("src")}
                for s in (episode.get("streams") or [])
                if isinstance(s, dict)
            ],
        },
        "workspace": {
            "instruction": state.get("instruction"),
            "success": state.get("success"),
            "segments": state.get("segments"),
            "grasps": state.get("grasps"),
            "trajectory": state.get("trajectory"),
            "preferences": state.get("preferences"),
            "frame_actions": state.get("frame_actions"),
            "action_labels": state.get("action_labels"),
        },
    }
    try:
        import httpx

        with httpx.Client(timeout=timeout) as client:
            r = client.post(endpoint, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    # allow nested {result: {...}}
    body = data.get("result") if isinstance(data.get("result"), dict) else data
    out: Dict[str, Any] = {}
    if body.get("instruction") is not None:
        out["instruction"] = str(body.get("instruction") or "")
    if body.get("success") is not None:
        s = str(body.get("success") or "unknown")
        out["success"] = s if s in ("success", "fail", "unknown") else "unknown"
    if isinstance(body.get("segments"), list):
        out["segments"] = body["segments"]
    if isinstance(body.get("grasps"), list):
        out["grasps"] = body["grasps"]
    if isinstance(body.get("trajectory"), list):
        out["trajectory"] = body["trajectory"]
    if isinstance(body.get("preferences"), list):
        out["preferences"] = body["preferences"]
    if not out:
        return None
    # fill gaps from current vla so set_vla_meta partial updates work
    vla = get_vla_meta(task, episode)
    out.setdefault("instruction", vla.get("instruction") or "")
    out.setdefault("success", vla.get("success") or "unknown")
    out.setdefault("segments", vla.get("segments") or [])
    out.setdefault("grasps", vla.get("grasps") or [])
    out.setdefault("trajectory", vla.get("trajectory") or [])
    out.setdefault("preferences", vla.get("preferences") or [])
    return out


def _demo_policy_prelabel(
    task: Task, episode: Dict[str, Any], state: Dict[str, Any]
) -> Dict[str, Any]:
    """启发式 demo：不覆盖已有非空 instruction；segments/grasps 仅在为空时填充。"""
    vla = get_vla_meta(task, episode)
    total = int(episode.get("total_frames") or 24)
    labels = state.get("action_labels") or list(DEFAULT_ACTION_LABELS)
    label_ids = [str(l.get("id")) for l in labels if isinstance(l, dict) and l.get("id")]

    instruction = (vla.get("instruction") or "").strip()
    if not instruction:
        instruction = str(
            episode.get("instruction")
            or episode.get("project_name")
            or f"complete task {episode.get('case_id') or task.id}"
        )

    segments = list(vla.get("segments") or [])
    if not segments:
        frame_actions = state.get("frame_actions") or {}
        runs: List[Dict[str, Any]] = []
        cur_id = None
        start = 0
        for i in range(total):
            ann = frame_actions.get(i) or frame_actions.get(str(i)) or {}
            aid = str(ann.get("action_id") or "idle")
            if cur_id is None:
                cur_id = aid
                start = i
            elif aid != cur_id:
                if cur_id != "idle":
                    runs.append(
                        {
                            "id": f"seg_{start}_{i - 1}",
                            "start_frame": start,
                            "end_frame": i - 1,
                            "action_id": cur_id,
                            "note": "prelabel",
                        }
                    )
                cur_id = aid
                start = i
        if cur_id and cur_id != "idle":
            runs.append(
                {
                    "id": f"seg_{start}_{total - 1}",
                    "start_frame": start,
                    "end_frame": total - 1,
                    "action_id": cur_id,
                    "note": "prelabel",
                }
            )
        if runs:
            segments = runs
        else:
            third = max(1, total // 3)
            seq = [x for x in ("reach", "grasp", "place") if x in label_ids] or label_ids[:3] or ["idle"]
            segments = []
            for i, aid in enumerate(seq[:3]):
                s = i * third
                e = min(total - 1, (i + 1) * third - 1) if i < 2 else total - 1
                segments.append(
                    {
                        "id": f"seg_{s}_{e}",
                        "start_frame": s,
                        "end_frame": max(s, e),
                        "action_id": aid,
                        "note": "prelabel",
                    }
                )

    grasps = list(vla.get("grasps") or [])
    if not grasps:
        mid = total // 2
        grasps = [
            {
                "id": f"grasp_prelabel_{mid}",
                "frame": mid,
                "position": {"x": 0.35, "y": 0.0, "z": 0.12},
                "orientation": {"roll": 0.0, "pitch": 1.57, "yaw": 0.0},
                "width": 0.06,
                "label": "grasp",
            }
        ]

    return {
        "instruction": instruction,
        "success": vla.get("success") or "unknown",
        "segments": segments,
        "grasps": grasps,
        "trajectory": vla.get("trajectory") or [],
        "preferences": vla.get("preferences") or [],
    }


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

    if not task.started_at:
        task.started_at = datetime.now(timezone.utc)
    from app.services.task_completion import after_annotation_submit

    after_annotation_submit(db, task, user.id, payload, work_time=work_time)
    db.commit()
    db.refresh(ann)
    return ann
