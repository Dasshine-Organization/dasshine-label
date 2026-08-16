"""
具身序列标注 API
"""

from __future__ import annotations

import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.embodied_schemas import (
    ActionLabelSchema,
    ActionSegmentSchema,
    EmbodiedEpisodeSchema,
    EmbodiedExportRequest,
    EmbodiedPrelabelBody,
    EmbodiedSubmitBody,
    EmbodiedWorkspacePutBody,
    EmbodiedWorkspaceStateSchema,
    FramePatchBody,
    GraspPoseSchema,
    PreferencePairSchema,
    TrajectoryPointSchema,
)
from app.services.embodied_service import (
    apply_policy_prelabel,
    apply_workspace_put,
    build_export_json,
    build_hdf5,
    build_lerobot_dataset_zip,
    build_lerobot_jsonl,
    build_rlds_dataset_zip,
    build_torque_csv,
    get_episode_dict,
    get_or_create_workspace,
    get_task_ref,
    get_vla_meta,
    patch_frame,
    resolve_task,
    submit_annotation,
    workspace_to_state,
)
from app.services.project_acl import can_access_task_workspace

router = APIRouter(prefix="/embodied", tags=["具身标注"])


def _episode_to_api(ep: Dict[str, Any], task=None) -> EmbodiedEpisodeSchema:
    streams = []
    for s in ep.get("streams") or []:
        streams.append(
            {
                "id": s["id"],
                "label": s["label"],
                "src": s["src"],
                "fallback_src": s.get("fallback_src"),
                "object_position": s.get("object_position"),
                "scale": s.get("scale"),
            }
        )
    attr = ep.get("attribution") or {}
    vla = get_vla_meta(task, ep) if task is not None else {
        "instruction": ep.get("instruction") or "",
        "success": ep.get("success") or "unknown",
    }
    return EmbodiedEpisodeSchema(
        case_id=str(ep.get("case_id") or "custom"),
        project_name=ep.get("project_name") or "",
        clip_duration_sec=float(ep.get("clip_duration_sec") or 0),
        fps=int(ep.get("fps") or 12),
        total_frames=int(ep.get("total_frames") or 0),
        streams=streams,
        attribution={
            "title": attr.get("title", ""),
            "detail_url": attr.get("detail_url", ""),
            "note": attr.get("note", ""),
        },
        instruction=str(vla.get("instruction") or ""),
        success=vla.get("success") if vla.get("success") in ("success", "fail", "unknown") else "unknown",
        has_proprioception=bool(ep.get("has_proprioception")),
    )


def _state_to_api(state: Dict[str, Any]) -> EmbodiedWorkspaceStateSchema:
    segs = []
    for s in state.get("segments") or []:
        if isinstance(s, dict):
            segs.append(ActionSegmentSchema(**{
                "id": str(s.get("id") or f"seg_{s.get('start_frame')}_{s.get('end_frame')}"),
                "start_frame": int(s.get("start_frame", 0)),
                "end_frame": int(s.get("end_frame", 0)),
                "action_id": str(s.get("action_id") or "idle"),
                "note": s.get("note"),
            }))
    grasps = []
    for g in state.get("grasps") or []:
        if isinstance(g, dict):
            grasps.append(GraspPoseSchema(**{
                "id": str(g.get("id") or "g"),
                "frame": int(g.get("frame", 0)),
                "position": g.get("position") or {"x": 0, "y": 0, "z": 0},
                "orientation": g.get("orientation") or {"roll": 0, "pitch": 0, "yaw": 0},
                "width": float(g.get("width", 0.08) or 0.08),
                "label": str(g.get("label") or "grasp"),
            }))
    traj = []
    for t in state.get("trajectory") or []:
        if isinstance(t, dict):
            traj.append(TrajectoryPointSchema(**{
                "frame": int(t.get("frame", 0)),
                "ee": t.get("ee") or {"x": 0, "y": 0, "z": 0, "roll": 0, "pitch": 0, "yaw": 0},
                "gripper": float(t.get("gripper", 0) or 0),
            }))
    prefs = []
    for p in state.get("preferences") or []:
        if isinstance(p, dict):
            winner = p.get("winner") or "tie"
            if winner not in ("a", "b", "tie"):
                winner = "tie"
            prefs.append(
                PreferencePairSchema(
                    id=str(p.get("id") or "pref"),
                    prompt=str(p.get("prompt") or ""),
                    chosen=str(p.get("chosen") or ""),
                    rejected=str(p.get("rejected") or ""),
                    winner=winner,
                )
            )
    success = state.get("success") or "unknown"
    if success not in ("success", "fail", "unknown"):
        success = "unknown"
    return EmbodiedWorkspaceStateSchema(
        task_id=state["task_id"],
        task_ref=state["task_ref"],
        user_id=state["user_id"],
        action_labels=[ActionLabelSchema(**x) for x in state["action_labels"]],
        frame_actions={
            int(k): {"action_id": v["action_id"], "note": v.get("note")}
            for k, v in state["frame_actions"].items()
        },
        committed_frames=state["committed_frames"],
        instruction=str(state.get("instruction") or ""),
        success=success,
        segments=segs,
        grasps=grasps,
        trajectory=traj,
        preferences=prefs,
        updated_at=state.get("updated_at"),
    )


def _require_task(db: Session, task_ref: str, user: User):
    task = resolve_task(db, task_ref)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, user):
        raise HTTPException(status_code=403, detail="无权访问该任务")
    return task


@router.get("/tasks/{task_ref}/episode", response_model=EmbodiedEpisodeSchema)
def get_episode(
    task_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _require_task(db, task_ref, current_user)
    return _episode_to_api(get_episode_dict(task), task)


@router.get("/tasks/{task_ref}/workspace", response_model=EmbodiedWorkspaceStateSchema)
def get_workspace(
    task_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _require_task(db, task_ref, current_user)
    ws = get_or_create_workspace(db, task, current_user)
    return _state_to_api(workspace_to_state(db, task, ws))


@router.put("/tasks/{task_ref}/workspace", response_model=EmbodiedWorkspaceStateSchema)
def put_workspace(
    task_ref: str,
    body: EmbodiedWorkspacePutBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _require_task(db, task_ref, current_user)
    ws = get_or_create_workspace(db, task, current_user)
    try:
        apply_workspace_put(
            db,
            task,
            ws,
            [x.model_dump() for x in body.action_labels],
            {int(k): v.model_dump() for k, v in body.frame_actions.items()},
            body.committed_frames,
            instruction=body.instruction,
            success=body.success,
            segments=[s.model_dump() for s in body.segments] if body.segments is not None else None,
            grasps=[g.model_dump() for g in body.grasps] if body.grasps is not None else None,
            trajectory=[t.model_dump() for t in body.trajectory] if body.trajectory is not None else None,
            preferences=[p.model_dump() for p in body.preferences] if body.preferences is not None else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.refresh(ws)
    db.refresh(task)
    return _state_to_api(workspace_to_state(db, task, ws))


@router.patch("/tasks/{task_ref}/frames/{frame_index}")
def patch_frame_annotation(
    task_ref: str,
    frame_index: int,
    body: FramePatchBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _require_task(db, task_ref, current_user)
    ws = get_or_create_workspace(db, task, current_user)
    fr = patch_frame(
        db, ws, frame_index, body.action_id, body.note, body.commit
    )
    return {
        "frame_index": fr.frame_index,
        "action_id": fr.action_id,
        "note": fr.note,
        "is_committed": fr.is_committed,
    }


@router.post("/tasks/{task_ref}/export")
def export_embodied(
    task_ref: str,
    body: EmbodiedExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _require_task(db, task_ref, current_user)
    ws = get_or_create_workspace(db, task, current_user)
    episode = get_episode_dict(task)
    state = workspace_to_state(db, task, ws)

    if body.format == "torque_csv":
        content = build_torque_csv(state, episode)
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="embodied_torque_{get_task_ref(task)}.csv"'
            },
        )

    if body.format == "lerobot_jsonl":
        content = build_lerobot_jsonl(task, ws, state, episode)
        return Response(
            content=content,
            media_type="application/x-ndjson; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="embodied_lerobot_{get_task_ref(task)}.jsonl"'
            },
        )

    if body.format == "lerobot_dataset":
        doc = build_export_json(task, ws, state, episode)
        content = build_lerobot_dataset_zip(
            [doc],
            str(episode.get("project_name") or "embodied"),
        )
        return Response(
            content=content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="embodied_lerobot_ds_{get_task_ref(task)}.zip"'
            },
        )

    if body.format == "hdf5":
        content = build_hdf5(task, ws, state, episode)
        return Response(
            content=content,
            media_type="application/x-hdf5",
            headers={
                "Content-Disposition": f'attachment; filename="embodied_{get_task_ref(task)}.hdf5"'
            },
        )

    if body.format == "rlds":
        doc = build_export_json(task, ws, state, episode)
        content = build_rlds_dataset_zip(
            [doc],
            str(episode.get("project_name") or "embodied"),
        )
        return Response(
            content=content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="embodied_rlds_{get_task_ref(task)}.zip"'
            },
        )

    payload = build_export_json(task, ws, state, episode)
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="embodied_{get_task_ref(task)}.json"'
        },
    )


@router.post("/tasks/{task_ref}/prelabel")
def prelabel_embodied(
    task_ref: str,
    body: EmbodiedPrelabelBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = body
    task = _require_task(db, task_ref, current_user)
    ws = get_or_create_workspace(db, task, current_user)
    result = apply_policy_prelabel(db, task, ws, model=body.model)
    state = workspace_to_state(db, task, ws)
    return {
        "message": "已应用策略预标注",
        "result": result,
        "workspace": _state_to_api(state),
    }


@router.post("/tasks/{task_ref}/submit")
def submit_embodied(
    task_ref: str,
    body: EmbodiedSubmitBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _require_task(db, task_ref, current_user)
    ws = get_or_create_workspace(db, task, current_user)
    ann = submit_annotation(db, task, current_user, ws, body.work_time)
    return {
        "message": "已提交具身标注",
        "annotation_id": ann.id,
        "task_id": task.id,
        "task_ref": get_task_ref(task),
        "task_status": task.status.value if hasattr(task.status, "value") else task.status,
    }
