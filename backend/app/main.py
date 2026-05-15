"""
FastAPI主入口
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import auth, projects, tasks, annotations, users, export, auto_label, quality, annotations_3d
from app.api.v1 import annotation_drafts, project_labels, task_prelabel


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    
    # 创建上传目录
    import os
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    yield
    
    # 关闭时执行
    print("👋 应用关闭")


def create_application() -> FastAPI:
    """创建FastAPI应用实例"""
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="自动标注与分发平台 API",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )
    
    # CORS配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(auth.router, prefix="/api/v1", tags=["认证"])
    app.include_router(users.router, prefix="/api/v1", tags=["用户"])
    app.include_router(projects.router, prefix="/api/v1", tags=["项目"])
    app.include_router(tasks.router, prefix="/api/v1", tags=["任务"])
    app.include_router(annotations.router, prefix="/api/v1", tags=["标注"])
    app.include_router(annotation_drafts.router, prefix="/api/v1", tags=["标注草稿"])
    app.include_router(project_labels.router, prefix="/api/v1", tags=["项目标签"])
    app.include_router(task_prelabel.router, prefix="/api/v1", tags=["预标注"])
    app.include_router(annotations_3d.router, prefix="/api/v1", tags=["3D标注"])
    app.include_router(export.router, prefix="/api/v1", tags=["导出"])
    app.include_router(auto_label.router, prefix="/api/v1", tags=["自动标注"])
    app.include_router(quality.router, prefix="/api/v1", tags=["质量控制"])
    # app.include_router(projects.router, prefix="/api/v1"， tags=["项目管理"])

    @app.get("/")
    async def root():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs"
        }
    
    @app.get("/health")
    async def health_check():
        return {"status": "ok"}
    
    return app


# 创建应用实例
app = create_application()
