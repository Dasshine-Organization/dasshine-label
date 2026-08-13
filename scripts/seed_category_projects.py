#!/usr/bin/env python3
"""为每个 AnnotationCategory 确保至少一个真实项目（幂等，按名称去重）。

用法（仓库根目录）:
  python scripts/seed_category_projects.py

不写入硬编码演示 task id；任务请通过项目管理导入。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.database import SessionLocal, engine
from app.core.security import get_password_hash
from app.models.base import Base
from app.models.project import Project, ProjectStatus
from app.models.user import User, UserRole, UserStatus
from app.schemas.project_schemas import AnnotationCategory, AnnotationType, ProjectCreate
from app.services.project_service import ProjectService

# 每类一个默认 ann_type + 展示名
CATEGORY_SEEDS = [
    ("种子 · 图像 2D", AnnotationCategory.image_2d, AnnotationType.bbox_2d),
    ("种子 · 3D 点云", AnnotationCategory.pointcloud_3d, AnnotationType.bbox_3d),
    ("种子 · 视频", AnnotationCategory.video, AnnotationType.video_action),
    ("种子 · 语音", AnnotationCategory.audio, AnnotationType.asr),
    ("种子 · 语料", AnnotationCategory.nlp, AnnotationType.ner),
    ("种子 · 具身", AnnotationCategory.embodied, AnnotationType.robot_action),
    ("种子 · OCR", AnnotationCategory.ocr, AnnotationType.ocr_text),
    ("种子 · 多模态", AnnotationCategory.multimodal, AnnotationType.vqa),
]


def main() -> None:
    from app.models import user, project, task, annotation, annotation_draft, embodied  # noqa: F401

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@dasshine.com",
                hashed_password=get_password_hash("admin123"),
                full_name="管理员",
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        svc = ProjectService(db)
        created = 0
        for name, cat, atype in CATEGORY_SEEDS:
            existing = db.query(Project).filter(Project.name == name).first()
            if existing:
                # 确保列字段与 schema 同步
                if not existing.category:
                    existing.category = cat.value
                if not existing.ann_type:
                    existing.ann_type = atype.value
                db.commit()
                print(f"= skip exists: {name} (id={existing.id})")
                continue
            proj = svc.create(
                ProjectCreate(
                    name=name,
                    description=f"P1 种子项目 · {cat.value}/{atype.value}",
                    category=cat,
                    ann_type=atype,
                    label_classes=[{"name": "default", "color": "#00d4ff"}],
                ),
                admin.id,
            )
            proj.status = ProjectStatus.ACTIVE
            db.commit()
            created += 1
            print(f"+ created: {name} (id={proj.id}, category={proj.category})")

        print(f"Done. created={created}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
