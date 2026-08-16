"""
Celery配置 - 异步任务队列

用于：
1. 自动标注（耗时操作）
2. 数据导出
3. 批量处理
4. 定时任务（超时检查等）
"""

from celery import Celery
from app.core.config import settings

# 创建Celery应用
celery_app = Celery(
    "dasshine_label",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.auto_label_tasks",
        "app.tasks.export_tasks",
        "app.tasks.quality_tasks",
    ]
)

# 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,
    
    # 任务结果过期时间
    result_expires=3600,
    
    # 任务执行超时（大包导出可超过 5 分钟）
    task_time_limit=1800,  # 30 分钟
    task_soft_time_limit=1500,
    
    # 并发配置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


# 定时任务配置
celery_app.conf.beat_schedule = {
    # 每5分钟检查超时任务
    "check-timeout-tasks": {
        "task": "app.tasks.quality_tasks.check_timeout_tasks",
        "schedule": 300.0,  # 5分钟
    },
}
