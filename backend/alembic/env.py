"""
Alembic 环境配置
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from app.core.config import settings
from app.models.base import Base

# 导入全部模型，保证 metadata 完整（与 database.init_db 对齐）
from app.models import (  # noqa: F401
    user,
    project,
    task,
    annotation,
    annotation_draft,
    embodied,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
