"""
任务管理API
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, get_current_user, get_current_admin
from app.models.user import User
from app.models.task import Task, TaskStatus, TaskPriority
from app.models.project import Project
from app.services.task_dispatch import TaskDispatchService, get_dispatch_service
from app.core.exceptions import raise_not_found, raise_bad_request

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
    
    - 管理员：查看所有任务
    - 标注员：查看自己相关的任务
    """
    from sqlalchemy.orm import joinedload

    query = db.query(Task).options(joinedload(Task.project))
    
    # 非管理员只能看自己的
    if not current_user.is_admin:
        query = query.filter(Task.assignee_id == current_user.id)
    
    # 筛选条件
    if project_id:
        query = query.filter(Task.project_id == project_id)
    if status:
        query = query.filter(Task.status == status)
    
    # 分页
    total = query.count()
    tasks = query.offset((page - 1) * page_size).limit(page_size).all()
    
    # 转换为响应格式
    result = []
    from app.services.project_service import _get_schema

    for task in tasks:
        assignee_name = None
        if task.assignee:
            assignee_name = task.assignee.username
        schema = _get_schema(task.project) if task.project else {}
        category = schema.get("category")
        ann_type = schema.get("ann_type")
        result.append({
            "id": task.id,
            "project_id": task.project_id,
            "project": task.project.name if task.project else "",
            "category": category,
            "ann_type": ann_type,
            "type": ann_type or (task.project.type.value if task.project and hasattr(task.project.type, "value") else ""),
            "status": task.status.value if hasattr(task.status, 'value') else task.status,
            "priority": task.priority,
            "assignee_id": task.assignee_id,
            "assignee_name": assignee_name,
            "pre_label_confidence": task.pre_label_confidence,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "reward": schema.get("price_per_task", 0.1),
        })
    
    return result


@router.get("/tasks/available", response_model=List[TaskResponse])
def get_available_tasks(
    project_id: Optional[int] = None,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取可领取的任务列表
    
    标注员调用此接口查看可接的任务
    """
    query = db.query(Task).filter(
        Task.status == TaskStatus.PENDING,
        Task.assignee_id.is_(None)
    )
    
    if project_id:
        query = query.filter(Task.project_id == project_id)
    
    tasks = query.order_by(Task.priority.desc()).limit(limit).all()
    
    return tasks


@router.post("/tasks/{task_id}/claim", response_model=TaskResponse)
def claim_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    领取任务
    
    标注员主动领取待分配任务
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise_not_found("任务不存在")
    
    if task.status != TaskStatus.PENDING or task.assignee_id:
        raise_bad_request("任务已被领取或不可领取")
    
    # 检查用户容量
    dispatch_service = get_dispatch_service(db)
    current_count = dispatch_service._get_current_task_count(current_user.id)
    max_capacity = dispatch_service.LEVEL_CAPACITY.get(
        current_user.level.value, 20
    )
    
    if current_count >= max_capacity:
        raise_bad_request(f"您当前已有{current_count}个进行中的任务，达到上限")
    
    # 分配任务
    assignment = dispatch_service._lock_and_assign(task, current_user)
    if not assignment:
        raise_bad_request("任务领取失败，请重试")
    
    db.refresh(task)
    return task


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
    
    # 检查权限
    if task.assignee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作此任务"
        )
    
    if task.status != TaskStatus.ASSIGNED:
        raise_bad_request("任务状态不正确")
    
    from datetime import datetime
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
    """提交标注结果"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise_not_found("任务不存在")
    
    if task.assignee_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权操作此任务"
        )
    
    if task.status not in [TaskStatus.ANNOTATING, TaskStatus.ASSIGNED]:
        raise_bad_request("任务状态不正确")
    
    # 创建标注记录
    from app.models.task import Annotation
    from datetime import datetime
    
    annotation = Annotation(
        task_id=task_id,
        annotator_id=current_user.id,
        result=request.result,
        started_at=task.started_at or task.assigned_at,
        completed_at=datetime.utcnow(),
        work_time=request.work_time,
        is_final=True
    )
    db.add(annotation)
    
    # 更新任务状态
    task.status = TaskStatus.SUBMITTED
    task.submitted_at = datetime.utcnow()
    task.work_time = request.work_time
    
    # 更新用户统计
    current_user.completed_tasks += 1
    
    db.commit()
    
    return {
        "success": True,
        "message": "提交成功",
        "annotation_id": annotation.id
    }


@router.post("/tasks/dispatch", response_model=TaskDispatchResponse)
def dispatch_tasks(
    request: TaskDispatchRequest,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    触发任务分发（管理员）
    
    批量分配待处理任务给标注员
    """
    service = get_dispatch_service(db)
    
    assignments = service.dispatch_tasks(
        project_id=request.project_id,
        batch_size=request.batch_size,
        strategy=request.strategy
    )
    
    return {
        "success": True,
        "assigned_count": len(assignments),
        "assignments": assignments
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
