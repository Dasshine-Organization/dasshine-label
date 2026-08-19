"""
项目模型
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SQLEnum, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.task import Task
    from app.models.organization import Organization


class ProjectType(str, enum.Enum):
    """项目类型"""
    TEXT_CLASSIFICATION = "text_classification"      # 文本分类
    NER = "ner"                                       # 命名实体识别
    TEXT_SUMMARIZATION = "text_summarization"        # 文本摘要
    IMAGE_CLASSIFICATION = "image_classification"    # 图像分类
    OBJECT_DETECTION = "object_detection"            # 目标检测
    IMAGE_SEGMENTATION = "image_segmentation"        # 图像分割
    OCR = "ocr"                                       # OCR
    AUDIO_TRANSCRIPTION = "audio_transcription"      # 语音转写
    MULTIMODAL = "multimodal"                        # 多模态


class ProjectStatus(str, enum.Enum):
    """项目状态"""
    DRAFT = "draft"                # 草稿
    PENDING = "pending"            # 待开始
    ACTIVE = "active"              # 进行中
    PAUSED = "paused"              # 已暂停
    COMPLETED = "completed"        # 已完成
    ARCHIVED = "archived"          # 已归档


class Project(Base, TimestampMixin):
    """项目表"""
    __tablename__ = "projects"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # 项目类型和状态（type 为遗留枚举；UI 分类以 category/ann_type 为准）
    type: Mapped[ProjectType] = mapped_column(SQLEnum(ProjectType))
    status: Mapped[ProjectStatus] = mapped_column(SQLEnum(ProjectStatus), default=ProjectStatus.DRAFT)

    # UI 分类一等字段（与 annotation_schema 双写，便于筛选与迁移）
    category: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    ann_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # 标注规范（JSON Schema）
    annotation_schema: Mapped[Dict[str, Any]] = mapped_column(JSON)
    
    # 自动标注配置
    auto_label_enabled: Mapped[bool] = mapped_column(default=False)
    auto_label_model: Mapped[Optional[str]] = mapped_column(String(100))  # 模型名称/ID
    auto_label_threshold: Mapped[float] = mapped_column(default=0.8)  # 置信度阈值
    
    # 质量控制配置
    quality_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    # 示例: {"golden_ratio": 0.1, "min_agreement": 0.8, "review_ratio": 0.1}
    
    # 统计信息
    total_items: Mapped[int] = mapped_column(default=0)  # 总数据量
    labeled_items: Mapped[int] = mapped_column(default=0)  # 已标注
    reviewed_items: Mapped[int] = mapped_column(default=0)  # 已审核
    approved_items: Mapped[int] = mapped_column(default=0)  # 已通过
    
    # 时间
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # 创建者
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped["User"] = relationship("User")

    # 多租户组织（可空：旧项目无组织）
    organization_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    organization: Mapped[Optional["Organization"]] = relationship(
        "Organization", back_populates="projects"
    )
    
    # 关系
    members: Mapped[List["ProjectMember"]] = relationship("ProjectMember", back_populates="project")
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="project")
    
    def __repr__(self) -> str:
        return f"<Project {self.name} ({self.status})>"
    
    @property
    def progress(self) -> float:
        """项目进度 %"""
        if self.total_items == 0:
            return 0.0
        return (self.approved_items / self.total_items) * 100


class ProjectMember(Base, TimestampMixin):
    """项目成员表"""
    __tablename__ = "project_members"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    # 角色
    role: Mapped[str] = mapped_column(String(50))  # owner, manager, annotator, reviewer
    
    # 权限
    can_assign: Mapped[bool] = mapped_column(default=False)
    can_review: Mapped[bool] = mapped_column(default=False)
    can_export: Mapped[bool] = mapped_column(default=False)

    # P17：guideline_ack_version / golden_fail_streak 等
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # 关系
    project: Mapped["Project"] = relationship("Project", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="projects")
    
    def __repr__(self) -> str:
        return f"<ProjectMember {self.user_id} in {self.project_id}>"
