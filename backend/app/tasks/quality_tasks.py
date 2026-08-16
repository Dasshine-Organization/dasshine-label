"""
质量检查相关任务
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def check_timeout_tasks():
    """
    检查并回收超时任务

    定时任务，每5分钟执行一次
    """
    try:
        from app.core.database import SessionLocal
        from app.services.task_dispatch import TaskDispatchService

        db = SessionLocal()
        try:
            service = TaskDispatchService(db)
            released = service.check_timeout_tasks(timeout_minutes=30)

            if released > 0:
                logger.info("回收了 %s 个超时任务", released)

            return {"released": released}

        finally:
            db.close()

    except Exception as e:
        logger.error("检查超时任务失败: %s", e)
        raise


@shared_task
def rotate_golden_tasks():
    """
    黄金题轮换：对开启 quality_config.golden_rotation 的项目维持黄金题比例。

    quality_config 示例:
      { "golden_rotation": true, "golden_ratio": 0.1 }
    """
    from app.core.database import SessionLocal
    from app.models.project import Project
    from app.services.quality_control import get_quality_service

    db = SessionLocal()
    try:
        projects = db.query(Project).all()
        total_inserted = 0
        touched = 0
        svc = get_quality_service(db)
        for project in projects:
            qc = project.quality_config or {}
            if not isinstance(qc, dict):
                continue
            if not qc.get("golden_rotation"):
                continue
            ratio = float(qc.get("golden_ratio") or qc.get("golden_claim_ratio") or 0.1)
            ratio = max(0.01, min(0.3, ratio))
            inserted = svc.insert_golden_tasks(project.id, ratio=ratio)
            if inserted:
                total_inserted += inserted
                touched += 1
        logger.info(
            "golden rotation done projects=%s inserted=%s",
            touched,
            total_inserted,
        )
        return {"projects": touched, "inserted": total_inserted}
    except Exception as e:
        logger.error("黄金题轮换失败: %s", e)
        raise
    finally:
        db.close()
