"""
数据库连接管理
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
    
# 创建数据库引擎
engine = create_engine(
    str(settings.DATABASE_URL),  # Pydantic v2 需要转换为字符串
    pool_pre_ping=True,  # 自动检测断开的连接
    pool_size=10,
    max_overflow=20,
)

# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
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
    from app.models import user, project, task, annotation, annotation_draft

    Base.metadata.create_all(bind=engine)


