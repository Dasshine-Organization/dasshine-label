#!/usr/bin/env python3
"""
种子数据：具身标注演示项目与任务（slug: demo / 2001 / 2002）
用法: 在项目根目录执行 python scripts/seed_embodied.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.project import Project, ProjectMember, ProjectStatus, ProjectType  # noqa: E402
from app.models.task import Task, TaskPriority, TaskStatus  # noqa: E402
from app.models.user import User, UserRole, UserStatus  # noqa: E402
from app.services.embodied_episodes import episode_for_slug  # noqa: E402


def ensure_tables():
    from app.models import user, project, task, annotation, annotation_draft, embodied  # noqa: F401

    Base.metadata.create_all(bind=engine)


def seed():
    ensure_tables()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@dasshine.com",
                hashed_password=get_password_hash("admin123"),
                full_name="系统管理员",
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        project = (
            db.query(Project)
            .filter(Project.name == "具身机器人标注演示")
            .first()
        )
        if not project:
            project = Project(
                name="具身机器人标注演示",
                description="InSight 多裁剪与 ALOHA 四相机 LeRobot 演示",
                type=ProjectType.MULTIMODAL,
                status=ProjectStatus.ACTIVE,
                annotation_schema={
                    "category": "embodied",
                    "ann_type": "robot_action",
                    "label_classes": [],
                },
                created_by_id=admin.id,
                total_items=3,
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            db.add(
                ProjectMember(
                    project_id=project.id,
                    user_id=admin.id,
                    role="owner",
                    can_assign=True,
                    can_review=True,
                    can_export=True,
                )
            )
            db.commit()

        slugs = [
            ("demo", "mars", "具身 · InSight 演示"),
            ("2001", "mars", "具身 · InSight 多视角"),
            ("2002", "aloha", "具身 · ALOHA 四相机"),
        ]
        created = 0
        for slug, case, title in slugs:
            existing = None
            for t in db.query(Task).filter(Task.project_id == project.id).all():
                meta = t.task_metadata or {}
                if meta.get("embodied_slug") == slug:
                    existing = t
                    break
            if existing:
                continue
            ep = episode_for_slug("2002" if case == "aloha" else "demo")
            task = Task(
                project_id=project.id,
                data={
                    "embodied_slug": slug,
                    "title": title,
                    "embodied_episode": ep,
                },
                task_metadata={"embodied_slug": slug, "category": "embodied"},
                status=TaskStatus.PENDING,
                priority=TaskPriority.NORMAL,
                assignee_id=admin.id,
            )
            db.add(task)
            created += 1
        db.commit()
        print(f"✅ 具身演示项目 id={project.id}，新建任务 {created} 条（slug: demo, 2001, 2002）")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
