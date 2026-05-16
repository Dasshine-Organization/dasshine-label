from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
import enum


# ── 复用你已有的 ProjectType，扩展新类型 ──────────────────────────────────────

class AnnotationCategory(str, enum.Enum):
    image_2d      = "image_2d"
    pointcloud_3d = "pointcloud_3d"
    video         = "video"
    audio         = "audio"
    nlp           = "nlp"
    embodied      = "embodied"
    ocr           = "ocr"
    multimodal    = "multimodal"


class AnnotationType(str, enum.Enum):
    # 图像 2D
    bbox_2d        = "bbox_2d"
    polygon        = "polygon"
    polyline       = "polyline"
    keypoint       = "keypoint"
    segmentation   = "segmentation"
    classification = "classification"
    # 3D
    bbox_3d        = "bbox_3d"
    lidar_seg      = "lidar_seg"
    lane_3d        = "lane_3d"
    # 视频
    video_tracking = "video_tracking"
    video_action   = "video_action"
    video_caption  = "video_caption"
    # 语音
    asr            = "asr"
    tts_label      = "tts_label"
    speaker_diarize= "speaker_diarize"
    emotion_audio  = "emotion_audio"
    # 语料
    ner            = "ner"
    re             = "re"
    sentiment      = "sentiment"
    text_classify  = "text_classify"
    qa_pair        = "qa_pair"
    summarization  = "summarization"
    translation    = "translation"
    # 具身机器人
    robot_traj     = "robot_traj"
    robot_action   = "robot_action"
    robot_grasp    = "robot_grasp"
    robot_scene    = "robot_scene"
    # OCR
    ocr_text       = "ocr_text"
    ocr_layout     = "ocr_layout"
    ocr_table      = "ocr_table"
    # 多模态
    image_caption  = "image_caption"
    vqa            = "vqa"
    rlhf           = "rlhf"


class DispatchStrategy(str, enum.Enum):
    smart       = "smart"
    random      = "random"
    round_robin = "round_robin"
    manual      = "manual"


# ── Label class ───────────────────────────────────────────────────────────────

class LabelClassSchema(BaseModel):
    name: str
    color: str = "#00d4ff"
    hotkey: Optional[str] = None
    attributes: List[Dict[str, Any]] = []


# ── Project Create / Update ───────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: str = ""
    cover_color: str = "#00d4ff"

    # 新增分类字段（存入 annotation_schema）
    category: AnnotationCategory
    ann_type: AnnotationType

    label_classes: List[LabelClassSchema] = []
    schema_config: Dict[str, Any] = {}

    # 分派配置
    dispatch_strategy: DispatchStrategy = DispatchStrategy.smart
    tasks_per_annotator: int = Field(10, ge=1, le=500)
    cross_validate_count: int = Field(1, ge=1, le=5)
    min_level: str = "novice"

    # 计费
    price_per_task: float = Field(0.1, ge=0)
    bonus_rate: float = Field(0.0, ge=0, le=1)

    # 时间
    deadline: Optional[datetime] = None

    # 自动标注
    auto_label_enabled: bool = False
    auto_label_model: str = "gpt-4o"
    auto_label_threshold: float = Field(0.8, ge=0, le=1)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cover_color: Optional[str] = None
    label_classes: Optional[List[LabelClassSchema]] = None
    schema_config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    dispatch_strategy: Optional[DispatchStrategy] = None
    tasks_per_annotator: Optional[int] = None
    cross_validate_count: Optional[int] = None
    price_per_task: Optional[float] = None
    bonus_rate: Optional[float] = None
    deadline: Optional[datetime] = None
    auto_label_enabled: Optional[bool] = None
    auto_label_model: Optional[str] = None
    auto_label_threshold: Optional[float] = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    cover_color: str
    category: Optional[str]
    ann_type: Optional[str]
    status: str
    dispatch_strategy: Optional[str]
    tasks_per_annotator: int
    cross_validate_count: int
    price_per_task: float
    auto_label_enabled: bool
    auto_label_model: Optional[str]
    auto_label_threshold: float
    total_items: int
    labeled_items: int
    approved_items: int
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectSummary(BaseModel):
    id: int
    name: str
    cover_color: str
    category: Optional[str]
    ann_type: Optional[str]
    status: str
    total_items: int
    approved_items: int
    price_per_task: float
    member_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


# ── Dispatch ──────────────────────────────────────────────────────────────────

class DispatchRequest(BaseModel):
    batch_size: int = Field(100, ge=1, le=2000)
    strategy: DispatchStrategy = DispatchStrategy.smart
    target_user_ids: Optional[List[int]] = None


class DispatchResult(BaseModel):
    success: bool
    batch_id: str
    assigned_count: int
    failed_count: int
    strategy: str
    assignments: List[Dict[str, Any]]
    message: str = ""


# ── Member ────────────────────────────────────────────────────────────────────

class AddMemberRequest(BaseModel):
    user_id: int
    role: str = Field("annotator", pattern="^(annotator|reviewer|manager|owner)$")


class MemberOut(BaseModel):
    user_id: int
    username: str
    level: str
    role: str
    accuracy_score: float
    completed_tasks: int


# ── Task import ───────────────────────────────────────────────────────────────

class TaskBulkCreate(BaseModel):
    data_urls: List[str] = []
    raw_texts: List[str] = []
    priority: int = 5
    golden_ratio: float = Field(0.05, ge=0, le=0.3)


# ── Stats ─────────────────────────────────────────────────────────────────────

class ProjectStats(BaseModel):
    project_id: int
    total_tasks: int
    pending: int
    assigned: int
    submitted: int
    approved: int
    rejected: int
    completion_rate: float
    approval_rate: float
    member_count: int
    dispatch_count: int
