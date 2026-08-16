"""具身标注 API 模型"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class CameraIntrinsicsSchema(BaseModel):
    fx: float = 0.0
    fy: float = 0.0
    cx: float = 0.0
    cy: float = 0.0
    width: float = 0.0
    height: float = 0.0


class CameraExtrinsicsSchema(BaseModel):
    position: Dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    orientation: Dict[str, float] = Field(
        default_factory=lambda: {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}
    )


class CameraStreamSchema(BaseModel):
    id: str
    label: str
    src: str
    fallback_src: Optional[str] = None
    object_position: Optional[str] = None
    scale: Optional[float] = None
    intrinsics: Optional[CameraIntrinsicsSchema] = None
    extrinsics: Optional[CameraExtrinsicsSchema] = None


class EmbodiedAttributionSchema(BaseModel):
    title: str = ""
    detail_url: str = ""
    note: str = ""


class EmbodiedEpisodeSchema(BaseModel):
    case_id: str
    project_name: str
    clip_duration_sec: float
    fps: int
    total_frames: int
    streams: List[CameraStreamSchema]
    attribution: EmbodiedAttributionSchema = Field(default_factory=EmbodiedAttributionSchema)
    instruction: str = ""
    success: Literal["success", "fail", "unknown"] = "unknown"
    has_proprioception: bool = False


class ActionLabelSchema(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=200)


class FrameAnnotationSchema(BaseModel):
    action_id: str = "idle"
    note: Optional[str] = None


class ActionSegmentSchema(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    start_frame: int = Field(..., ge=0)
    end_frame: int = Field(..., ge=0)
    action_id: str = "idle"
    note: Optional[str] = None


class GraspPoseSchema(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    frame: int = Field(0, ge=0)
    position: Dict[str, float] = Field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    orientation: Dict[str, float] = Field(
        default_factory=lambda: {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}
    )
    width: float = 0.08
    label: str = "grasp"


class TrajectoryPointSchema(BaseModel):
    frame: int = Field(0, ge=0)
    ee: Dict[str, float] = Field(
        default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0, "roll": 0.0, "pitch": 0.0, "yaw": 0.0}
    )
    gripper: float = 0.0


class PreferencePairSchema(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    prompt: str = ""
    chosen: str = ""
    rejected: str = ""
    winner: Literal["a", "b", "tie"] = "tie"


class EmbodiedWorkspaceStateSchema(BaseModel):
    task_id: int
    task_ref: str
    user_id: int
    action_labels: List[ActionLabelSchema]
    frame_actions: Dict[int, FrameAnnotationSchema]
    committed_frames: List[int]
    instruction: str = ""
    success: Literal["success", "fail", "unknown"] = "unknown"
    segments: List[ActionSegmentSchema] = Field(default_factory=list)
    grasps: List[GraspPoseSchema] = Field(default_factory=list)
    trajectory: List[TrajectoryPointSchema] = Field(default_factory=list)
    preferences: List[PreferencePairSchema] = Field(default_factory=list)
    updated_at: Optional[datetime] = None


class EmbodiedWorkspacePutBody(BaseModel):
    action_labels: List[ActionLabelSchema]
    frame_actions: Dict[int, FrameAnnotationSchema] = Field(default_factory=dict)
    committed_frames: List[int] = Field(default_factory=list)
    instruction: Optional[str] = None
    success: Optional[Literal["success", "fail", "unknown"]] = None
    segments: Optional[List[ActionSegmentSchema]] = None
    grasps: Optional[List[GraspPoseSchema]] = None
    trajectory: Optional[List[TrajectoryPointSchema]] = None
    preferences: Optional[List[PreferencePairSchema]] = None


class FramePatchBody(BaseModel):
    action_id: Optional[str] = None
    note: Optional[str] = None
    commit: Optional[bool] = None


class EmbodiedExportRequest(BaseModel):
    format: Literal[
        "json", "torque_csv", "lerobot_jsonl", "lerobot_dataset", "hdf5", "rlds", "tfrecord"
    ] = "json"


class EmbodiedSubmitBody(BaseModel):
    work_time: int = Field(0, ge=0)


class EmbodiedPrelabelBody(BaseModel):
    model: Literal["auto", "embodied_policy_demo", "embodied_policy_http"] = "auto"
