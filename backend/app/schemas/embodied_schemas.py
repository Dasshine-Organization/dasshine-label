"""具身标注 API 模型"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CameraStreamSchema(BaseModel):
    id: str
    label: str
    src: str
    fallback_src: Optional[str] = None
    object_position: Optional[str] = None
    scale: Optional[float] = None


class EmbodiedAttributionSchema(BaseModel):
    title: str
    detail_url: str
    note: str


class EmbodiedEpisodeSchema(BaseModel):
    case_id: Literal["mars", "aloha"]
    project_name: str
    clip_duration_sec: float
    fps: int
    total_frames: int
    streams: List[CameraStreamSchema]
    attribution: EmbodiedAttributionSchema


class ActionLabelSchema(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=200)


class FrameAnnotationSchema(BaseModel):
    action_id: str = "idle"
    note: Optional[str] = None


class EmbodiedWorkspaceStateSchema(BaseModel):
    task_id: int
    task_ref: str
    user_id: int
    action_labels: List[ActionLabelSchema]
    frame_actions: Dict[int, FrameAnnotationSchema]
    committed_frames: List[int]
    updated_at: Optional[datetime] = None


class EmbodiedWorkspacePutBody(BaseModel):
    action_labels: List[ActionLabelSchema]
    frame_actions: Dict[int, FrameAnnotationSchema] = Field(default_factory=dict)
    committed_frames: List[int] = Field(default_factory=list)


class FramePatchBody(BaseModel):
    action_id: Optional[str] = None
    note: Optional[str] = None
    commit: Optional[bool] = None


class EmbodiedExportRequest(BaseModel):
    format: Literal["json", "torque_csv"] = "json"


class EmbodiedSubmitBody(BaseModel):
    work_time: int = Field(0, ge=0)
