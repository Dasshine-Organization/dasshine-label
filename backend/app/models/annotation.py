"""
标注数据模型
支持文本、图片、3D点云等多种标注类型
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum, JSON, Integer, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.task import Task


class AnnotationStatus(str, enum.Enum):
    """标注状态"""
    PENDING = "pending"      # 待标注
    IN_PROGRESS = "in_progress"  # 标注中
    COMPLETED = "completed"  # 已完成
    REVIEWING = "reviewing"  # 审核中
    APPROVED = "approved"    # 已通过
    REJECTED = "rejected"    # 已拒绝


class AnnotationType(str, enum.Enum):
    """标注类型"""
    TEXT = "text"            # 文本标注
    CLASSIFICATION = "classification"  # 分类
    NER = "ner"              # 命名实体识别
    BOUNDING_BOX = "bounding_box"  # 2D边界框
    POLYGON = "polygon"      # 多边形
    KEYPOINT = "keypoint"    # 关键点
    SEGMENTATION = "segmentation"  # 分割
    CUBOID_3D = "cuboid_3d"  # 3D边界框
    POINT_3D = "point_3d"    # 3D点
    POLYGON_3D = "polygon_3d"  # 3D多边形
    SENTIMENT = "sentiment"  # 情感分析
    SUMMARY = "summary"      # 摘要
    ROBOT_ACTION = "robot_action"  # 具身逐帧动作序列


class Annotation(Base, TimestampMixin):
    """标注模型
    
    支持多种标注类型，数据以JSON格式存储在data字段中
    """
    __tablename__ = "annotations"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # 关联关系
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    task: Mapped["Task"] = relationship("Task", back_populates="annotations")
    
    # 关联的数据项ID（文本ID、图片ID、点云文件名等）
    data_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    # 时序帧ID（用于视频或连续帧标注）
    frame_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # 追踪ID（用于目标追踪）
    track_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    
    # 标注类型
    annotation_type: Mapped[AnnotationType] = mapped_column(Enum(AnnotationType), nullable=False)
    
    # 标注数据（JSON格式，根据类型不同结构不同）
    data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # 标注状态
    status: Mapped[AnnotationStatus] = mapped_column(Enum(AnnotationStatus), default=AnnotationStatus.COMPLETED)
    
    # 审核相关
    review_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # approved/rejected
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # 质量评分 (0-100)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # 工作时长(秒)
    work_time: Mapped[int] = mapped_column(Integer, default=0)
    
    # 创建者
    annotator_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    annotator: Mapped["User"] = relationship("User", back_populates="annotations", foreign_keys=[annotator_id])
    
    # 版本控制
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("annotations.id"), nullable=True)
    
    # 是否是最新版本
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 置信度（自动标注时）
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # 元数据（避免使用 metadata 保留字）
    annotation_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, name="metadata")
    
    def __repr__(self) -> str:
        return f"<Annotation(id={self.id}, type={self.annotation_type}, task_id={self.task_id})>"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "data_id": self.data_id,
            "frame_id": self.frame_id,
            "track_id": self.track_id,
            "annotation_type": self.annotation_type.value,
            "data": self.data,
            "status": self.status.value,
            "review_status": self.review_status,
            "review_comment": self.review_comment,
            "quality_score": self.quality_score,
            "work_time": self.work_time,
            "annotator_id": self.annotator_id,
            "version": self.version,
            "is_latest": self.is_latest,
            "confidence": self.confidence,
            "metadata": self.annotation_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
