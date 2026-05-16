#!/usr/bin/env python3
"""种子：文本 / 语音 / 视频标注演示任务"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.database import SessionLocal, engine
from app.core.security import get_password_hash
from app.models.base import Base
from app.models.project import Project, ProjectMember, ProjectStatus
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User, UserRole, UserStatus
from app.schemas.project_schemas import AnnotationCategory, AnnotationType, ProjectCreate
from app.services.project_service import ProjectService

DEMO_TEXT = (
    "特斯拉公司今日在上海超级工厂宣布扩大产能。"
    "首席执行官马斯克表示，新款 Model Y 将在第四季度交付。"
    "分析师认为此举将加剧电动汽车市场竞争。"
)

DEMO_AUDIO_URL = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
DEMO_VIDEO_URL = "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"


def main():
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
        specs = [
            ("语料标注演示", AnnotationCategory.nlp, AnnotationType.ner, "nlp"),
            ("语音转写演示", AnnotationCategory.audio, AnnotationType.asr, "audio"),
            ("视频片段演示", AnnotationCategory.video, AnnotationType.video_action, "video"),
        ]
        task_defs = [
            (3001, "nlp", {"text": DEMO_TEXT, "title": "新闻稿 NER"}),
            (3002, "audio", {"audio_url": DEMO_AUDIO_URL, "title": "ASR 示例", "media_type": "audio"}),
            (3003, "video", {"video_url": DEMO_VIDEO_URL, "title": "动作片段", "media_type": "video"}),
        ]

        for pname, cat, atype, slug in specs:
            proj = db.query(Project).filter(Project.name == pname).first()
            if not proj:
                proj = svc.create(
                    ProjectCreate(
                        name=pname,
                        description=f"{pname} — 联调任务",
                        category=cat,
                        ann_type=atype,
                    ),
                    admin.id,
                )
                proj.status = ProjectStatus.ACTIVE
                db.commit()

            for tid, tslug, data in task_defs:
                if tslug != slug:
                    continue
                exists = False
                for t in db.query(Task).filter(Task.project_id == proj.id).all():
                    meta = t.task_metadata or {}
                    if meta.get("demo_slug") == str(tid) or str(tid) == str(t.id):
                        exists = True
                        break
                if exists:
                    continue
                url = data.get("audio_url") or data.get("video_url")
                task = Task(
                    project_id=proj.id,
                    data=data,
                    data_url=url,
                    task_metadata={"demo_slug": str(tid), "category": slug},
                    status=TaskStatus.PENDING,
                    priority=TaskPriority.NORMAL,
                    assignee_id=admin.id,
                )
                db.add(task)
        db.commit()
        print("✅ 文本/语音/视频演示任务已就绪（slug: 3001, 3002, 3003）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
