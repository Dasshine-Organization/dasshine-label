"""
FastAPI主入口
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1 import (
    annotation_drafts,
    annotations,
    annotations_3d,
    auth,
    auto_label,
    billing,
    collab,
    dataset,
    embodied,
    export,
    modality_workspace,
    orgs,
    project_labels,
    projects,
    quality,
    roles,
    storage,
    storage_mounts,
    task_prelabel,
    tasks,
    users,
)
from app.core.config import settings
from app.core.logging_middleware import RequestLoggingMiddleware
from app.core.logging_setup import setup_logging
from app.core.rate_limit_middleware import RateLimitMiddleware

logger = logging.getLogger("dasshine.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info(
        "starting app=%s version=%s debug=%s upload_dir=%s cors=%s",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.DEBUG,
        settings.UPLOAD_DIR,
        settings.BACKEND_CORS_ORIGINS,
    )
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    yield
    logger.info("shutting down")


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="自动标注与分发平台 API",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/v1", tags=["认证"])
    app.include_router(users.router, prefix="/api/v1", tags=["用户"])
    app.include_router(roles.router, prefix="/api/v1", tags=["角色"])
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(orgs.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    app.include_router(dataset.router, prefix="/api/v1")
    app.include_router(storage.router, prefix="/api/v1")
    app.include_router(storage_mounts.router, prefix="/api/v1")
    app.include_router(collab.router, prefix="/api/v1")
    app.include_router(tasks.router, prefix="/api/v1", tags=["任务"])
    app.include_router(annotations.router, prefix="/api/v1", tags=["标注"])
    app.include_router(annotation_drafts.router, prefix="/api/v1", tags=["标注草稿"])
    app.include_router(project_labels.router, prefix="/api/v1", tags=["项目标签"])
    app.include_router(task_prelabel.router, prefix="/api/v1", tags=["预标注"])
    app.include_router(annotations_3d.router, prefix="/api/v1", tags=["3D标注"])
    app.include_router(export.router, prefix="/api/v1", tags=["导出"])
    app.include_router(auto_label.router, prefix="/api/v1", tags=["自动标注"])
    app.include_router(quality.router, prefix="/api/v1", tags=["质量控制"])
    app.include_router(embodied.router, prefix="/api/v1")
    app.include_router(modality_workspace.router, prefix="/api/v1")

    upload_path = os.path.abspath(settings.UPLOAD_DIR)
    os.makedirs(upload_path, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=upload_path), name="uploads")

    @app.get("/")
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs" if settings.DEBUG else None,
        }

    @app.get("/health")
    async def health_check():
        """存活探针：进程可响应即可。"""
        return {"status": "ok", "version": settings.APP_VERSION}

    @app.get("/ready")
    async def readiness_check():
        """就绪探针：数据库 + 存储可写。"""
        from app.core.database import engine
        from app.services.file_storage import FileStorageService

        db_ok = False
        db_error = None
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = True
        except Exception as e:
            db_error = str(e)
            logger.warning("readiness db check failed: %s", e)

        storage_check = {"ok": False}
        try:
            storage_check = FileStorageService().health_check()
        except Exception as e:
            storage_check = {"ok": False, "error": str(e)}
            logger.warning("readiness storage check failed: %s", e)

        ready = db_ok and bool(storage_check.get("ok"))
        payload = {
            "status": "ready" if ready else "not_ready",
            "checks": {
                "database": {"ok": db_ok, "error": db_error},
                "storage": storage_check,
            },
            "version": settings.APP_VERSION,
        }
        if not ready:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=503, content=payload)
        return payload

    return app


app = create_application()
