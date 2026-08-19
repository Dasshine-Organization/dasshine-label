"""
任务管理API
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field

from app.api.deps import get_db, get_current_user, get_current_admin
from app.models.user import User
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.project import Project
from app.services.task_dispatch import TaskDispatchService, get_dispatch_service
from app.services.project_acl import is_task_assignee
from app.core.exceptions import raise_not_found, raise_bad_request
from sqlalchemy import or_, text

router = APIRouter()


# ============ 请求/响应模型 ============

class TaskCreate(BaseModel):
    """创建任务请求"""
    project_id: int
    data: dict = Field(..., description="任务数据")
    data_url: Optional[str] = Field(None, description="数据文件URL")
    task_metadata: Optional[dict] = Field(None, description="元数据")
    priority: int = Field(default=5, ge=1, le=10)


class TaskResponse(BaseModel):
    """任务响应"""
    id: int
    project_id: int
    status: str
    priority: int
    assignee_id: Optional[int]
    assignee_name: Optional[str]
    pre_label_confidence: Optional[float]
    created_at: str
    
    class Config:
        from_attributes = True


class TaskDispatchRequest(BaseModel):
    """任务分发请求"""
    project_id: int
    batch_size: int = Field(default=100, ge=1, le=500)
    strategy: str = Field(default="smart", pattern="^(smart|random|round_robin)$")


class TaskDispatchResponse(BaseModel):
    """任务分发响应"""
    success: bool
    assigned_count: int
    assignments: List[dict]


class TaskClaimRequest(BaseModel):
    """领取任务请求"""
    project_id: Optional[int] = None


class TaskSubmitRequest(BaseModel):
    """提交标注请求"""
    result: dict = Field(..., description="标注结果")
    work_time: int = Field(..., description="工作时长(秒)", ge=0)


class TaskReviewRequest(BaseModel):
    """审核任务请求"""
    decision: str = Field(..., pattern="^(approved|rejected)$")
    feedback: Optional[str] = None
    score: Optional[float] = Field(None, ge=0, le=100)


# ============ API端点 ============

from app.services.task_serializer import task_list_item as _task_list_item


@router.get("/tasks", response_model=List[TaskResponse])
def list_tasks(
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取任务列表
    
    - 管理员：查看所有任务（有 active_org 时按组织收窄）
    - 标注员：自己的任务 + 当前组织下可领取的 PENDING
    """
    from app.services.org_scope import ensure_active_org_id

    query = (
        db.query(Task)
        .options(
            joinedload(Task.project),
            joinedload(Task.assignee),
        )
        .join(Project, Project.id == Task.project_id)
    )

    active_org = ensure_active_org_id(db, current_user)

    # 非管理员：自己的任务（含交叉共标）+ 当前组织可领取的待分派任务
    if not current_user.is_admin:
        uid = current_user.id
        pending_org = (Task.status == TaskStatus.PENDING) & (Task.assignee_id.is_(None))
        if active_org is not None:
            pending_org = pending_org & (Project.organization_id == active_org)
        else:
            pending_org = pending_org & False  # 无组织则不可见公共池
        query = query.filter(
            or_(
                Task.assignee_id == uid,
                text(
                    "(tasks.metadata->'assignee_ids') @> to_jsonb(:uid::int)"
                ).bindparams(uid=uid),
                text(
                    "(tasks.metadata->'co_assignee_ids') @> to_jsonb(:cuid::int)"
                ).bindparams(cuid=uid),
                pending_org,
            )
        )
    elif active_org is not None:
        query = query.filter(Project.organization_id == active_org)
    
    # 筛选条件
    if project_id:
        query = query.filter(Task.project_id == project_id)
    if status:
        query = query.filter(Task.status == status)
    
    # 分页
    total = query.count()
    tasks = query.offset((page - 1) * page_size).limit(page_size).all()
    
    from app.services.project_service import _get_schema

    return [
        _task_list_item(task, _get_schema(task.project) if task.project else {})
        for task in tasks
    ]


@router.get("/tasks/available")
def get_available_tasks(
    project_id: Optional[int] = None,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取可领取的任务列表
    
    标注员调用此接口查看可接的任务（默认按当前组织过滤）
    """
    from app.models.project import Project
    from app.services.organization_service import OrganizationService
    from app.services.project_service import _get_schema

    query = (
        db.query(Task)
        .options(joinedload(Task.project), joinedload(Task.assignee))
        .join(Project, Project.id == Task.project_id)
        .filter(Task.status == TaskStatus.PENDING, Task.assignee_id.is_(None))
    )

    if project_id:
        query = query.filter(Task.project_id == project_id)
    elif not current_user.is_admin:
        org_svc = OrganizationService(db)
        org_svc.ensure_personal_org(current_user)
        if current_user.active_org_id:
            query = query.filter(Project.organization_id == current_user.active_org_id)

    # 轻量黄金题优先：按项目 quality_config.golden_claim_ratio 概率把黄金题提到前面
    tasks = query.order_by(Task.is_golden.desc(), Task.priority.desc()).limit(limit * 2).all()
    prefer_golden: List[Task] = []
    normal: List[Task] = []
    import random

    for t in tasks:
        qc = (t.project.quality_config if t.project else None) or {}
        ratio = float(qc.get("golden_claim_ratio") or 0)
        if t.is_golden and ratio > 0 and random.random() < ratio:
            prefer_golden.append(t)
        else:
            normal.append(t)
    ordered = (prefer_golden + normal)[:limit]

    return [
        _task_list_item(task, _get_schema(task.project) if task.project else {})
        for task in ordered
    ]


@router.post("/tasks/claim-next")
def claim_next_task(
    project_id: Optional[int] = None,
    prefer_active_learning: bool = Query(False, description="优先领取主动学习池任务"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """领取下一题：从可领池取一条并 claim（跳过本人已 skip 的）。"""
    from app.models.project import Project
    from app.services.guidelines import ensure_guidelines_acked, get_member_streak
    from app.services.org_scope import project_visible_in_active_org
    from app.services.organization_service import OrganizationService
    from app.services.project_service import _get_schema

    query = (
        db.query(Task)
        .options(joinedload(Task.project), joinedload(Task.assignee))
        .join(Project, Project.id == Task.project_id)
        .filter(Task.status == TaskStatus.PENDING, Task.assignee_id.is_(None))
    )
    if project_id:
        query = query.filter(Task.project_id == project_id)
    elif not current_user.is_admin:
        org_svc = OrganizationService(db)
        org_svc.ensure_personal_org(current_user)
        if current_user.active_org_id:
            query = query.filter(Project.organization_id == current_user.active_org_id)

    candidates = query.order_by(Task.priority.desc(), Task.id.asc()).limit(40).all()

    if prefer_active_learning and project_id:
        from app.services.active_learning import pool_task_ids

        pool_ids = set(pool_task_ids(db, project_id))
        if pool_ids:
            in_pool = [t for t in candidates if t.id in pool_ids]
            rest = [t for t in candidates if t.id not in pool_ids]
            candidates = in_pool + rest
    elif project_id:
        proj = db.query(Project).filter(Project.id == project_id).first()
        qc = proj.quality_config if proj and isinstance(proj.quality_config, dict) else {}
        if qc.get("active_learning_prefer_claim"):
            from app.services.active_learning import pool_task_ids

            pool_ids = set(pool_task_ids(db, project_id))
            if pool_ids:
                in_pool = [t for t in candidates if t.id in pool_ids]
                rest = [t for t in candidates if t.id not in pool_ids]
                candidates = in_pool + rest

    for task in candidates:
        if not task.project:
            continue
        if not project_visible_in_active_org(db, task.project, current_user):
            continue
        ack_err = ensure_guidelines_acked(db, task.project, current_user)
        if ack_err:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ack_err)
        qc = task.project.quality_config if isinstance(task.project.quality_config, dict) else {}
        try:
            fail_th = int(qc.get("golden_fail_threshold") or 5)
        except (TypeError, ValueError):
            fail_th = 5
        if get_member_streak(db, task.project_id, current_user.id) >= fail_th:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"连续黄金题失败已暂停领取（阈值 {fail_th}）",
            )
        meta = dict(task.task_metadata or {})
        skipped = meta.get("skipped_by_user_ids") or []
        if current_user.id in skipped or str(current_user.id) in [str(x) for x in skipped]:
            continue

        dispatch_service = get_dispatch_service(db)
        current_count = dispatch_service._get_current_task_count(current_user.id)
        max_capacity = dispatch_service.LEVEL_CAPACITY.get(
            _annotator_level_key(current_user), 20
        )
        if current_count >= max_capacity:
            raise_bad_request(f"您当前已有{current_count}个进行中的任务，达到上限")
        assignment = dispatch_service._lock_and_assign(task, current_user)
        if not assignment:
            continue
        task = (
            db.query(Task)
            .options(joinedload(Task.project), joinedload(Task.assignee))
            .filter(Task.id == task.id)
            .first()
        )
        schema = _get_schema(task.project) if task and task.project else {}
        return {"success": True, "task": _task_list_item(task, schema)}

    raise HTTPException(status_code=404, detail="暂无可领取任务")


@router.post("/tasks/{task_id}/skip")
def skip_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """跳过当前题：释放回领取池，并记录本用户已跳过。"""
    from app.services.project_service import _get_schema

    task = (
        db.query(Task)
        .options(joinedload(Task.project), joinedload(Task.assignee))
        .filter(Task.id == task_id)
        .first()
    )
    if not task:
        raise_not_found("任务不存在")
    if not is_task_assignee(task, current_user) and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权跳过此任务")

    meta = dict(task.task_metadata or {})
    skipped = list(meta.get("skipped_by_user_ids") or [])
    if current_user.id not in skipped and str(current_user.id) not in [str(x) for x in skipped]:
        skipped.append(current_user.id)
    meta["skipped_by_user_ids"] = skipped
    from datetime import datetime, timezone

    meta["last_skipped_at"] = datetime.now(timezone.utc).isoformat()
    task.task_metadata = meta
    task.assignee_id = None
    task.status = TaskStatus.PENDING
    try:
        task.priority = max(1, int(task.priority or 5) - 1)
    except (TypeError, ValueError):
        pass
    db.commit()
    schema = _get_schema(task.project) if task.project else {}
    return {"success": True, "message": "已跳过，任务退回领取池", "task": _task_list_item(task, schema)}


@router.get("/tasks/{task_id}")
def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取任务详情（含 data_url，供标注页加载图像）"""
    from app.services.project_acl import can_access_task_workspace
    from app.services.project_service import _get_schema

    task = (
        db.query(Task)
        .options(joinedload(Task.project), joinedload(Task.assignee))
        .filter(Task.id == task_id)
        .first()
    )
    if not task:
        raise_not_found("任务不存在")

    if not current_user.is_admin and not can_access_task_workspace(db, task, current_user):
        if task.assignee_id != current_user.id and task.status != TaskStatus.PENDING:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该任务")

    schema = _get_schema(task.project) if task.project else {}
    item = _task_list_item(task, schema)
    item["data"] = task.data or {}
    meta = dict(task.task_metadata or {})
    # Blind: never expose golden_scores / answers to non-reviewers
    from app.services.golden_blind import can_see_golden, maybe_attach_golden_fields

    if not can_see_golden(db, task, current_user):
        meta.pop("golden_scores", None)
    # Annotators can see reject feedback/targets after reject
    item["task_metadata"] = meta
    item["pre_label_result"] = task.pre_label_result
    item = maybe_attach_golden_fields(db, task, current_user, item)
    return item


def _annotator_level_key(user: User) -> str:
    if user.level is None:
        return "novice"
    return user.level.value if hasattr(user.level, "value") else str(user.level)


@router.post("/tasks/{task_id}/claim")
def claim_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    领取任务
    
    标注员主动领取待分配任务（须属于当前组织）
    """
    from app.services.org_scope import project_visible_in_active_org
    from app.services.project_service import _get_schema

    task = (
        db.query(Task)
        .options(joinedload(Task.project), joinedload(Task.assignee))
        .filter(Task.id == task_id)
        .first()
    )
    if not task:
        raise_not_found("任务不存在")

    if not task.project or not project_visible_in_active_org(db, task.project, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权领取其他组织的任务",
        )

    if task.status != TaskStatus.PENDING or task.assignee_id:
        raise_bad_request("任务已被领取或不可领取")

    # P17：连续黄金题失败暂停领取
    from app.services.guidelines import ensure_guidelines_acked, get_member_streak

    if task.project:
        ack_err = ensure_guidelines_acked(db, task.project, current_user)
        if ack_err:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ack_err)
        qc = task.project.quality_config if isinstance(task.project.quality_config, dict) else {}
        try:
            fail_th = int(qc.get("golden_fail_threshold") or 5)
        except (TypeError, ValueError):
            fail_th = 5
        streak = get_member_streak(db, task.project_id, current_user.id)
        if streak >= fail_th:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"连续 {streak} 道黄金题未通过，已暂停领取（阈值 {fail_th}），请联系管理员",
            )

    dispatch_service = get_dispatch_service(db)
    current_count = dispatch_service._get_current_task_count(current_user.id)
    max_capacity = dispatch_service.LEVEL_CAPACITY.get(
        _annotator_level_key(current_user), 20
    )

    if current_count >= max_capacity:
        raise_bad_request(f"您当前已有{current_count}个进行中的任务，达到上限")

    assignment = dispatch_service._lock_and_assign(task, current_user)
    if not assignment:
        raise_bad_request("任务领取失败，请重试")

    task = (
        db.query(Task)
        .options(joinedload(Task.project), joinedload(Task.assignee))
        .filter(Task.id == task_id)
        .first()
    )
    schema = _get_schema(task.project) if task and task.project else {}
    return _task_list_item(task, schema)


@router.post("/tasks/{task_id}/start")
def start_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """开始标注任务"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise_not_found("任务不存在")
    
    if not is_task_assignee(task, current_user) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作此任务"
        )
    
    if task.status not in (TaskStatus.ASSIGNED, TaskStatus.ANNOTATING):
        raise_bad_request("任务状态不正确")
    
    from datetime import datetime
    if task.status == TaskStatus.ASSIGNED:
        task.status = TaskStatus.ANNOTATING
        task.started_at = datetime.utcnow()
        db.commit()
    
    return {"success": True, "message": "任务开始", "started_at": task.started_at}


@router.post("/tasks/{task_id}/submit")
def submit_task(
    task_id: int,
    request: TaskSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """提交标注结果（交叉共标：满 N 人后才 SUBMITTED）"""
    import uuid
    from datetime import datetime, timezone
    from app.models.annotation import Annotation, AnnotationStatus, AnnotationType
    from app.services.task_completion import after_annotation_submit

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise_not_found("任务不存在")
    
    if not is_task_assignee(task, current_user) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作此任务"
        )
    
    if task.status not in [TaskStatus.ANNOTATING, TaskStatus.ASSIGNED]:
        raise_bad_request("任务状态不正确")
    
    existing = (
        db.query(Annotation)
        .filter(
            Annotation.task_id == task_id,
            Annotation.annotator_id == current_user.id,
            Annotation.is_latest.is_(True),
        )
        .first()
    )
    if existing:
        existing.data = request.result
        existing.work_time = request.work_time
        existing.version += 1
        annotation = existing
    else:
        annotation = Annotation(
            id=str(uuid.uuid4()),
            task_id=task_id,
            data_id=str(task_id),
            annotation_type=AnnotationType.TEXT,
            data=request.result,
            status=AnnotationStatus.COMPLETED,
            annotator_id=current_user.id,
            work_time=request.work_time,
            is_latest=True,
        )
        db.add(annotation)

    progress = after_annotation_submit(
        db, task, current_user.id, request.result, work_time=request.work_time
    )
    current_user.completed_tasks = (current_user.completed_tasks or 0) + 1
    db.commit()
    
    return {
        "success": True,
        "message": "提交成功" if progress["fully_submitted"] else f"已提交（{progress['done']}/{progress['need']}）",
        "annotation_id": annotation.id,
        "task_status": progress["task_status"],
        "submit_progress": {"done": progress["done"], "need": progress["need"]},
    }


@router.post("/tasks/dispatch", response_model=TaskDispatchResponse)
def dispatch_tasks(
    request: TaskDispatchRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    触发任务分发（管理员）— 委托 ProjectService（与项目分发 UI 同一真源）。
    """
    from app.schemas.project_schemas import DispatchRequest, DispatchStrategy
    from app.services.project_service import ProjectService

    try:
        strat = DispatchStrategy(request.strategy)
    except ValueError:
        strat = DispatchStrategy.smart

    result = ProjectService(db).dispatch(
        request.project_id,
        DispatchRequest(batch_size=request.batch_size, strategy=strat),
        dispatcher_id=current_user.id,
    )
    return {
        "success": bool(result.get("success", True)),
        "assigned_count": result.get("assigned_count", 0),
        "assignments": result.get("assignments") or [],
    }


@router.post("/tasks/auto-dispatch")
def auto_dispatch(
    project_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    自动分发（简化版）
    
    一键分发项目的所有待处理任务
    """
    service = get_dispatch_service(db)
    
    # 获取项目的所有待分配任务
    pending_count = db.query(Task).filter(
        Task.project_id == project_id,
        Task.status == TaskStatus.PENDING
    ).count()
    
    if pending_count == 0:
        return {"success": True, "message": "没有待分配的任务", "assigned": 0}
    
    # 批量分发
    assignments = service.dispatch_tasks(
        project_id=project_id,
        batch_size=min(pending_count, 500),
        strategy="smart"
    )
    
    return {
        "success": True,
        "message": f"成功分配 {len(assignments)}/{pending_count} 个任务",
        "assigned": len(assignments),
        "pending": pending_count - len(assignments)
    }


@router.post("/tasks/release/{task_id}")
def release_task(
    task_id: int,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    放弃/释放任务
    
    标注员主动放弃已领取但未完成的任务
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise_not_found("任务不存在")
    
    # 只能释放自己的任务
    if task.assignee_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权释放此任务"
        )
    
    service = get_dispatch_service(db)
    success = service.release_task(task_id, reason or "user_release")
    
    if success:
        return {"success": True, "message": "任务已释放"}
    else:
        raise_bad_request("任务释放失败")


@router.get("/tasks/{task_id}/lock")
def get_task_lock(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询任务标注占用锁状态"""
    from app.services.task_lock_service import TaskLockService

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise_not_found("任务不存在")
    return TaskLockService(db).status(task_id)


@router.post("/tasks/{task_id}/lock")
def acquire_task_lock(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取或刷新任务标注占用锁（心跳同接口：已持有则续期）"""
    from app.services.task_lock_service import TaskLockService

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise_not_found("任务不存在")
    svc = TaskLockService(db)
    result = svc.acquire(task, current_user)
    if result.get("acquired"):
        return result
    # 未抢到：若调用方已是持有人则 heartbeat；否则返回占用信息
    hb = svc.heartbeat(task_id, current_user)
    if hb.get("ok"):
        st = svc.status(task_id)
        st["acquired"] = True
        return st
    return result


@router.delete("/tasks/{task_id}/lock")
def release_task_lock(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """释放任务标注占用锁"""
    from app.services.task_lock_service import TaskLockService

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise_not_found("任务不存在")
    ok = TaskLockService(db).release(task_id, current_user)
    if not ok:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权释放此锁")
    return {"ok": True, "task_id": task_id}


@router.get("/tasks/stats/{project_id}")
def get_task_stats(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取项目任务统计"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise_not_found("项目不存在")
    
    # 统计各状态任务数
    from sqlalchemy import func
    
    stats = db.query(
        Task.status,
        func.count(Task.id).label('count')
    ).filter(
        Task.project_id == project_id
    ).group_by(Task.status).all()
    
    status_count = {str(s.status): s.count for s in stats}
    
    return {
        "project_id": project_id,
        "total": sum(status_count.values()),
        "pending": status_count.get('pending', 0),
        "assigned": status_count.get('assigned', 0),
        "annotating": status_count.get('annotating', 0),
        "submitted": status_count.get('submitted', 0),
        "reviewing": status_count.get('reviewing', 0),
        "approved": status_count.get('approved', 0),
        "by_status": status_count
    }


@router.post("/tasks/check-timeout")
def check_timeout_tasks(
    timeout_minutes: int = 30,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    检查并回收超时任务（管理员）
    
    回收长时间未处理的任务
    """
    service = get_dispatch_service(db)
    released = service.check_timeout_tasks(timeout_minutes)
    
    return {
        "success": True,
        "released_count": released,
        "timeout_minutes": timeout_minutes
    }
