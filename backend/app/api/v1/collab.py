"""
Automerge 共编：WebSocket 中继 + HTTP 快照兜底。
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.user import User
from app.services.collab_room import (
    b64,
    collab_enabled,
    collab_hub,
    from_b64,
    load_collab_state,
    save_collab_state,
)
from app.services.project_acl import can_access_task_workspace, get_task_and_project

logger = logging.getLogger("dasshine.collab")

router = APIRouter(tags=["collab"])


class CollabDocBody(BaseModel):
    state_b64: str = Field(..., description="Automerge.save base64")
    engine: str = Field(default="automerge")


def _user_from_token(db: Session, token: str) -> Optional[User]:
    payload = decode_access_token(token)
    if not payload:
        return None
    uid = payload.get("sub")
    if not uid:
        return None
    return db.query(User).filter(User.id == int(uid)).first()


@router.get("/tasks/{task_id}/collab-doc")
def get_collab_doc(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not collab_enabled():
        raise HTTPException(status_code=503, detail="共编未启用")
    task, _ = get_task_and_project(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权访问")
    state = load_collab_state(db, task_id)
    return {
        "task_id": task_id,
        "engine": "automerge",
        "state_b64": b64(state) if state else "",
    }


@router.put("/tasks/{task_id}/collab-doc")
def put_collab_doc(
    task_id: int,
    body: CollabDocBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not collab_enabled():
        raise HTTPException(status_code=503, detail="共编未启用")
    task, _ = get_task_and_project(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not can_access_task_workspace(db, task, current_user):
        raise HTTPException(status_code=403, detail="无权访问")
    try:
        raw = from_b64(body.state_b64) if body.state_b64 else b""
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效 state_b64: {e}") from e
    save_collab_state(db, task_id, raw, current_user.id)
    return {"ok": True, "task_id": task_id, "bytes": len(raw)}


@router.websocket("/ws/tasks/{task_id}/collab")
async def collab_ws(
    websocket: WebSocket,
    task_id: int,
    token: str = Query(...),
):
    if not collab_enabled():
        await websocket.close(code=1013)
        return

    db = SessionLocal()
    try:
        user = _user_from_token(db, token)
        if not user or not user.is_active:
            await websocket.close(code=4401)
            return
        task, _ = get_task_and_project(db, task_id)
        if not task or not can_access_task_workspace(db, task, user):
            await websocket.close(code=4403)
            return
        init_state = load_collab_state(db, task_id)
        meta = {"user_id": user.id, "username": user.username}
    finally:
        db.close()

    await websocket.accept()
    room = await collab_hub.room(task_id)
    await room.add(websocket, meta)
    from app.core.metrics import collab_ws_close, collab_ws_message, collab_ws_open

    collab_ws_open()

    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "init",
                    "engine": "automerge",
                    "state_b64": b64(init_state) if init_state else "",
                    "presence": room.presence(),
                },
                ensure_ascii=False,
            )
        )
        await collab_hub.broadcast(
            task_id,
            {"type": "presence", "presence": room.presence()},
        )

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            mtype = msg.get("type")
            collab_ws_message(str(mtype or "unknown"))
            if mtype == "update":
                await collab_hub.broadcast(
                    task_id,
                    {
                        "type": "update",
                        "update_b64": msg.get("update_b64") or "",
                        "from_user_id": meta["user_id"],
                    },
                    exclude=websocket,
                )
            elif mtype == "awareness":
                await collab_hub.broadcast(
                    task_id,
                    {
                        "type": "awareness",
                        "payload": msg.get("payload"),
                        "from_user_id": meta["user_id"],
                        "from_username": meta["username"],
                    },
                    exclude=websocket,
                )
            elif mtype == "persist":
                state_b64 = msg.get("state_b64") or ""
                try:
                    state = from_b64(state_b64) if state_b64 else b""
                except Exception:
                    continue
                db2 = SessionLocal()
                try:
                    save_collab_state(db2, task_id, state, meta["user_id"])
                finally:
                    db2.close()
            elif mtype == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("collab_ws error task=%s: %s", task_id, e)
    finally:
        collab_ws_close()
        await room.remove(websocket)
        await collab_hub.broadcast(
            task_id, {"type": "presence", "presence": room.presence()}
        )
        await collab_hub.discard_if_empty(task_id)
