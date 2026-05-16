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
    EmbodiedEpisodeSchema,
    EmbodiedExportRequest,
    EmbodiedSubmitBody,
    EmbodiedWorkspacePutBody,
    EmbodiedWorkspaceStateSchema,
    FramePatchBody,
)
from app.services.project_acl import can_access_task_workspace
from app.services.embodied_service import (
    apply_workspace_put,
    build_export_json,
    build_torque_csv,
    get_episode_dict,
    get_or_create_workspace,
    get_task_ref,
    patch_frame,
    resolve_task,
    submit_annotation,
    workspace_to_state,
)

router = APIRouter(prefix="/embodied", tags=["具身标注"])


def _episode_to_api(ep: Dict[str, Any]) -> EmbodiedEpisodeSchema:
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
    return EmbodiedEpisodeSchema(
        case_id=ep["case_id"],
        project_name=ep["project_name"],
        clip_duration_sec=ep["clip_duration_sec"],
        fps=ep["fps"],
        total_frames=ep["total_frames"],
        streams=streams,
        attribution={
            "title": attr.get("title", ""),
            "detail_url": attr.get("detail_url", ""),
            "note": attr.get("note", ""),
        },
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
    return _episode_to_api(get_episode_dict(task))


@router.get("/tasks/{task_ref}/workspace", response_model=EmbodiedWorkspaceStateSchema)
def get_workspace(
    task_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = _require_task(db, task_ref, current_user)
    ws = get_or_create_workspace(db, task, current_user)
    state = workspace_to_state(db, task, ws)
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
        updated_at=state.get("updated_at"),
    )


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
            ws,
            [x.model_dump() for x in body.action_labels],
            {int(k): v.model_dump() for k, v in body.frame_actions.items()},
            body.committed_frames,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    db.refresh(ws)
    state = workspace_to_state(db, task, ws)
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
        updated_at=state.get("updated_at"),
    )


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

    payload = build_export_json(task, ws, state, episode)
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="embodied_{get_task_ref(task)}.json"'
        },
    )


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
    }
