"""
数据库初始化脚本
创建默认管理员账号和测试数据

在仓库根目录执行：
  python scripts/init_db.py
或在 backend 目录下确保 PYTHONPATH 含 backend。
"""
from __future__ import annotations

import sys
from pathlib import Path

# 以本仓库 backend 为准（勿硬编码其它本地路径 / 分叉副本）
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
# 先导入所有模型，确保 SQLAlchemy mapper 正确配置
from app.models.base import Base
from app.models.user import User, UserRole, UserStatus
from app.models.project import Project, ProjectMember  # 导入 ProjectMember
from app.models.task import Task
from app.models.annotation import Annotation
from app.models import embodied  # noqa: F401 — embodied_workspaces / embodied_frame_annotations
from app.core.security import get_password_hash


def init_database():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表创建完成")


def create_default_users(db: Session):
    """创建默认用户"""
    
    # 检查是否已有用户
    existing = db.query(User).first()
    if existing:
        print("⚠️  数据库中已有用户，跳过创建默认账号")
        return
    
    # 创建管理员账号
    admin = User(
        username="admin",
        email="admin@dasshine.com",
        hashed_password=get_password_hash("admin123"),
        full_name="系统管理员",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        level="expert"
    )
    db.add(admin)
    
    # 创建标注员账号
    annotator = User(
        username="annotator",
        email="annotator@dasshine.com",
        hashed_password=get_password_hash("anno123"),
        full_name="测试标注员",
        role=UserRole.ANNOTATOR,
        status=UserStatus.ACTIVE,
        level="intermediate"
    )
    db.add(annotator)
    
    # 创建审核员账号
    reviewer = User(
        username="reviewer",
        email="reviewer@dasshine.com",
        hashed_password=get_password_hash("review123"),
        full_name="测试审核员",
        role=UserRole.REVIEWER,
        status=UserStatus.ACTIVE,
        level="senior"
    )
    db.add(reviewer)
    
    db.commit()
    print("✅ 默认用户创建完成")


def main():
    print("🚀 Dasshine Label 数据库初始化...")
    
    # 创建表
    init_database()
    
    # 创建默认用户
    db = SessionLocal()
    try:
        create_default_users(db)
        print("\n" + "="*50)
        print("📋 默认账号信息:")
        print("="*50)
        print("\n👤 管理员账号:")
        print("   用户名: admin")
        print("   密码: admin123")
        print("   角色: 系统管理员")
        print("\n👤 标注员账号:")
        print("   用户名: annotator")
        print("   密码: anno123")
        print("   角色: 标注员")
        print("\n👤 审核员账号:")
        print("   用户名: reviewer")
        print("   密码: review123")
        print("   角色: 审核员")
        print("\n" + "="*50)
        print("✨ 初始化完成！可以登录系统了")
        print("="*50)
    finally:
        db.close()


if __name__ == "__main__":
    main()
