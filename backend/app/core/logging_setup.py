"""应用日志初始化。"""

from __future__ import annotations

import logging
import sys

from app.core.config import settings


def setup_logging() -> None:
    level = getattr(logging, (settings.LOG_LEVEL or "INFO").upper(), logging.INFO)
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(level)

    # 降低嘈杂第三方日志
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DEBUG else logging.WARNING
    )
