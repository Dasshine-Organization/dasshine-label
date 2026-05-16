# backend/app/api/v1/projects.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user, get_current_admin as require_admin
from app.models.user import User
from app.services.project_acl import can_administrate_project

router = APIRouter(prefix="/projects", tags=["projects"])


# ── helpers ───────────────────────────────────────────────────────────────────

def _to_summary(p: Project, db: Session) -> dict:
    schema = _get_schema(p)
    from app.models.project import ProjectMember
    member_count = db.query(ProjectMember).filter(ProjectMember.project_id == p.id).count()
    status_val = p.status.value if hasattr(p.status, "value") else str(p.status)
    return {
        "id": p.id,
        "name": p.name,
        "cover_color": schema.get("cover_color", "#00d4ff"),
        "category": schema.get("category"),
        "ann_type": schema.get("ann_type"),
        "status": status_val,
        "total_items": p.total_items or 0,
        "approved_items": p.approved_items or 0,
        "price_per_task": schema.get("price_per_task", 0.1),
        "member_count": member_count,
        "created_at": p.created_at,
    }


def _to_out(p: Project) -> dict:
    schema = _get_schema(p)
    status_val = p.status.value if hasattr(p.status, "value") else str(p.status)
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description or "",
        "cover_color": schema.get("cover_color", "#00d4ff"),
        "category": schema.get("category"),
        "ann_type": schema.get("ann_type"),
        "status": status_val,
        "dispatch_strategy": schema.get("dispatch_strategy", "smart"),
        "tasks_per_annotator": schema.get("tasks_per_annotator", 10),
        "cross_validate_count": schema.get("cross_validate_count", 1),
        "price_per_task": schema.get("price_per_task", 0.1),
        "auto_label_enabled": p.auto_label_enabled or False,
        "auto_label_model": p.auto_label_model,
        "auto_label_threshold": p.auto_label_threshold or 0.8,
        "total_items": p.total_items or 0,
        "labeled_items": p.labeled_items or 0,
        "approved_items": p.approved_items or 0,
        "created_at": p.created_at,
    }

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    type: str
    status: str
    total_items: int
    labeled_items: int
    approved_items: int
    progress: float
    created_at: datetime
    created_by_id: int

    class Config:
        from_attributes = True

# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ProjectService(db)
    project = svc.create(payload, current_user.id)
    return _to_out(project)


@router.get("")
def list_projects(
    skip: int = 0,
    limit: int = Query(50, le=200),
    status: Optional[str] = None,
    category: Optional[str] = None,
    my_projects: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ProjectService(db)
    user_id = current_user.id if (my_projects or not current_user.is_admin) else None
    projects = svc.list_all(skip=skip, limit=limit, status=status,
                            category=category, user_id=user_id)
    return [_to_summary(p, db) for p in projects]


@router.get("/{project_id}")
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return _to_out(project)


@router.patch("/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    svc = ProjectService(db)
    project = svc.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="仅管理员或项目所有者可修改项目")

    update_data = project_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    
    db.commit()
    db.refresh(project)
    return {"message": "更新成功", "project": project}


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """删除项目"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="仅管理员或项目所有者可删除项目")

    db.delete(project)
    db.commit()
    return {"message": "删除成功"}


@router.delete("/{project_id}/members/{user_id}")
def remove_member(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加项目成员"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not can_administrate_project(db, project, current_user):
        raise HTTPException(status_code=403, detail="仅管理员或项目所有者可添加成员")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    member = ProjectMember(
        project_id=project_id,
        user_id=user_id,
        role=role,
        can_assign=role in ["owner", "manager"],
        can_review=role in ["owner", "manager", "reviewer"],
        can_export=role in ["owner", "manager"]
    )
    db.add(member)
    db.commit()
    
    return {"message": "成员添加成功"}
