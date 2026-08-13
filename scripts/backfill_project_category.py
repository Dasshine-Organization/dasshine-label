#!/usr/bin/env python3
"""将 annotation_schema 中的 category/ann_type 回填到 projects 列字段。

用法:
  python scripts/backfill_project_category.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.database import SessionLocal
from app.models.project import Project
from app.services.project_service import (
    _get_schema,
    _resolve_project_ann_type,
    _resolve_project_category,
)


def main() -> None:
    from app.models import user, project, task, annotation, annotation_draft, embodied  # noqa: F401

    db = SessionLocal()
    updated = 0
    try:
        for p in db.query(Project).all():
            cat = _resolve_project_category(p)
            ann = _resolve_project_ann_type(p)
            schema = _get_schema(p)
            changed = False
            if cat and p.category != cat:
                p.category = cat
                changed = True
            if ann and p.ann_type != ann:
                p.ann_type = ann
                changed = True
            # 同步写回 schema，保证双写一致
            if cat and schema.get("category") != cat:
                schema["category"] = cat
                changed = True
            if ann and schema.get("ann_type") != ann:
                schema["ann_type"] = ann
                changed = True
            if changed:
                p.annotation_schema = schema
                updated += 1
        db.commit()
        print(f"backfilled projects: {updated}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
