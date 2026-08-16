"""
任务分发服务 - 智能任务调度核心算法

核心功能：
1. 智能任务匹配 - 基于多维度评分选择最优标注员
2. 负载均衡 - 避免单个标注员过载
3. 防冲突机制 - 任务锁定防止重复分配
4. 主动学习 - 优先分发模型不确定的样本
"""

import random
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.models.user import User, AnnotatorLevel
from app.models.project import Project
from app.models.task import Task, TaskStatus
from app.core.config import settings
from app.core.exceptions import TaskDispatchError

logger = logging.getLogger(__name__)


@dataclass
class MatchScore:
    """匹配度评分结果"""
    user_id: int
    username: str
    total_score: float
    skill_score: float      # 技能匹配度 (0-1)
    quality_score: float    # 历史质量 (0-1)
    load_score: float       # 负载均衡 (0-1)
    speed_score: float      # 响应速度 (0-1)
    level_score: float      # 等级加成 (0-1)
    current_tasks: int      # 当前任务数
    max_capacity: int       # 最大容量


class TaskDispatchService:
    """任务分发服务"""
    
    # 权重配置（可动态调整）
    WEIGHTS = {
        'skill': 0.35,        # 技能匹配权重
        'quality': 0.25,      # 历史质量权重
        'load': 0.20,         # 负载均衡权重
        'speed': 0.10,        # 响应速度权重
        'level': 0.10,        # 等级加成权重
    }
    
    # 等级对应容量
    LEVEL_CAPACITY = {
        'novice': 10,         # 新手：最多10个任务
        'junior': 20,         # 初级：20个
        'intermediate': 30,   # 中级：30个
        'senior': 50,         # 高级：50个
        'expert': 80,         # 专家：80个
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def dispatch_tasks(
        self,
        project_id: int,
        batch_size: int = 100,
        strategy: str = "smart"
    ) -> List[Dict]:
        """
        批量分发任务 — 委托 ProjectService（与 UI 分发同一真源）。
        """
        from app.schemas.project_schemas import DispatchRequest, DispatchStrategy
        from app.services.project_service import ProjectService

        try:
            strat = DispatchStrategy(strategy)
        except ValueError:
            strat = DispatchStrategy.smart

        result = ProjectService(self.db).dispatch(
            project_id,
            DispatchRequest(batch_size=batch_size, strategy=strat),
            dispatcher_id=0,
        )
        return result.get("assignments") or []
    
    def _assign_task(
        self,
        task: Task,
        annotators: List[User],
        strategy: str
    ) -> Optional[Dict]:
        """
        为单个任务分配标注员
        
        Returns:
            分配结果或None
        """
        if not annotators:
            return None
        
        # 根据策略选择标注员
        if strategy == "smart":
            selected = self._smart_select(task, annotators)
        elif strategy == "random":
            selected = random.choice(annotators)
        elif strategy == "round_robin":
            selected = annotators[0]  # 简单轮询
        else:
            selected = self._smart_select(task, annotators)
        
        if not selected:
            return None
        
        # 锁定任务并分配
        try:
            return self._lock_and_assign(task, selected)
        except Exception as e:
            logger.error(f"任务分配失败: {e}")
            return None
    
    def _smart_select(self, task: Task, annotators: List[User]) -> Optional[User]:
        """
        智能选择最优标注员
        
        算法：
        1. 计算每个标注员的多维度匹配分数
        2. 加权求和得到总分
        3. 选择分数最高的标注员
        """
        scores: List[MatchScore] = []
        
        for annotator in annotators:
            # 检查是否还有容量
            current_tasks = self._get_current_task_count(annotator.id)
            level_key = (
                annotator.level.value
                if annotator.level and hasattr(annotator.level, "value")
                else (str(annotator.level) if annotator.level else "novice")
            )
            max_capacity = self.LEVEL_CAPACITY.get(level_key, 20)
            
            if current_tasks >= max_capacity:
                continue  # 已满负荷
            
            # 计算各维度分数
            skill_score = self._calculate_skill_match(task, annotator)
            quality_score = self._calculate_quality_score(annotator)
            load_score = self._calculate_load_score(current_tasks, max_capacity)
            speed_score = self._calculate_speed_score(annotator)
            level_score = self._calculate_level_score(annotator)
            
            # 加权总分
            total_score = (
                skill_score * self.WEIGHTS['skill'] +
                quality_score * self.WEIGHTS['quality'] +
                load_score * self.WEIGHTS['load'] +
                speed_score * self.WEIGHTS['speed'] +
                level_score * self.WEIGHTS['level']
            )
            
            scores.append(MatchScore(
                user_id=annotator.id,
                username=annotator.username,
                total_score=total_score,
                skill_score=skill_score,
                quality_score=quality_score,
                load_score=load_score,
                speed_score=speed_score,
                level_score=level_score,
                current_tasks=current_tasks,
                max_capacity=max_capacity
            ))
        
        if not scores:
            return None
        
        # 按总分排序，选最高分
        scores.sort(key=lambda x: x.total_score, reverse=True)
        best_match = scores[0]
        
        logger.debug(
            f"任务 {task.id} 最优匹配: {best_match.username} "
            f"(总分: {best_match.total_score:.3f}, "
            f"技能: {best_match.skill_score:.2f}, "
            f"质量: {best_match.quality_score:.2f})"
        )
        
        # 返回选中的标注员
        return self.db.query(User).filter(User.id == best_match.user_id).first()
    
    def _calculate_skill_match(self, task: Task, annotator: User) -> float:
        """
        计算技能匹配度
        
        基于：
        - 标注员技能标签与项目需求的匹配
        - 历史在该类型项目上的表现
        """
        if not annotator.skills:
            return 0.3  # 无技能标签，给基础分
        
        # 获取项目所需技能（从项目类型推断）
        project = task.project
        required_skills = self._get_required_skills(project)
        
        if not required_skills:
            return 0.8  # 无特殊要求，给高分
        
        # 计算匹配度
        annotator_skills = set(annotator.skills.split(',')) if annotator.skills else set()
        matched = len(annotator_skills & set(required_skills))
        total_required = len(required_skills)
        
        # 基础分0.3，每匹配一个技能加0.2
        score = 0.3 + (matched / total_required) * 0.7 if total_required > 0 else 0.5
        return min(score, 1.0)
    
    def _calculate_quality_score(self, annotator: User) -> float:
        """
        计算历史质量评分
        
        基于：
        - 准确率
        - 审核通过率
        - 返工率
        """
        if annotator.total_tasks == 0:
            # 新用户，给中等分数，鼓励参与
            return 0.6
        
        # 基础质量分
        accuracy = annotator.accuracy_score / 100.0
        
        # 完成率加成
        completion_rate = annotator.completed_tasks / annotator.total_tasks
        
        # 综合评分（准确率占70%，完成率占30%）
        score = accuracy * 0.7 + completion_rate * 0.3
        
        return max(0.1, min(score, 1.0))
    
    def _calculate_load_score(self, current: int, max_capacity: int) -> float:
        """
        计算负载均衡分数
        
        原则：负载越轻，分数越高，但避免过于倾斜
        """
        if max_capacity == 0:
            return 0.0
        
        load_ratio = current / max_capacity
        
        # 负载低于30%，满分
        if load_ratio < 0.3:
            return 1.0
        # 负载30-70%，线性递减
        elif load_ratio < 0.7:
            return 1.0 - (load_ratio - 0.3) * 1.5
        # 负载70-90%，快速递减
        elif load_ratio < 0.9:
            return 0.4 - (load_ratio - 0.7) * 1.5
        # 负载90%以上，极低分
        else:
            return 0.1
    
    def _calculate_speed_score(self, annotator: User) -> float:
        """
        计算响应速度评分
        
        基于平均任务完成时间
        """
        # 简化实现：基于效率评分
        efficiency = annotator.efficiency_score / 100.0 if annotator.efficiency_score else 0.5
        return max(0.3, efficiency)
    
    def _calculate_level_score(self, annotator: User) -> float:
        """
        计算等级加成
        
        高级标注员获得适当优先
        """
        level_bonus = {
            'novice': 0.5,
            'junior': 0.6,
            'intermediate': 0.75,
            'senior': 0.9,
            'expert': 1.0,
        }
        return level_bonus.get(annotator.level.value, 0.5)
    
    def _get_pending_tasks(self, project_id: int, limit: int) -> List[Task]:
        """获取待分配的任务"""
        return self.db.query(Task).filter(
            and_(
                Task.project_id == project_id,
                Task.status == TaskStatus.PENDING,
                Task.assignee_id.is_(None)
            )
        ).order_by(
            Task.priority.desc(),  # 优先级高的先分配
            Task.created_at.asc()   # 同优先级先进先出
        ).limit(limit).all()
    
    def _get_available_annotators(self, project_id: int) -> List[User]:
        """获取项目可用的标注员"""
        from app.models.project import ProjectMember
        
        # 查询项目成员中的标注员
        members = self.db.query(ProjectMember).filter(
            and_(
                ProjectMember.project_id == project_id,
                ProjectMember.role.in_(['annotator', 'manager', 'owner'])
            )
        ).all()
        
        if not members:
            return []
        
        user_ids = [m.user_id for m in members]
        
        # 获取活跃用户
        return self.db.query(User).filter(
            and_(
                User.id.in_(user_ids),
                User.status == 'active'
            )
        ).all()
    
    def _get_current_task_count(self, user_id: int) -> int:
        """获取用户当前进行中的任务数"""
        return self.db.query(Task).filter(
            and_(
                Task.assignee_id == user_id,
                Task.status.in_([
                    TaskStatus.ASSIGNED,
                    TaskStatus.ANNOTATING
                ])
            )
        ).count()
    
    def _get_required_skills(self, project: Project) -> List[str]:
        """获取项目所需技能"""
        # 从项目类型推断所需技能
        type_skills = {
            'text_classification': ['文本理解', '分类标注'],
            'ner': ['NER', '命名实体', '文本理解'],
            'image_classification': ['图像识别', '分类标注'],
            'object_detection': ['目标检测', '图像标注'],
            'ocr': ['OCR', '文本识别', '文档处理'],
            'legal': ['法律', '法律术语'],
            'medical': ['医疗', '医学术语'],
        }
        
        project_type = project.type.value if hasattr(project.type, 'value') else str(project.type)
        return type_skills.get(project_type, [])
    
    def _lock_and_assign(self, task: Task, annotator: User) -> Dict:
        """
        锁定任务并分配给标注员（claim 路径）。
        委托 ProjectService._assign_task_multi，写 TaskAssignment + metadata。
        """
        import uuid as uuid_lib
        from app.services.project_service import ProjectService

        batch_id = f"claim-{uuid_lib.uuid4().hex[:12]}"
        svc = ProjectService(self.db)
        # score 1.0 for self-claim
        added = svc._assign_task_multi(task, [(annotator, 1.0)], batch_id, cross_n=1)
        if not added:
            logger.warning(f"任务 {task.id} 已被分配")
            return None
        row = added[0]
        logger.info(f"任务 {task.id} 分配给 {annotator.username}")
        return {
            "task_id": row["task_id"],
            "user_id": row["user_id"],
            "username": row["username"],
            "assigned_at": row["assigned_at"],
        }
    
    def _update_annotator_cache(self, annotators: List[User], assigned_user_id: int):
        """更新标注员缓存（简单计数）"""
        for annotator in annotators:
            if annotator.id == assigned_user_id:
                # 临时增加计数（实际应从DB重新查询）
                if not hasattr(annotator, '_temp_task_count'):
                    annotator._temp_task_count = 0
                annotator._temp_task_count += 1
                break
    
    def release_task(self, task_id: int, reason: str = None) -> bool:
        """
        释放任务（标注员放弃或超时）
        
        Returns:
            是否成功释放
        """
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return False
        
        # 只有已分配但未完成的任务可以释放
        if task.status not in [TaskStatus.ASSIGNED, TaskStatus.ANNOTATING]:
            return False
        
        # 记录释放日志
        from app.models.task import TaskAssignment
        assignment_log = TaskAssignment(
            task_id=task_id,
            user_id=task.assignee_id,
            action='release',
            reason=reason or 'user_release'
        )
        self.db.add(assignment_log)
        
        # 重置任务状态
        task.assignee_id = None
        task.status = TaskStatus.PENDING
        task.assigned_at = None
        
        self.db.commit()
        
        logger.info(f"任务 {task_id} 已释放，原因: {reason}")
        return True
    
    def check_timeout_tasks(self, timeout_minutes: int = 30) -> int:
        """
        检查并回收超时任务
        
        Returns:
            回收的任务数
        """
        timeout_threshold = datetime.utcnow() - timedelta(minutes=timeout_minutes)
        
        timeout_tasks = self.db.query(Task).filter(
            and_(
                Task.status == TaskStatus.ASSIGNED,
                Task.assigned_at < timeout_threshold
            )
        ).all()
        
        released_count = 0
        for task in timeout_tasks:
            if self.release_task(task.id, 'timeout'):
                released_count += 1
        
        if released_count > 0:
            logger.info(f"回收 {released_count} 个超时任务")
        
        return released_count


class ActiveLearningDispatch(TaskDispatchService):
    """
    主动学习任务分发
    
    优先分发对模型提升最有价值的样本
    """
    
    def get_high_value_tasks(self, project_id: int, limit: int = 100) -> List[Task]:
        """
        获取高价值任务（主动学习）
        
        价值标准：
        1. 模型置信度低（不确定性高）
        2. 与已标注样本差异大（多样性）
        3. 潜在错误标签（预测与预标注不一致）
        """
        return self.db.query(Task).filter(
            and_(
                Task.project_id == project_id,
                Task.status == TaskStatus.PENDING,
                or_(
                    # 低置信度
                    Task.pre_label_confidence < 0.6,
                    # 无预标注（需要人工）
                    Task.pre_label_confidence.is_(None)
                )
            )
        ).order_by(
            Task.pre_label_confidence.asc().nullsfirst(),
            Task.priority.desc()
        ).limit(limit).all()


def get_dispatch_service(db: Session) -> TaskDispatchService:
    """获取任务分发服务实例"""
    return TaskDispatchService(db)
