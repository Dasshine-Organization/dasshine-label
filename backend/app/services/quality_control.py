"""
质量控制服务 - 交叉验证、黄金标准、质量评分

核心功能：
1. 交叉验证 - 多个标注员同一条数据的比对
2. 黄金标准 - 测试题机制
3. 一致性计算 - Kappa系数、Fleiss Kappa
4. 质量评分 - 标注员能力评估
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.task import Task, TaskStatus, Review
from app.models.annotation import Annotation
from app.models.user import User, AnnotatorLevel
from app.models.project import Project

logger = logging.getLogger(__name__)


@dataclass
class AgreementResult:
    """一致性结果"""
    task_id: int
    annotator_count: int                      # 标注人数
    agreement_rate: float                     # 一致率 0-1
    kappa_score: float                        # Kappa系数
    is_golden: bool                           # 是否为黄金标准题
    golden_accuracy: Optional[float] = None   # 黄金题准确率


@dataclass
class QualityScore:
    """质量评分"""
    user_id: int
    username: str
    accuracy: float           # 准确率
    consistency: float        # 一致性
    efficiency: float         # 效率分
    overall_score: float      # 综合评分
    level: AnnotatorLevel     # 当前等级
    suggested_level: AnnotatorLevel  # 建议等级


class QualityControlService:
    """质量控制服务"""
    
    # 一致性阈值
    MIN_AGREEMENT_THRESHOLD = 0.8    # 最小一致率
    KAPPA_THRESHOLD = 0.6            # Kappa阈值
    
    # 黄金标准题比例
    GOLDEN_RATIO = 0.1               # 10% 测试题
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_cross_validation(self, task_id: int) -> Optional[AgreementResult]:
        """
        计算任务的交叉验证结果
        
        当多个标注员标注同一任务时，计算他们的一致性
        """
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return None
        
        # 获取所有最新标注结果（按标注员去重取最新）
        annotations = self.db.query(Annotation).filter(
            Annotation.task_id == task_id,
            Annotation.is_latest == True,
        ).all()

        # 同一 annotator 多条时保留最新一条
        by_user: Dict[int, Annotation] = {}
        for a in annotations:
            prev = by_user.get(a.annotator_id)
            if not prev or (a.updated_at or a.created_at or 0) > (prev.updated_at or prev.created_at or 0):
                by_user[a.annotator_id] = a
        annotations = list(by_user.values())
        
        if len(annotations) < 2:
            # 只有一个标注，无法计算一致性
            return AgreementResult(
                task_id=task_id,
                annotator_count=len(annotations),
                agreement_rate=1.0,
                kappa_score=1.0,
                is_golden=task.is_golden
            )
        
        # 提取标注结果
        results = [self._extract_result_key(a.data or {}) for a in annotations]
        
        # 计算简单一致率
        agreement_rate = self._calculate_agreement_rate(results)
        
        # 计算Kappa系数
        kappa = self._calculate_kappa(results)
        
        # 黄金标准题准确率
        golden_accuracy = None
        if task.is_golden and task.golden_answer:
            gold = task.golden_answer
            if isinstance(gold, dict) and isinstance(gold.get("data"), dict):
                gold = gold["data"]
            golden_accuracy = self._calculate_golden_accuracy(
                results, gold if isinstance(gold, dict) else {"value": gold}
            )
        
        return AgreementResult(
            task_id=task_id,
            annotator_count=len(annotations),
            agreement_rate=agreement_rate,
            kappa_score=kappa,
            is_golden=task.is_golden,
            golden_accuracy=golden_accuracy
        )
    
    def _extract_result_key(self, result: Dict) -> str:
        """提取结果的关键特征用于比对"""
        if not isinstance(result, dict):
            return str(result)
        # 嵌套 data（黄金题结构）
        if "data" in result and isinstance(result["data"], dict) and len(result) <= 4:
            result = result["data"]
        # modality spans（NER / OCR）
        if "spans" in result and isinstance(result["spans"], list):
            parts = []
            for e in result["spans"]:
                if not isinstance(e, dict):
                    continue
                label = e.get("label") or e.get("text") or ""
                text = e.get("text") or ""
                bbox = e.get("bbox")
                if bbox:
                    parts.append(f"{label}:{text}:{tuple(bbox)}")
                else:
                    start, end = e.get("start"), e.get("end")
                    parts.append(f"{label}:{text}:{start}-{end}")
            return "|".join(sorted(parts))
        if "entities" in result:
            entities = result["entities"]
            return "|".join(sorted([
                f"{e.get('label')}:{e.get('text')}"
                for e in entities if isinstance(e, dict)
            ]))
        if "annotations2d" in result and isinstance(result["annotations2d"], list):
            parts = []
            for b in result["annotations2d"]:
                if isinstance(b, dict):
                    parts.append(f"{b.get('label')}:{b.get('bbox') or b.get('xywh')}")
            return "|".join(sorted(parts))
        if "transcript" in result:
            return str(result.get("transcript") or "")
        if "caption" in result:
            return str(result.get("caption") or "")
        if "label" in result:
            return str(result["label"])
        return str(sorted((k, str(v)) for k, v in result.items() if k not in ("schema", "submitted_at")))

    
    def _calculate_agreement_rate(self, results: List[str]) -> float:
        """
        计算简单一致率
        
        使用最多出现的结果作为标准，计算匹配比例
        """
        if not results:
            return 0.0
        
        # 统计各结果出现次数
        counts = defaultdict(int)
        for r in results:
            counts[r] += 1
        
        # 最多出现的结果
        max_count = max(counts.values())
        
        return max_count / len(results)
    
    def _calculate_kappa(self, results: List[str]) -> float:
        """
        计算 Fleiss' Kappa 系数
        
        Kappa > 0.8 几乎完全一致
        Kappa 0.6-0.8 一致性好
        Kappa 0.4-0.6 一致性中等
        Kappa < 0.4 一致性差
        """
        if len(results) < 2:
            return 1.0
        
        # 统计各类别
        categories = list(set(results))
        n = len(results)
        k = len(categories)
        
        if k == 1:
            return 1.0  # 所有人都一样
        
        # 每个类别的占比
        p = [results.count(c) / n for c in categories]
        
        # P_e: 随机一致的概率
        p_e = sum(pi ** 2 for pi in p)
        
        # P_o: 观察到的一致概率（简化版）
        # 使用最多出现的结果占比
        max_count = max(results.count(c) for c in categories)
        p_o = max_count / n
        
        # Kappa
        if p_e >= 1:
            return 1.0
        
        kappa = (p_o - p_e) / (1 - p_e)
        return round(max(0, kappa), 3)
    
    def _calculate_golden_accuracy(
        self, 
        results: List[str], 
        golden_answer: Dict
    ) -> float:
        """计算黄金标准题的准确率"""
        golden_key = self._extract_result_key(golden_answer)
        
        correct_count = sum(1 for r in results if r == golden_key)
        return correct_count / len(results)
    
    def insert_golden_tasks(self, project_id: int, ratio: float = None) -> int:
        """
        向项目中插入黄金标准题
        
        Args:
            project_id: 项目ID
            ratio: 黄金题比例，默认使用配置值
            
        Returns:
            插入的黄金题数量
        """
        ratio = ratio or self.GOLDEN_RATIO
        
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return 0
        
        # 获取项目的普通任务
        normal_tasks = self.db.query(Task).filter(
            and_(
                Task.project_id == project_id,
                Task.is_golden == False
            )
        ).all()
        
        if not normal_tasks:
            return 0
        
        # 计算需要插入的数量
        total_tasks = self.db.query(Task).filter(
            Task.project_id == project_id
        ).count()
        
        target_golden = int(total_tasks * ratio)
        current_golden = self.db.query(Task).filter(
            and_(
                Task.project_id == project_id,
                Task.is_golden == True
            )
        ).count()
        
        need_insert = target_golden - current_golden
        if need_insert <= 0:
            return 0
        
        # 随机选择任务设为黄金题
        import random
        candidates = random.sample(
            normal_tasks, 
            min(need_insert, len(normal_tasks))
        )
        
        inserted = 0
        for task in candidates:
            golden_answer = self._generate_golden_answer(task)
            if not golden_answer:
                continue
            task.is_golden = True
            task.golden_answer = golden_answer
            inserted += 1
        
        self.db.commit()
        logger.info(f"项目 {project_id} 插入 {inserted} 道黄金标准题")
        
        return inserted
    
    def _generate_golden_answer(self, task: Task) -> Optional[Dict]:
        """仅在有最新标注真值时生成黄金答案；否则跳过（不写空 placeholder）。"""
        ann = (
            self.db.query(Annotation)
            .filter(Annotation.task_id == task.id, Annotation.is_latest == True)
            .order_by(Annotation.updated_at.desc())
            .first()
        )
        if ann and isinstance(ann.data, dict) and ann.data:
            return {
                "data": ann.data,
                "source": "existing_annotation",
                "confidence": 1.0,
                "annotation_id": ann.id,
            }
        return None
    
    def calculate_annotator_quality(self, user_id: int) -> Optional[QualityScore]:
        """
        计算标注员的质量评分
        
        综合指标：
        - 准确率（基于黄金题）
        - 一致性（基于交叉验证）
        - 效率（完成速度）
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        
        # 1. 准确率（基于黄金题）
        golden_annotations = self.db.query(Annotation).join(Task).filter(
            and_(
                Annotation.annotator_id == user_id,
                Task.is_golden == True,
                Annotation.is_latest == True,
            )
        ).all()
        
        if golden_annotations:
            correct = 0
            for ann in golden_annotations:
                task = ann.task
                if task.golden_answer:
                    gold = task.golden_answer
                    payload = gold.get("data") if isinstance(gold, dict) and "data" in gold else gold
                    if self._results_match(ann.data or {}, payload or {}):
                        correct += 1
            accuracy = correct / len(golden_annotations)
        else:
            # 无黄金题，使用默认分
            accuracy = 0.7
        
        # 2. 一致性（基于交叉验证任务）
        cross_tasks = self.db.query(Task).join(Annotation).filter(
            and_(
                Annotation.annotator_id == user_id,
                Task.status == TaskStatus.APPROVED
            )
        ).all()
        
        if cross_tasks:
            agreement_scores = []
            for task in cross_tasks:
                result = self.calculate_cross_validation(task.id)
                if result:
                    agreement_scores.append(result.agreement_rate)
            consistency = sum(agreement_scores) / len(agreement_scores) if agreement_scores else 0.7
        else:
            consistency = 0.7
        
        # 3. 效率分（基于历史平均速度）
        efficiency = min(user.efficiency_score / 100, 1.0) if user.efficiency_score else 0.5
        
        # 综合评分
        overall = accuracy * 0.5 + consistency * 0.3 + efficiency * 0.2
        
        # 建议等级
        suggested_level = self._suggest_level(overall, user.completed_tasks)
        
        return QualityScore(
            user_id=user_id,
            username=user.username,
            accuracy=round(accuracy, 3),
            consistency=round(consistency, 3),
            efficiency=round(efficiency, 3),
            overall_score=round(overall, 3),
            level=user.level,
            suggested_level=suggested_level
        )
    
    def _results_match(self, result1: Dict, result2: Dict) -> bool:
        """比较两个结果是否匹配"""
        key1 = self._extract_result_key(result1)
        key2 = self._extract_result_key(result2)
        return key1 == key2
    
    def _suggest_level(self, score: float, completed_tasks: int) -> AnnotatorLevel:
        """根据评分建议等级"""
        if score >= 0.95 and completed_tasks > 1000:
            return AnnotatorLevel.EXPERT
        elif score >= 0.90 and completed_tasks > 500:
            return AnnotatorLevel.SENIOR
        elif score >= 0.85 and completed_tasks > 200:
            return AnnotatorLevel.INTERMEDIATE
        elif score >= 0.80 and completed_tasks > 50:
            return AnnotatorLevel.JUNIOR
        else:
            return AnnotatorLevel.NOVICE
    
    def review_task(
        self, 
        task_id: int, 
        reviewer_id: int,
        decision: str,  # 'approved' | 'rejected'
        score: float = None,
        feedback: str = None,
        canonical_annotation_id: str = None,
        targets: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """
        审核任务。

        - approved → APPROVED（可写 canonical_annotation_id）
        - rejected → ANNOTATING（驳回回流标注，保留原 assignee）
        - targets：驳回时的对象定位 [{object_id, label?, note?}]
        """
        from app.services.consensus import latest_annotations, set_canonical
        from app.services.notifications import notify

        task = self.db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return False

        status = task.status
        if status not in (TaskStatus.SUBMITTED, TaskStatus.REVIEWING, TaskStatus.REJECTED):
            logger.warning(
                "review_task refused: task %s status=%s",
                task_id,
                status.value if hasattr(status, "value") else status,
            )
            return False

        if decision not in ("approved", "rejected"):
            return False

        versions = latest_annotations(task)
        if decision == "approved":
            chosen = canonical_annotation_id
            if not chosen:
                if len(versions) == 1:
                    chosen = versions[0].id
                elif getattr(task, "canonical_annotation_id", None):
                    chosen = task.canonical_annotation_id
                elif len(versions) > 1:
                    logger.warning(
                        "review_task refused: task %s needs canonical_annotation_id",
                        task_id,
                    )
                    return False
            if chosen and not set_canonical(self.db, task, chosen):
                return False

        clean_targets: List[Dict[str, Any]] = []
        if decision == "rejected" and isinstance(targets, list):
            for t in targets:
                if not isinstance(t, dict):
                    continue
                oid = t.get("object_id") or t.get("id")
                if oid is None:
                    continue
                clean_targets.append(
                    {
                        "object_id": str(oid),
                        "label": t.get("label"),
                        "note": t.get("note") or t.get("message"),
                    }
                )

        # 创建审核记录
        review = Review(
            task_id=task_id,
            reviewer_id=reviewer_id,
            decision=decision,
            score=score,
            feedback=feedback,
            issues=(
                ([*(self._analyze_issues(task)), *[f"定位:{x['object_id']}" for x in clean_targets]]
                 if decision == "rejected"
                 else None)
            ),
        )
        self.db.add(review)

        if decision == "approved":
            task.status = TaskStatus.APPROVED
        else:
            # 驳回回流：回到标注中，便于标注员继续修改后再次提交
            task.status = TaskStatus.ANNOTATING
            meta = dict(task.task_metadata or {})
            if feedback:
                meta["last_reject_feedback"] = feedback
            meta["last_rejected_at"] = datetime.utcnow().isoformat()
            if clean_targets:
                meta["last_reject_targets"] = clean_targets
            else:
                meta.pop("last_reject_targets", None)
            task.task_metadata = meta

            notify_uids = set()
            if task.assignee_id:
                notify_uids.add(task.assignee_id)
            for uid in (meta.get("submitted_annotator_ids") or []):
                try:
                    notify_uids.add(int(uid))
                except (TypeError, ValueError):
                    pass
            for uid in notify_uids:
                notify(
                    self.db,
                    uid,
                    type="task_rejected",
                    title=f"任务 #{task_id} 已驳回",
                    body=(feedback or "请根据审核意见修改后重新提交")[:500],
                    payload={
                        "task_id": task_id,
                        "project_id": task.project_id,
                        "targets": clean_targets,
                    },
                )

        # 更新标注员评分
        if score is not None and task.assignee_id:
            self._update_annotator_score(task.assignee_id, score)

        try:
            from app.services.webhooks import emit_for_task

            emit_for_task(
                self.db,
                task,
                "review.decided",
                {"decision": decision, "reviewer_id": reviewer_id},
            )
        except Exception:
            logger.exception("webhook emit review.decided failed")

        self.db.commit()

        logger.info(f"任务 {task_id} 审核完成: {decision}")
        return True
    
    def _analyze_issues(self, task: Task) -> List[str]:
        """分析任务存在的问题"""
        issues = []
        
        # 交叉验证一致性检查
        cv_result = self.calculate_cross_validation(task.id)
        if cv_result and cv_result.agreement_rate < self.MIN_AGREEMENT_THRESHOLD:
            issues.append(f"一致性较低 ({cv_result.agreement_rate:.1%})")
        
        # 黄金题准确率检查
        if cv_result and cv_result.is_golden and cv_result.golden_accuracy < 1.0:
            issues.append(f"黄金题错误")
        
        # 其他检查...
        
        return issues if issues else ["标注质量不达标"]
    
    def _update_annotator_score(self, user_id: int, score: float):
        """更新标注员评分"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        # 移动平均更新准确率
        if user.total_tasks == 0:
            user.accuracy_score = score * 100
        else:
            # 加权平均：历史70% + 新评分30%
            user.accuracy_score = user.accuracy_score * 0.7 + score * 100 * 0.3
        
        self.db.commit()
    
    def get_project_quality_report(self, project_id: int) -> Dict:
        """
        生成项目质量报告
        """
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {}
        
        # 统计
        total_tasks = self.db.query(Task).filter(
            Task.project_id == project_id
        ).count()
        
        approved_tasks = self.db.query(Task).filter(
            and_(
                Task.project_id == project_id,
                Task.status == TaskStatus.APPROVED
            )
        ).count()
        
        # 交叉验证统计
        cross_validated = self.db.query(Task).filter(
            and_(
                Task.project_id == project_id,
                Task.status == TaskStatus.APPROVED
            )
        ).having(func.count(Task.annotations) >= 2).group_by(Task.id).count()
        
        # 黄金题统计
        golden_tasks = self.db.query(Task).filter(
            and_(
                Task.project_id == project_id,
                Task.is_golden == True
            )
        ).count()
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "total_tasks": total_tasks,
            "approved_tasks": approved_tasks,
            "approval_rate": round(approved_tasks / total_tasks * 100, 2) if total_tasks > 0 else 0,
            "cross_validated": cross_validated,
            "golden_tasks": golden_tasks,
            "quality_score": self._calculate_project_quality_score(project_id)
        }
    
    def _calculate_project_quality_score(self, project_id: int) -> float:
        """计算项目整体质量分"""
        # 综合多个指标
        reviews = self.db.query(Review).join(Task).filter(
            Task.project_id == project_id
        ).all()
        
        if not reviews:
            return 0.0
        
        scores = [r.score for r in reviews if r.score]
        if scores:
            return round(sum(scores) / len(scores), 2)
        
        return 0.0


def get_quality_service(db: Session) -> QualityControlService:
    """获取质量控制服务实例"""
    return QualityControlService(db)
