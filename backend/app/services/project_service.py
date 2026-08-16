"""
ProjectService — 适配现有模型体系
使用 app.models.user.User / project.Project / project.ProjectMember / task.Task
通过 annotation_schema 字段存储扩展配置（category, ann_type, dispatch 等）
"""
import uuid as uuid_lib
import logging
import random
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User, AnnotatorLevel
from app.models.project import Project, ProjectMember, ProjectStatus
from app.models.task import Task, TaskStatus, TaskPriority, Review, TaskAssignment
from app.schemas.project_schemas import (
    ProjectCreate, ProjectUpdate, DispatchRequest,
    TaskBulkCreate, DispatchStrategy,
)

logger = logging.getLogger(__name__)

# ── Level config ──────────────────────────────────────────────────────────────

LEVEL_CAPACITY = {
    AnnotatorLevel.NOVICE:       10,
    AnnotatorLevel.JUNIOR:       20,
    AnnotatorLevel.INTERMEDIATE: 30,
    AnnotatorLevel.SENIOR:       50,
    AnnotatorLevel.EXPERT:       80,
}

LEVEL_BONUS = {
    AnnotatorLevel.NOVICE:       0.5,
    AnnotatorLevel.JUNIOR:       0.6,
    AnnotatorLevel.INTERMEDIATE: 0.75,
    AnnotatorLevel.SENIOR:       0.9,
    AnnotatorLevel.EXPERT:       1.0,
}

WEIGHTS = {"skill": 0.35, "quality": 0.25, "load": 0.20, "speed": 0.10, "level": 0.10}


def _get_schema(project: Project) -> Dict[str, Any]:
    """安全读取 annotation_schema，兼容 None 和 JSON string"""
    s = project.annotation_schema
    if not s:
        return {}
    if isinstance(s, str):
        try:
            return json.loads(s)
        except Exception:
            return {}
    return s if isinstance(s, dict) else {}


# ann_type → UI category（与前端 ANN_TYPE_TO_CATEGORY 对齐）
_ANN_TYPE_TO_CATEGORY = {
    "bbox_2d": "image_2d", "polygon": "image_2d", "polyline": "image_2d",
    "keypoint": "image_2d", "segmentation": "image_2d", "classification": "image_2d",
    "bbox_3d": "pointcloud_3d", "lidar_seg": "pointcloud_3d", "lane_3d": "pointcloud_3d",
    "video_tracking": "video", "video_action": "video", "video_caption": "video",
    "asr": "audio", "tts_label": "audio", "speaker_diarize": "audio", "emotion_audio": "audio",
    "ner": "nlp", "re": "nlp", "sentiment": "nlp", "text_classify": "nlp",
    "qa_pair": "nlp", "summarization": "nlp", "translation": "nlp",
    "robot_traj": "embodied", "robot_action": "embodied", "robot_grasp": "embodied", "robot_scene": "embodied",
    "ocr_text": "ocr", "ocr_layout": "ocr", "ocr_table": "ocr",
    "image_caption": "multimodal", "vqa": "multimodal", "rlhf": "multimodal",
}

# 旧 Project.type enum → UI category
_PROJECT_TYPE_TO_CATEGORY = {
    "text_classification": "nlp",
    "ner": "nlp",
    "text_summarization": "nlp",
    "image_classification": "image_2d",
    "object_detection": "image_2d",
    "image_segmentation": "image_2d",
    "ocr": "ocr",
    "audio_transcription": "audio",
    "multimodal": "multimodal",
}


def _resolve_project_category(project: Project) -> str:
    """解析项目 UI 类别：列字段 → schema.category → ann_type → 旧 type"""
    col = str(getattr(project, "category", None) or "").strip().lower()
    if col:
        return col
    schema = _get_schema(project)
    raw = str(schema.get("category") or "").strip().lower()
    if raw:
        return raw
    ann = str(getattr(project, "ann_type", None) or schema.get("ann_type") or "").strip().lower()
    if ann and ann in _ANN_TYPE_TO_CATEGORY:
        return _ANN_TYPE_TO_CATEGORY[ann]
    type_val = project.type.value if hasattr(project.type, "value") else str(project.type or "")
    type_val = type_val.strip().lower()
    return _PROJECT_TYPE_TO_CATEGORY.get(type_val, type_val)


def _resolve_project_ann_type(project: Project) -> str:
    col = str(getattr(project, "ann_type", None) or "").strip().lower()
    if col:
        return col
    schema = _get_schema(project)
    return str(schema.get("ann_type") or "").strip().lower()


def _project_matches_category(project: Project, category: str) -> bool:
    want = (category or "").strip().lower()
    if not want:
        return True
    return _resolve_project_category(project) == want


def _active_tasks_count(user: User, db: Session) -> int:
    """统计用户当前活跃任务数"""
    return db.query(Task).filter(
        Task.assignee_id == user.id,
        Task.status.in_([TaskStatus.ASSIGNED, TaskStatus.ANNOTATING]),
    ).count()


# ══════════════════════════════════════════════════════════════════
# ProjectService
# ══════════════════════════════════════════════════════════════════

class ProjectService:

    def __init__(self, db: Session):
        self.db = db

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create(self, payload: ProjectCreate, creator_id: int) -> Project:
        # 把新增字段全部打包进 annotation_schema
        schema = {
            "category": payload.category.value,
            "ann_type": payload.ann_type.value,
            "label_classes": [lc.model_dump() for lc in payload.label_classes],
            "schema_config": payload.schema_config,
            "dispatch_strategy": payload.dispatch_strategy.value,
            "tasks_per_annotator": payload.tasks_per_annotator,
            "cross_validate_count": payload.cross_validate_count,
            "min_level": payload.min_level,
            "price_per_task": payload.price_per_task,
            "bonus_rate": payload.bonus_rate,
            "cover_color": payload.cover_color,
            "deadline": payload.deadline.isoformat() if payload.deadline else None,
            "dispatch_logs": [],
        }

        org_id = None
        creator = self.db.query(User).filter(User.id == creator_id).first()
        if creator is not None:
            from app.services.organization_service import OrganizationService

            org = OrganizationService(self.db).ensure_personal_org(creator)
            org_id = creator.active_org_id or org.id

        project = Project(
            name=payload.name,
            description=payload.description,
            type=self._map_type(payload.category.value, payload.ann_type.value),
            status=ProjectStatus.DRAFT,
            category=payload.category.value,
            ann_type=payload.ann_type.value,
            annotation_schema=schema,
            auto_label_enabled=payload.auto_label_enabled,
            auto_label_model=payload.auto_label_model,
            auto_label_threshold=payload.auto_label_threshold,
            quality_config={},
            created_by_id=creator_id,
            organization_id=org_id,
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)

        # 创建者自动成为 owner
        self._add_member_raw(project.id, creator_id, "owner")

        logger.info("Project created id=%d name=%s", project.id, project.name)
        return project

    def _map_type(self, category: str, ann_type: str) -> str:
        """把新的 category/ann_type 映射到现有 ProjectType enum 值（尽量兼容）"""
        from app.models.project import ProjectType
        MAP = {
            "image_2d": ProjectType.OBJECT_DETECTION,
            "pointcloud_3d": ProjectType.OBJECT_DETECTION,
            "video": ProjectType.MULTIMODAL,
            "audio": ProjectType.AUDIO_TRANSCRIPTION,
            "nlp": ProjectType.NER,
            "embodied": ProjectType.MULTIMODAL,
            "ocr": ProjectType.OCR,
            "multimodal": ProjectType.MULTIMODAL,
        }
        return MAP.get(category, ProjectType.MULTIMODAL)

    def get(self, project_id: int) -> Optional[Project]:
        return self.db.query(Project).filter(Project.id == project_id).first()

    def list_all(
        self,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        category: Optional[str] = None,
        user_id: Optional[int] = None,
        org_id: Optional[int] = None,
    ) -> List[Project]:
        q = self.db.query(Project)
        if status:
            try:
                q = q.filter(Project.status == ProjectStatus(status))
            except ValueError:
                logger.warning("Unknown project status filter: %s", status)
        if org_id is not None:
            q = q.filter(Project.organization_id == org_id)
        if user_id:
            member_project_ids = (
                self.db.query(ProjectMember.project_id)
                .filter(ProjectMember.user_id == user_id)
                .subquery()
            )
            q = q.filter(
                (Project.created_by_id == user_id) |
                Project.id.in_(member_project_ids)
            )
        # category：优先走列字段 SQL 过滤，再对无列值的旧行做内存兜底
        rows = q.order_by(Project.created_at.desc()).all()
        if category:
            rows = [p for p in rows if _project_matches_category(p, category)]
        return rows[skip : skip + limit]

    def update(self, project_id: int, payload: ProjectUpdate) -> Project:
        project = self.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        schema = _get_schema(project)

        # Update top-level fields
        if payload.name is not None:
            project.name = payload.name
        if payload.description is not None:
            project.description = payload.description
        if payload.status is not None:
            try:
                project.status = ProjectStatus(payload.status)
            except ValueError as e:
                raise ValueError(f"无效的项目状态: {payload.status}") from e
        if payload.auto_label_enabled is not None:
            project.auto_label_enabled = payload.auto_label_enabled
        if payload.auto_label_model is not None:
            project.auto_label_model = payload.auto_label_model
        if payload.auto_label_threshold is not None:
            project.auto_label_threshold = payload.auto_label_threshold

        # Update schema fields
        for field in [
            "cover_color", "dispatch_strategy", "tasks_per_annotator",
            "cross_validate_count", "price_per_task", "bonus_rate",
        ]:
            val = getattr(payload, field, None)
            if val is not None:
                schema[field] = val.value if hasattr(val, "value") else val

        if payload.label_classes is not None:
            schema["label_classes"] = [lc.model_dump() for lc in payload.label_classes]
        if payload.schema_config is not None:
            schema["schema_config"] = payload.schema_config
        if payload.deadline is not None:
            schema["deadline"] = payload.deadline.isoformat()

        project.annotation_schema = schema
        self.db.commit()
        self.db.refresh(project)
        return project

    def archive(self, project_id: int) -> Project:
        project = self.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        if project.status == ProjectStatus.ARCHIVED:
            return project

        schema = _get_schema(project)
        prev = project.status.value if hasattr(project.status, "value") else str(project.status)
        schema["status_before_archive"] = prev
        schema["archived_at"] = datetime.now(timezone.utc).isoformat()
        project.annotation_schema = schema
        project.status = ProjectStatus.ARCHIVED
        project.end_date = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(project)
        logger.info("Project archived id=%d", project_id)
        return project

    def restore(self, project_id: int) -> Project:
        project = self.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        if project.status != ProjectStatus.ARCHIVED:
            raise ValueError("项目未处于归档状态")

        schema = _get_schema(project)
        prev = schema.pop("status_before_archive", None) or ProjectStatus.PAUSED.value
        schema.pop("archived_at", None)
        project.annotation_schema = schema
        try:
            project.status = ProjectStatus(prev)
        except ValueError:
            project.status = ProjectStatus.PAUSED
        project.end_date = None
        self.db.commit()
        self.db.refresh(project)
        logger.info("Project restored id=%d status=%s", project_id, project.status)
        return project

    def delete(self, project_id: int) -> Dict[str, Any]:
        """删除项目及其任务、成员（级联清理关联表）"""
        project = self.get(project_id)
        if not project:
            return {"ok": False, "reason": "not_found"}

        task_ids = [
            row[0]
            for row in self.db.query(Task.id).filter(Task.project_id == project_id).all()
        ]
        if task_ids:
            self.db.query(Review).filter(Review.task_id.in_(task_ids)).delete(
                synchronize_session=False
            )
            self.db.query(TaskAssignment).filter(
                TaskAssignment.task_id.in_(task_ids)
            ).delete(synchronize_session=False)
            self.db.query(Task).filter(Task.project_id == project_id).delete(
                synchronize_session=False
            )

        self.db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id
        ).delete(synchronize_session=False)
        self.db.delete(project)
        self.db.commit()
        logger.info("Project deleted id=%d tasks=%d", project_id, len(task_ids))
        return {"ok": True, "deleted_tasks": len(task_ids)}

    def activate(self, project_id: int) -> Project:
        p = self.get(project_id)
        if not p:
            raise ValueError("Not found")
        p.status = ProjectStatus.ACTIVE
        self.db.commit()
        self.db.refresh(p)
        return p

    def pause(self, project_id: int) -> Project:
        p = self.get(project_id)
        if not p:
            raise ValueError("Not found")
        p.status = ProjectStatus.PAUSED
        self.db.commit()
        self.db.refresh(p)
        return p

    # ── Members ───────────────────────────────────────────────────────────────

    def _add_member_raw(self, project_id: int, user_id: int, role: str):
        existing = self.db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        ).first()
        if existing:
            return
        member = ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role=role,
            can_assign=(role in ["owner", "manager"]),
            can_review=(role in ["owner", "manager", "reviewer"]),
            can_export=(role in ["owner", "manager"]),
        )
        self.db.add(member)
        self.db.commit()

    def add_member(self, project_id: int, user_id: int, role: str = "annotator") -> bool:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not self.get(project_id) or not user:
            return False
        self._add_member_raw(project_id, user_id, role)
        return True

    def remove_member(self, project_id: int, user_id: int) -> bool:
        self.db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        ).delete()
        self.db.commit()
        return True

    def get_members(self, project_id: int) -> List[Dict]:
        members = self.db.query(ProjectMember).filter(
            ProjectMember.project_id == project_id
        ).all()
        result = []
        for m in members:
            user = self.db.query(User).filter(User.id == m.user_id).first()
            if user:
                result.append({
                    "user_id": user.id,
                    "username": user.username,
                    "level": user.level.value if hasattr(user.level, "value") else user.level,
                    "role": m.role,
                    "accuracy_score": user.accuracy_score,
                    "completed_tasks": user.completed_tasks,
                })
        return result

    # ── Task import ───────────────────────────────────────────────────────────

    def bulk_import_tasks(self, payload: TaskBulkCreate, project_id: int) -> Dict[str, int]:
        project = self.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        items = (
            [{"data_url": u, "raw_text": None} for u in payload.data_urls] +
            [{"data_url": None, "raw_text": t} for t in payload.raw_texts]
        )
        if not items:
            return {"created": 0, "golden": 0}

        n_golden = max(1, int(len(items) * payload.golden_ratio))
        golden_indices = set(random.sample(range(len(items)), min(n_golden, len(items))))

        created = 0
        for i, item in enumerate(items):
            task_data = {}
            if item["raw_text"]:
                task_data["text"] = item["raw_text"]

            task = Task(
                project_id=project_id,
                data=task_data,
                data_url=item["data_url"],
                priority=payload.priority,
                is_golden=(i in golden_indices),
                status=TaskStatus.PENDING,
            )
            self.db.add(task)
            created += 1

        project.total_items = (project.total_items or 0) + created
        self.db.commit()
        return {"created": created, "golden": n_golden}

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _score_user(self, user: User, project: Project, active: int) -> float:
        cap = LEVEL_CAPACITY.get(user.level, 10)
        if active >= cap:
            return 0.0

        schema = _get_schema(project)
        category = schema.get("category", "")

        # Skill match
        skills = []
        if user.skills:
            try:
                skills = json.loads(user.skills) if isinstance(user.skills, str) else user.skills
            except Exception:
                skills = []
        req = {category} if category else set()
        matched = len(req & set(skills))
        skill_s = 0.3 + (matched / max(len(req), 1)) * 0.7 if req else 0.7

        # Quality
        quality_s = (user.accuracy_score / 100) * 0.7 + (
            user.completed_tasks / max(user.total_tasks, 1)
        ) * 0.3 if user.total_tasks > 0 else 0.6

        # Load
        load = active / cap
        load_s = 1.0 if load < 0.3 else (
            1.0 - (load - 0.3) * 1.5 if load < 0.7 else (
                0.4 - (load - 0.7) * 1.5 if load < 0.9 else 0.1
            )
        )

        level_s = LEVEL_BONUS.get(user.level, 0.5)

        return round(
            WEIGHTS["skill"] * skill_s +
            WEIGHTS["quality"] * quality_s +
            WEIGHTS["load"] * load_s +
            WEIGHTS["speed"] * min(1.0, user.efficiency_score / 100) +
            WEIGHTS["level"] * level_s,
            4
        )

    def _get_eligible_users(self, project: Project) -> List[tuple]:
        """返回 [(user, active_task_count)] 已过滤容量"""
        members = self.db.query(ProjectMember).filter(
            ProjectMember.project_id == project.id
        ).all()

        schema = _get_schema(project)
        min_level_str = schema.get("min_level", "novice")
        level_order = [l.value for l in AnnotatorLevel]
        min_idx = level_order.index(min_level_str) if min_level_str in level_order else 0

        result = []
        for m in members:
            user = self.db.query(User).filter(User.id == m.user_id).first()
            if not user or not user.is_active or user.is_admin:
                continue
            user_level_str = user.level.value if hasattr(user.level, "value") else user.level
            if level_order.index(user_level_str) < min_idx:
                continue
            active = _active_tasks_count(user, self.db)
            cap = LEVEL_CAPACITY.get(user.level, 10)
            if active < cap:
                result.append((user, active))
        return result

    def dispatch(self, project_id: int, payload: DispatchRequest, dispatcher_id: int) -> Dict[str, Any]:
        project = self.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        schema = _get_schema(project)
        batch_id = str(uuid_lib.uuid4())
        cross_n = self._cross_validate_count(schema)

        pending = (
            self.db.query(Task)
            .filter(Task.project_id == project_id, Task.status == TaskStatus.PENDING)
            .order_by(Task.priority.desc(), Task.created_at.asc())
            .limit(payload.batch_size)
            .all()
        )
        if not pending:
            return {"success": True, "batch_id": batch_id, "assigned_count": 0,
                    "failed_count": 0, "strategy": payload.strategy.value,
                    "assignments": [], "message": "没有待分派的任务"}

        # Get users
        if payload.strategy == DispatchStrategy.manual and payload.target_user_ids:
            eligible = []
            for uid in payload.target_user_ids:
                u = self.db.query(User).filter(User.id == uid).first()
                if u:
                    active = _active_tasks_count(u, self.db)
                    eligible.append((u, active))
        else:
            eligible = self._get_eligible_users(project)

        if not eligible:
            return {"success": False, "batch_id": batch_id, "assigned_count": 0,
                    "failed_count": len(pending), "strategy": payload.strategy.value,
                    "assignments": [], "message": "没有可用的标注员"}

        assignments, failed = [], 0

        if payload.strategy == DispatchStrategy.smart:
            for task in pending:
                scored = self._scored_pool(eligible, project)
                picks = scored[:cross_n]
                if not picks:
                    failed += 1
                    continue
                added = self._assign_task_multi(task, picks, batch_id, cross_n)
                if added:
                    assignments.extend(added)
                    eligible = [(u, _active_tasks_count(u, self.db)) for u, _ in eligible]
                else:
                    failed += 1

        elif payload.strategy == DispatchStrategy.random:
            for task in pending:
                pool = self._scored_pool(eligible, project)
                if not pool:
                    failed += 1
                    continue
                random.shuffle(pool)
                picks = pool[:cross_n]
                added = self._assign_task_multi(task, picks, batch_id, cross_n)
                if added:
                    assignments.extend(added)
                    eligible = [(u, _active_tasks_count(u, self.db)) for u, _ in eligible]
                else:
                    failed += 1

        else:  # round_robin / manual
            pool = self._scored_pool(eligible, project)
            if not pool:
                failed = len(pending)
            else:
                idx = 0
                for task in pending:
                    if not pool:
                        failed += 1
                        continue
                    picks = []
                    seen = set()
                    for _ in range(len(pool) * 2):
                        if len(picks) >= cross_n:
                            break
                        user, score = pool[idx % len(pool)]
                        idx += 1
                        if user.id in seen:
                            continue
                        seen.add(user.id)
                        picks.append((user, score))
                    added = self._assign_task_multi(task, picks, batch_id, cross_n)
                    if added:
                        assignments.extend(added)
                        eligible = [(u, _active_tasks_count(u, self.db)) for u, _ in eligible]
                        pool = self._scored_pool(eligible, project)
                    else:
                        failed += 1

        # Save dispatch log into annotation_schema
        logs = schema.get("dispatch_logs", [])
        logs.append({
            "batch_id": batch_id,
            "strategy": payload.strategy.value,
            "total": len(pending),
            "assigned": len({a["task_id"] for a in assignments}),
            "assignment_rows": len(assignments),
            "cross_validate_count": cross_n,
            "failed": failed,
            "dispatcher_id": dispatcher_id,
            "dispatched_at": datetime.utcnow().isoformat(),
        })
        schema["dispatch_logs"] = logs[-50:]  # keep last 50
        project.annotation_schema = schema
        self.db.commit()

        return {
            "success": True,
            "batch_id": batch_id,
            "assigned_count": len({a["task_id"] for a in assignments}),
            "failed_count": failed,
            "strategy": payload.strategy.value,
            "assignments": assignments,
            "message": f"成功分派 {len({a['task_id'] for a in assignments})} 个任务"
            + (f"（交叉 {cross_n} 人）" if cross_n > 1 else ""),
        }

    @staticmethod
    def _cross_validate_count(schema: Dict[str, Any]) -> int:
        try:
            n = int(schema.get("cross_validate_count") or 1)
        except (TypeError, ValueError):
            n = 1
        return max(1, min(n, 5))

    def _scored_pool(self, eligible: List, project: Optional[Project] = None) -> List:
        out = []
        for u, active in eligible:
            if project is not None:
                score = self._score_user(u, project, active)
            else:
                score = max(0.01, 1.0 - (active / 50.0))
            if score > 0:
                out.append((u, score))
        out.sort(key=lambda x: x[1], reverse=True)
        return out

    def _assign_task_multi(
        self,
        task: Task,
        picks: List,
        batch_id: str,
        cross_n: int,
    ) -> List[Dict]:
        """将任务分给最多 cross_n 人；写 TaskAssignment；共标人写入 task_metadata。"""
        if not picks:
            return []
        fresh = self.db.query(Task).filter(Task.id == task.id).with_for_update().first()
        if not fresh or fresh.status != TaskStatus.PENDING or fresh.assignee_id:
            return []

        primary_user, primary_score = picks[0]
        co = picks[1:cross_n]
        assignee_ids = [primary_user.id] + [u.id for u, _ in co]

        fresh.status = TaskStatus.ASSIGNED
        fresh.assignee_id = primary_user.id
        fresh.assigned_at = datetime.utcnow()
        meta = dict(fresh.task_metadata or {})
        meta.update({
            "dispatch_score": primary_score,
            "batch_id": batch_id,
            "cross_validate_count": cross_n,
            "assignee_ids": assignee_ids,
            "co_assignee_ids": [u.id for u, _ in co],
        })
        fresh.task_metadata = meta

        results = []
        for user, score in picks[:cross_n]:
            self.db.add(TaskAssignment(
                task_id=fresh.id,
                user_id=user.id,
                action="assign",
                reason=f"batch:{batch_id}",
            ))
            results.append(self._adict(fresh, user, score))
        self.db.commit()
        return results

    def _try_assign(self, task: Task, user: User, score: float, batch_id: str) -> bool:
        return bool(self._assign_task_multi(task, [(user, score)], batch_id, 1))

    @staticmethod
    def _adict(task: Task, user: User, score: float) -> Dict:
        return {
            "task_id": task.id,
            "user_id": user.id,
            "username": user.username,
            "score": score,
            "assigned_at": datetime.utcnow().isoformat(),
        }

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self, project_id: int) -> Dict[str, Any]:
        project = self.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        tasks = self.db.query(Task).filter(Task.project_id == project_id).all()
        total     = len(tasks)
        pending   = sum(1 for t in tasks if t.status == TaskStatus.PENDING)
        assigned  = sum(1 for t in tasks if t.status in (TaskStatus.ASSIGNED, TaskStatus.ANNOTATING))
        submitted = sum(1 for t in tasks if t.status in (TaskStatus.SUBMITTED, TaskStatus.REVIEWING))
        approved  = sum(1 for t in tasks if t.status == TaskStatus.APPROVED)
        rejected  = sum(1 for t in tasks if t.status == TaskStatus.REJECTED)

        reviewed  = approved + rejected
        completion_rate = round((approved + rejected + submitted) / total * 100, 1) if total else 0.0
        approval_rate   = round(approved / reviewed * 100, 1) if reviewed else 0.0

        member_count   = self.db.query(ProjectMember).filter(ProjectMember.project_id == project_id).count()
        schema         = _get_schema(project)
        dispatch_count = len(schema.get("dispatch_logs", []))

        return {
            "project_id": project_id,
            "total_tasks": total,
            "pending": pending,
            "assigned": assigned,
            "submitted": submitted,
            "approved": approved,
            "rejected": rejected,
            "completion_rate": completion_rate,
            "approval_rate": approval_rate,
            "member_count": member_count,
            "dispatch_count": dispatch_count,
        }
