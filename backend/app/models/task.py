"""
任务模型
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SQLEnum, JSON, Integer, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.project import Project
    from app.models.annotation import Annotation
    from app.models.annotation_draft import AnnotationDraft


class TaskStatus(str, enum.Enum):
    """任务状态"""
    PENDING = "pending"                    # 待分配
    PRE_LABELING = "pre_labeling"          # 自动标注中
    ASSIGNED = "assigned"                  # 已分配
    ANNOTATING = "annotating"              # 标注中
    SUBMITTED = "submitted"                # 已提交
    REVIEWING = "reviewing"                # 审核中
    REJECTED = "rejected"                  # 已驳回
    APPROVED = "approved"                  # 已通过
    SKIPPED = "skipped"                    # 已跳过


class TaskPriority(int, enum.Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    URGENT = 10


class Task(Base, TimestampMixin):
    """任务表（一个数据项）"""
    __tablename__ = "tasks"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # 关联项目
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    project: Mapped["Project"] = relationship("Project", back_populates="tasks")
    
    # 数据内容
    data: Mapped[Dict[str, Any]] = mapped_column(JSON)  # 原始数据
    data_url: Mapped[Optional[str]] = mapped_column(String(500))  # 文件URL（图片/音频/视频）
    
    # 元数据（使用 task_metadata 避免与 SQLAlchemy 保留字冲突）
    task_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, name="metadata")  # 额外元数据
    
    # 状态和优先级
    status: Mapped[TaskStatus] = mapped_column(SQLEnum(TaskStatus), default=TaskStatus.PENDING)
    priority: Mapped[int] = mapped_column(Integer, default=TaskPriority.NORMAL)
    
    # 自动标注结果
    pre_label_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    pre_label_confidence: Mapped[Optional[float]] = mapped_column(Float)
    
    # 分配信息
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    assignee: Mapped[Optional["User"]] = relationship("User", back_populates="assigned_tasks")
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # 时间跟踪
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # 工作量统计（秒）
    work_time: Mapped[int] = mapped_column(Integer, default=0)
    
    # 是否黄金标准题（测试题）
    is_golden: Mapped[bool] = mapped_column(Boolean, default=False)
    golden_answer: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)  # 标准答案
    
    # 关系 - 引用外部Annotation模型
    annotations: Mapped[List["Annotation"]] = relationship("Annotation", back_populates="task")
    annotation_drafts: Mapped[List["AnnotationDraft"]] = relationship(
        "AnnotationDraft", back_populates="task", cascade="all, delete-orphan"
    )
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="task")
    
    def __repr__(self) -> str:
        return f"<Task {self.id} ({self.status})>"


class Review(Base, TimestampMixin):
    """审核记录表"""
    __tablename__ = "reviews"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    task: Mapped["Task"] = relationship("Task", back_populates="reviews")
    
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    # 审核结果
    decision: Mapped[str] = mapped_column(String(20))  # approved, rejected
    score: Mapped[Optional[float]] = mapped_column(Float)  # 质量评分 0-100
    
    # 反馈
    feedback: Mapped[Optional[str]] = mapped_column(Text)  # 审核意见
    issues: Mapped[Optional[List[str]]] = mapped_column(JSON)  # 问题列表
    
    def __repr__(self) -> str:
        return f"<Review {self.id}: {self.decision}>"


class TaskAssignment(Base, TimestampMixin):
    """任务分配记录（用于追踪任务流转）"""
    __tablename__ = "task_assignments"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    action: Mapped[str] = mapped_column(String(50))  # assign, release, reassign, timeout
    reason: Mapped[Optional[str]] = mapped_column(String(200))
    
    def __repr__(self) -> str:
        return f"<TaskAssignment {self.action}>"
