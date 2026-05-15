"""
用户模型
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.project import Project, ProjectMember
    from app.models.task import Task
    from app.models.annotation import Annotation
    from app.models.annotation_draft import AnnotationDraft


class UserRole(str, enum.Enum):
    """用户角色"""
    SUPER_ADMIN = "super_admin"    # 超级管理员
    ADMIN = "admin"                # 管理员
    MANAGER = "manager"            # 项目经理
    ANNOTATOR = "annotator"        # 标注员
    REVIEWER = "reviewer"          # 审核员


class UserStatus(str, enum.Enum):
    """用户状态"""
    ACTIVE = "active"              # 活跃
    INACTIVE = "inactive"          # 未激活
    SUSPENDED = "suspended"        # 已暂停
    DELETED = "deleted"            # 已删除


class AnnotatorLevel(str, enum.Enum):
    """标注员等级"""
    NOVICE = "novice"              # 新手
    JUNIOR = "junior"              # 初级
    INTERMEDIATE = "intermediate"  # 中级
    SENIOR = "senior"              # 高级
    EXPERT = "expert"              # 专家


class User(Base, TimestampMixin):
    """用户表"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    
    # 基本信息
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    avatar: Mapped[Optional[str]] = mapped_column(String(500))  # 头像URL
    
    # 角色和状态
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.ANNOTATOR)
    status: Mapped[UserStatus] = mapped_column(SQLEnum(UserStatus), default=UserStatus.ACTIVE)
    
    # 标注员专属字段
    level: Mapped[AnnotatorLevel] = mapped_column(SQLEnum(AnnotatorLevel), default=AnnotatorLevel.NOVICE)
    accuracy_score: Mapped[float] = mapped_column(default=0.0)  # 准确率评分 0-100
    efficiency_score: Mapped[float] = mapped_column(default=0.0)  # 效率评分
    total_tasks: Mapped[int] = mapped_column(default=0)  # 总任务数
    completed_tasks: Mapped[int] = mapped_column(default=0)  # 已完成任务数
    
    # 技能标签（JSON数组）
    skills: Mapped[Optional[str]] = mapped_column(Text)  # ["法律", "医疗", "NER"]
    
    # 最后登录
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # 关系
    projects: Mapped[List["ProjectMember"]] = relationship("ProjectMember", back_populates="user")
    annotations: Mapped[List["Annotation"]] = relationship(
        "Annotation", 
        back_populates="annotator",
        foreign_keys="Annotation.annotator_id"
    )
    assigned_tasks: Mapped[List["Task"]] = relationship("Task", back_populates="assignee")
    annotation_drafts: Mapped[List["AnnotationDraft"]] = relationship(
        "AnnotationDraft", back_populates="user", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"
    
    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE
    
    @property
    def is_admin(self) -> bool:
        return self.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]
    
    @property
    def completion_rate(self) -> float:
        """完成率"""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100
