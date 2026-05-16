"""
项目标签类（写入 project.annotation_schema['label_classes']）及当前用户权限摘要。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models.project import Project
from app.models.user import User, UserRole
from app.services.project_acl import (
    can_delete_project_label_class,
    can_edit_project_label_classes,
    get_project_member,
    is_project_owner_user,
)

router = APIRouter()

LABEL_CLASSES_KEY = "label_classes"


class LabelClassItem(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    color: str = Field(..., min_length=1)
    hotkey: Optional[str] = None


class LabelClassesBody(BaseModel):
    label_classes: List[LabelClassItem] = Field(default_factory=list)


class ProjectMembershipCapabilities(BaseModel):
    project_id: int
    user_id: int
    member_role: Optional[str] = None
    is_project_owner: bool
    is_super_admin: bool
    can_edit_label_classes: bool
    can_delete_label_classes: bool


def _schema_copy(project: Project) -> Dict[str, Any]:
    return dict(project.annotation_schema or {})


def _items_to_body(items: List[Dict[str, Any]]) -> LabelClassesBody:
    parsed: List[LabelClassItem] = []
    for x in items:
        if not isinstance(x, dict):
            continue
        parsed.append(
            LabelClassItem(
                id=str(x.get("id", "")),
                name=str(x.get("name", "")),
                color=str(x.get("color", "#94a3b8")),
                hotkey=x.get("hotkey") if x.get("hotkey") else None,
            )
        )
    return LabelClassesBody(label_classes=parsed)


@router.get("/projects/{project_id}/my-label-capabilities", response_model=ProjectMembershipCapabilities)
def my_label_capabilities(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    m = get_project_member(db, project_id, current_user.id)
    is_owner = is_project_owner_user(project, m, current_user)
    is_super = current_user.role == UserRole.SUPER_ADMIN
    return ProjectMembershipCapabilities(
        project_id=project_id,
        user_id=current_user.id,
        member_role=m.role if m else None,
        is_project_owner=is_owner,
        is_super_admin=is_super,
        can_edit_label_classes=can_edit_project_label_classes(db, project, current_user),
        can_delete_label_classes=can_delete_project_label_class(db, project, current_user),
    )


@router.get("/projects/{project_id}/label-classes", response_model=LabelClassesBody)
def get_label_classes(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    m = get_project_member(db, project_id, current_user.id)
    if not m and current_user.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        raise HTTPException(status_code=403, detail="非项目成员")
    items = _get_label_classes(project)
    return _items_to_body(items)


def _normalize_items(items: List[LabelClassItem]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for it in items:
        d: Dict[str, Any] = {"id": it.id, "name": it.name.strip(), "color": it.color}
        if it.hotkey:
            d["hotkey"] = it.hotkey
        if not d["name"]:
            raise HTTPException(status_code=400, detail="标签名称不能为空")
        out.append(d)
    names = [x["name"] for x in out]
    if len(names) != len(set(names)):
        raise HTTPException(status_code=400, detail="标签名称不能重复")
    if len(out) < 1:
        raise HTTPException(status_code=400, detail="至少保留一个标签类")
    return out


@router.put("/projects/{project_id}/label-classes", response_model=LabelClassesBody)
def put_label_classes(
    project_id: int,
    body: LabelClassesBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_edit_project_label_classes(db, project, current_user):
        raise HTTPException(status_code=403, detail="无权修改项目标签类")

    normalized = _normalize_items(body.label_classes)
    schema = _schema_copy(project)
    schema[LABEL_CLASSES_KEY] = normalized
    project.annotation_schema = schema
    db.commit()
    db.refresh(project)
    return _items_to_body(normalized)


@router.delete("/projects/{project_id}/label-classes/{label_id}")
def delete_label_class(
    project_id: int,
    label_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_delete_project_label_class(db, project, current_user):
        raise HTTPException(status_code=403, detail="仅超级管理员或项目所有者可删除标签类")

    items = _get_label_classes(project)
    if len(items) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个标签类")
    new_items = [x for x in items if str(x.get("id")) != label_id]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="未找到该标签类")
    if not new_items:
        raise HTTPException(status_code=400, detail="至少保留一个标签类")

    schema = _schema_copy(project)
    schema[LABEL_CLASSES_KEY] = new_items
    project.annotation_schema = schema
    db.commit()
    return {"message": "已删除", "label_classes": new_items}
