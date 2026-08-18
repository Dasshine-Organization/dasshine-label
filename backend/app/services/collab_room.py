"""
任务共编房间：进程内 WebSocket 中继 + 可选 Redis pub/sub 扇出（多 worker）。
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import threading
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

from app.core.config import settings

logger = logging.getLogger("dasshine.collab")

_REDIS_CHANNEL = "dasshine:collab"


class CollabRoom:
    def __init__(self, task_id: int) -> None:
        self.task_id = task_id
        self.clients: Dict[WebSocket, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()

    async def add(self, ws: WebSocket, meta: Dict[str, Any]) -> None:
        async with self.lock:
            self.clients[ws] = meta

    async def remove(self, ws: WebSocket) -> None:
        async with self.lock:
            self.clients.pop(ws, None)

    def presence(self) -> list:
        seen = {}
        for meta in self.clients.values():
            uid = meta.get("user_id")
            if uid is not None:
                seen[uid] = {
                    "user_id": uid,
                    "username": meta.get("username"),
                }
        return list(seen.values())

    async def broadcast_local(
        self, payload: dict, *, exclude: Optional[WebSocket] = None
    ) -> None:
        dead: Set[WebSocket] = set()
        data = json.dumps(payload, ensure_ascii=False)
        for ws in list(self.clients.keys()):
            if exclude is not None and ws is exclude:
                continue
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            await self.remove(ws)


class CollabHub:
    def __init__(self) -> None:
        self._rooms: Dict[int, CollabRoom] = {}
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._redis = None
        self._pubsub_started = False
        self._origin = id(self)

    def _ensure_redis(self):
        if self._redis is not None:
            return self._redis
        url = str(getattr(settings, "REDIS_URL", "") or "")
        if not url:
            return None
        try:
            import redis

            self._redis = redis.from_url(url, decode_responses=True)
            self._redis.ping()
            logger.info("collab redis fanout enabled")
            return self._redis
        except Exception as e:
            logger.warning("collab redis unavailable: %s", e)
            self._redis = False  # type: ignore
            return None

    def _start_pubsub(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._pubsub_started:
            return
        r = self._ensure_redis()
        if not r or r is False:
            return
        self._pubsub_started = True
        self._loop = loop

        def _listen():
            try:
                pubsub = r.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(_REDIS_CHANNEL)
                for msg in pubsub.listen():
                    if msg.get("type") != "message":
                        continue
                    try:
                        envelope = json.loads(msg["data"])
                    except Exception:
                        continue
                    if envelope.get("origin") == self._origin:
                        continue
                    task_id = int(envelope.get("task_id") or 0)
                    payload = envelope.get("payload")
                    if not task_id or not isinstance(payload, dict):
                        continue
                    if self._loop:
                        asyncio.run_coroutine_threadsafe(
                            self._deliver_from_redis(task_id, payload),
                            self._loop,
                        )
            except Exception as e:
                logger.warning("collab pubsub stopped: %s", e)

        threading.Thread(target=_listen, name="collab-redis", daemon=True).start()

    async def _deliver_from_redis(self, task_id: int, payload: dict) -> None:
        room = await self.room(task_id)
        await room.broadcast_local(payload)

    async def room(self, task_id: int) -> CollabRoom:
        async with self._lock:
            if self._loop is None:
                try:
                    self._loop = asyncio.get_running_loop()
                    self._start_pubsub(self._loop)
                except RuntimeError:
                    pass
            if task_id not in self._rooms:
                self._rooms[task_id] = CollabRoom(task_id)
            return self._rooms[task_id]

    async def broadcast(
        self,
        task_id: int,
        payload: dict,
        *,
        exclude: Optional[WebSocket] = None,
    ) -> None:
        room = await self.room(task_id)
        await room.broadcast_local(payload, exclude=exclude)
        r = self._ensure_redis()
        if r and r is not False:
            try:
                r.publish(
                    _REDIS_CHANNEL,
                    json.dumps(
                        {
                            "origin": self._origin,
                            "task_id": task_id,
                            "payload": payload,
                        },
                        ensure_ascii=False,
                    ),
                )
            except Exception as e:
                logger.debug("collab redis publish failed: %s", e)

    async def discard_if_empty(self, task_id: int) -> None:
        async with self._lock:
            r = self._rooms.get(task_id)
            if r is not None and not r.clients:
                self._rooms.pop(task_id, None)


collab_hub = CollabHub()


def load_collab_state(db, task_id: int) -> bytes:
    from app.models.task_collab import TaskCollabDoc

    row = db.query(TaskCollabDoc).filter(TaskCollabDoc.task_id == task_id).first()
    if not row or not row.state:
        return b""
    engine = getattr(row, "engine", None) or "automerge"
    if engine not in ("automerge", ""):
        # 旧 Yjs 快照不再加载
        return b""
    return bytes(row.state)


def save_collab_state(db, task_id: int, state: bytes, user_id: Optional[int]) -> None:
    from app.models.task_collab import TaskCollabDoc

    row = db.query(TaskCollabDoc).filter(TaskCollabDoc.task_id == task_id).first()
    if row is None:
        row = TaskCollabDoc(
            task_id=task_id,
            state=state or b"",
            engine="automerge",
            updated_by_id=user_id,
        )
        db.add(row)
    else:
        row.state = state or b""
        row.engine = "automerge"
        row.updated_by_id = user_id
    db.commit()


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def from_b64(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def collab_enabled() -> bool:
    return bool(getattr(settings, "COLLAB_ENABLED", True))
