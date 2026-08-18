"""
数据库连接管理（唯一引擎入口；app.db.session 转发至此）
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.core.config import settings

try:
    from app.models.base import Base  # noqa: F401
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

    Base = declarative_base()

_pool = getattr(settings, "DATABASE_POOL_SIZE", 20) or 20
_overflow = getattr(settings, "DATABASE_MAX_OVERFLOW", 10) or 10
engine = create_engine(
    str(settings.DATABASE_URL),
    pool_pre_ping=True,
    pool_size=int(_pool),
    max_overflow=max(int(_overflow), int(_pool)),
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """获取数据库会话（用于依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """初始化数据库（创建表）"""
    from app.models.base import Base
    from app.models import (  # noqa: F401
        user,
        project,
        task,
        annotation,
        annotation_draft,
        embodied,
        organization,
        task_lock,
        org_billing,
        task_collab,
        storage_mount,
    )

    Base.metadata.create_all(bind=engine)
