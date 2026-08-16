"""
数据集导入服务
支持：
- 本地图像文件（多文件 / 文件夹拖入）
- 图像文件夹（ZIP）
- COCO JSON
- YOLO TXT
- CSV / JSONL（文本/语料）
- 音频文件夹（ZIP）
- 点云文件夹（ZIP）
"""
import os
import csv
import json
import uuid
import zipfile
import logging
import tempfile
from io import StringIO, BytesIO
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskStatus, TaskPriority
from app.services.file_storage import FileStorageService

logger = logging.getLogger(__name__)

# ── Supported formats ─────────────────────────────────────────────────────────

IMAGE_EXTS  = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".gif"}
AUDIO_EXTS  = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}
VIDEO_EXTS  = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
PCD_EXTS    = {".pcd", ".bin", ".ply", ".las"}
TEXT_EXTS   = {".txt", ".json", ".jsonl", ".csv"}


class ImportResult:
    def __init__(self):
        self.total      = 0
        self.success    = 0
        self.skipped    = 0
        self.errors: List[str] = []
        self.batch_id   = str(uuid.uuid4())
        self.started_at = datetime.utcnow().isoformat()

    def to_dict(self):
        payload = {
            "batch_id":   self.batch_id,
            "total":      self.total,
            "success":    self.success,
            "skipped":    self.skipped,
            "errors":     self.errors[:20],
            "error_count": len(self.errors),
            "started_at": self.started_at,
            "finished_at": datetime.utcnow().isoformat(),
        }
        if self.errors:
            logger.warning(
                "dataset_import_failed batch_id=%s total=%s success=%s skipped=%s errors=%s",
                self.batch_id,
                self.total,
                self.success,
                self.skipped,
                self.errors[:5],
            )
        else:
            logger.info(
                "dataset_import_ok batch_id=%s total=%s success=%s skipped=%s",
                self.batch_id,
                self.total,
                self.success,
                self.skipped,
            )
        return payload


class DatasetImportService:

    def __init__(self, db: Session, file_server_base_url: Optional[str] = None):
        self.db = db
        self.storage = FileStorageService(file_server_base_url)

    # ── Entry point ───────────────────────────────────────────────────────────

    def import_local_files(
        self,
        project_id: int,
        files: List[Tuple[str, bytes]],
        priority: int = 5,
        golden_ratio: float = 0.05,
    ) -> ImportResult:
        """导入本地图像文件，写入文件服务器并创建任务"""
        result = ImportResult()
        project = self._get_project(project_id)
        if not project:
            result.errors.append(f"Project {project_id} not found")
            return result

        import random

        valid: List[Tuple[str, bytes]] = []
        for name, content in files:
            ext = os.path.splitext(name)[-1].lower()
            if ext in IMAGE_EXTS:
                valid.append((name, content))
            else:
                result.skipped += 1

        result.total = len(valid)
        if not valid:
            result.errors.append("未找到支持的图像文件")
            return result

        n_golden = max(1, int(len(valid) * golden_ratio))
        golden_idx = set(random.sample(range(len(valid)), min(n_golden, len(valid))))

        for i, (name, content) in enumerate(valid):
            try:
                rel, public_url = self.storage.save_bytes(project_id, name, content)
                ext = os.path.splitext(name)[-1].lower()
                task = Task(
                    project_id=project_id,
                    data={"filename": os.path.basename(name), "storage_path": rel},
                    data_url=public_url,
                    task_metadata={
                        "source": "local_file_import",
                        "original_name": name,
                        "ext": ext,
                    },
                    priority=priority,
                    is_golden=(i in golden_idx),
                    status=TaskStatus.PENDING,
                )
                self.db.add(task)
                result.success += 1
            except Exception as e:
                result.errors.append(f"{name}: {e}")

        project.total_items = (project.total_items or 0) + result.success
        self.db.commit()
        return result

    def import_from_urls(
        self,
        project_id: int,
        urls: List[str],
        priority: int = 5,
        golden_ratio: float = 0.05,
    ) -> ImportResult:
        """直接导入 URL 列表（图像/音频/视频）"""
        result = ImportResult()
        project = self._get_project(project_id)
        if not project:
            result.errors.append(f"Project {project_id} not found")
            return result

        import random
        n_golden = max(1, int(len(urls) * golden_ratio))
        golden_idx = set(random.sample(range(len(urls)), min(n_golden, len(urls))))

        for i, url in enumerate(urls):
            try:
                ext = os.path.splitext(url.split("?")[0])[-1].lower()
                data = {"url": url}
                task = Task(
                    project_id=project_id,
                    data=data,
                    data_url=url,
                    task_metadata={"source": "url_import", "ext": ext},
                    priority=priority,
                    is_golden=(i in golden_idx),
                    status=TaskStatus.PENDING,
                )
                self.db.add(task)
                result.success += 1
            except Exception as e:
                result.errors.append(f"URL {url}: {e}")
            result.total += 1

        project.total_items = (project.total_items or 0) + result.success
        self.db.commit()
        return result

    def import_from_texts(
        self,
        project_id: int,
        texts: List[str],
        priority: int = 5,
        golden_ratio: float = 0.05,
    ) -> ImportResult:
        """导入文本列表（NLP/语料任务）"""
        result = ImportResult()
        project = self._get_project(project_id)
        if not project:
            result.errors.append(f"Project {project_id} not found")
            return result

        import random
        n_golden = max(1, int(len(texts) * golden_ratio))
        golden_idx = set(random.sample(range(len(texts)), min(n_golden, len(texts))))

        for i, text in enumerate(texts):
            if not text.strip():
                result.skipped += 1
                result.total += 1
                continue
            try:
                task = Task(
                    project_id=project_id,
                    data={"text": text},
                    data_url=None,
                    task_metadata={"source": "text_import"},
                    priority=priority,
                    is_golden=(i in golden_idx),
                    status=TaskStatus.PENDING,
                )
                self.db.add(task)
                result.success += 1
            except Exception as e:
                result.errors.append(f"Text item {i}: {e}")
            result.total += 1

        project.total_items = (project.total_items or 0) + result.success
        self.db.commit()
        return result

    def import_zip(
        self,
        project_id: int,
        zip_bytes: bytes,
        base_url_prefix: str = "",
        priority: int = 5,
        golden_ratio: float = 0.05,
    ) -> ImportResult:
        """
        导入 ZIP 包（图像文件夹 / 音频文件夹 / 点云文件夹）
        图像/音频/视频/点云文件写入 UPLOAD_DIR，data_url 指向文件服务
        """
        result = ImportResult()
        project = self._get_project(project_id)
        if not project:
            result.errors.append(f"Project {project_id} not found")
            return result

        import random

        try:
            with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
                result.total = len(names)

                valid = []
                for name in names:
                    ext = os.path.splitext(name)[-1].lower()
                    if ext in IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS | PCD_EXTS:
                        valid.append((name, ext))
                    else:
                        result.skipped += 1

                n_golden = max(1, int(len(valid) * golden_ratio))
                golden_idx = set(random.sample(range(len(valid)), min(n_golden, len(valid))))

                for i, (name, ext) in enumerate(valid):
                    try:
                        content = zf.read(name)
                        if ext in IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS | PCD_EXTS:
                            rel, public_url = self.storage.save_bytes(
                                project_id, os.path.basename(name), content, subdir="zip"
                            )
                            data_url = public_url
                            data = {"filename": os.path.basename(name), "storage_path": rel}
                        else:
                            data_url = f"{base_url_prefix.rstrip('/')}/{name}" if base_url_prefix else ""
                            data = {"filename": name}

                        task = Task(
                            project_id=project_id,
                            data=data,
                            data_url=data_url,
                            task_metadata={
                                "source": "zip_import",
                                "original_name": name,
                                "ext": ext,
                            },
                            priority=priority,
                            is_golden=(i in golden_idx),
                            status=TaskStatus.PENDING,
                        )
                        self.db.add(task)
                        result.success += 1
                    except Exception as e:
                        result.errors.append(f"{name}: {e}")

        except zipfile.BadZipFile:
            result.errors.append("Invalid ZIP file")
        except Exception as e:
            result.errors.append(f"ZIP processing error: {e}")

        project.total_items = (project.total_items or 0) + result.success
        self.db.commit()
        return result

    def import_coco_json(
        self,
        project_id: int,
        coco_json: Dict[str, Any],
        import_annotations: bool = True,
        priority: int = 5,
    ) -> ImportResult:
        """
        导入 COCO JSON 格式
        - images → Task
        - annotations → pre_label_result（可选）
        """
        result = ImportResult()
        project = self._get_project(project_id)
        if not project:
            result.errors.append(f"Project {project_id} not found")
            return result

        images = coco_json.get("images", [])
        annotations = coco_json.get("annotations", [])
        categories = {c["id"]: c["name"] for c in coco_json.get("categories", [])}

        # Group annotations by image_id
        ann_by_image: Dict[int, List] = {}
        for ann in annotations:
            ann_by_image.setdefault(ann["image_id"], []).append(ann)

        result.total = len(images)
        for img in images:
            try:
                img_id = img["id"]
                img_anns = ann_by_image.get(img_id, [])

                pre_label = None
                if import_annotations and img_anns:
                    pre_label = {
                        "format": "coco",
                        "annotations": [
                            {
                                "id": a["id"],
                                "category": categories.get(a["category_id"], "unknown"),
                                "bbox": a.get("bbox"),
                                "segmentation": a.get("segmentation"),
                                "score": 1.0,
                            }
                            for a in img_anns
                        ],
                    }

                task = Task(
                    project_id=project_id,
                    data={
                        "image_id": img_id,
                        "file_name": img.get("file_name", ""),
                        "width": img.get("width", 0),
                        "height": img.get("height", 0),
                    },
                    data_url=img.get("coco_url") or img.get("flickr_url") or "",
                    task_metadata={"source": "coco_import", "coco_image_id": img_id},
                    pre_label_result=pre_label,
                    pre_label_confidence=0.9 if pre_label else None,
                    priority=priority,
                    status=TaskStatus.PENDING,
                )
                self.db.add(task)
                result.success += 1
            except Exception as e:
                result.errors.append(f"Image {img.get('id')}: {e}")

        project.total_items = (project.total_items or 0) + result.success
        self.db.commit()
        return result

    def import_yolo(
        self,
        project_id: int,
        yolo_zip_bytes: bytes,
        class_names: List[str],
        base_url_prefix: str = "",
        priority: int = 5,
    ) -> ImportResult:
        """
        导入 YOLO 格式（images/ + labels/ 的 ZIP）
        """
        result = ImportResult()
        project = self._get_project(project_id)
        if not project:
            result.errors.append(f"Project {project_id} not found")
            return result

        try:
            with zipfile.ZipFile(BytesIO(yolo_zip_bytes)) as zf:
                names = zf.namelist()

                img_files = {
                    os.path.splitext(os.path.basename(n))[0]: n
                    for n in names
                    if os.path.splitext(n)[-1].lower() in IMAGE_EXTS
                }
                lbl_files = {
                    os.path.splitext(os.path.basename(n))[0]: n
                    for n in names
                    if n.endswith(".txt") and "labels" in n
                }

                result.total = len(img_files)
                for stem, img_path in img_files.items():
                    try:
                        img_bytes = zf.read(img_path)
                        # 始终使用存储后端返回的公网 URL（local / S3）；
                        # 勿用 ZIP 内相对路径覆盖，否则 S3 下 data_url 会指向错误对象。
                        _, img_url = self.storage.save_bytes(
                            project_id, os.path.basename(img_path), img_bytes, subdir="yolo"
                        )
                        if base_url_prefix and not img_url:
                            img_url = f"{base_url_prefix.rstrip('/')}/{os.path.basename(img_path)}"
                        pre_label = None

                        if stem in lbl_files:
                            lbl_content = zf.read(lbl_files[stem]).decode("utf-8")
                            anns = []
                            for line in lbl_content.strip().splitlines():
                                parts = line.split()
                                if len(parts) >= 5:
                                    cls_id = int(parts[0])
                                    cx, cy, w, h = map(float, parts[1:5])
                                    anns.append({
                                        "category": class_names[cls_id] if cls_id < len(class_names) else str(cls_id),
                                        "bbox_yolo": [cx, cy, w, h],
                                        "score": 1.0,
                                    })
                            if anns:
                                pre_label = {"format": "yolo", "annotations": anns}

                        task = Task(
                            project_id=project_id,
                            data={"file_name": img_path},
                            data_url=img_url,
                            task_metadata={"source": "yolo_import", "stem": stem},
                            pre_label_result=pre_label,
                            priority=priority,
                            status=TaskStatus.PENDING,
                        )
                        self.db.add(task)
                        result.success += 1
                    except Exception as e:
                        result.errors.append(f"{img_path}: {e}")

        except zipfile.BadZipFile:
            result.errors.append("Invalid ZIP file")

        project.total_items = (project.total_items or 0) + result.success
        self.db.commit()
        return result

    def import_csv(
        self,
        project_id: int,
        csv_content: str,
        text_column: str = "text",
        label_column: Optional[str] = None,
        priority: int = 5,
        golden_ratio: float = 0.05,
    ) -> ImportResult:
        """导入 CSV（文本/语料任务）"""
        result = ImportResult()
        project = self._get_project(project_id)
        if not project:
            result.errors.append(f"Project {project_id} not found")
            return result

        import random

        try:
            reader = csv.DictReader(StringIO(csv_content))
            rows = list(reader)
            result.total = len(rows)

            if not rows:
                return result

            if text_column not in (rows[0].keys() if rows else []):
                # Try first column
                text_column = list(rows[0].keys())[0]

            n_golden = max(1, int(len(rows) * golden_ratio))
            golden_idx = set(random.sample(range(len(rows)), min(n_golden, len(rows))))

            for i, row in enumerate(rows):
                text = row.get(text_column, "").strip()
                if not text:
                    result.skipped += 1
                    continue
                try:
                    pre_label = None
                    if label_column and label_column in row and row[label_column]:
                        pre_label = {
                            "format": "csv",
                            "label": row[label_column],
                            "score": 1.0,
                        }
                    task = Task(
                        project_id=project_id,
                        data={k: v for k, v in row.items()},
                        data_url=None,
                        task_metadata={"source": "csv_import", "row_index": i},
                        pre_label_result=pre_label,
                        priority=priority,
                        is_golden=(i in golden_idx),
                        status=TaskStatus.PENDING,
                    )
                    self.db.add(task)
                    result.success += 1
                except Exception as e:
                    result.errors.append(f"Row {i}: {e}")

        except Exception as e:
            result.errors.append(f"CSV parse error: {e}")

        project.total_items = (project.total_items or 0) + result.success
        self.db.commit()
        return result

    def import_jsonl(
        self,
        project_id: int,
        jsonl_content: str,
        priority: int = 5,
        golden_ratio: float = 0.05,
    ) -> ImportResult:
        """导入 JSONL（每行一个 JSON 对象，适合 QA 对、对话数据）"""
        result = ImportResult()
        project = self._get_project(project_id)
        if not project:
            result.errors.append(f"Project {project_id} not found")
            return result

        import random

        lines = [l.strip() for l in jsonl_content.splitlines() if l.strip()]
        result.total = len(lines)

        n_golden = max(1, int(len(lines) * golden_ratio))
        golden_idx = set(random.sample(range(len(lines)), min(n_golden, len(lines))))

        for i, line in enumerate(lines):
            try:
                obj = json.loads(line)
                task = Task(
                    project_id=project_id,
                    data=obj,
                    data_url=obj.get("url") or obj.get("image_url"),
                    task_metadata={"source": "jsonl_import", "line_index": i},
                    priority=priority,
                    is_golden=(i in golden_idx),
                    status=TaskStatus.PENDING,
                )
                self.db.add(task)
                result.success += 1
            except Exception as e:
                result.errors.append(f"Line {i}: {e}")

        project.total_items = (project.total_items or 0) + result.success
        self.db.commit()
        return result

    def import_embodied_episodes(
        self,
        project_id: int,
        payload: Any,
        priority: int = 5,
    ) -> ImportResult:
        """
        导入具身 episode。
        支持：
        - { "episodes": [ {...}, ... ] }
        - 单个 episode 对象（含 streams）
        - JSONL：每行一个 episode 或 {episode: ...}
        """
        result = ImportResult()
        project = self._get_project(project_id)
        if not project:
            result.errors.append(f"Project {project_id} not found")
            return result

        from app.services.embodied_episodes import normalize_episode

        episodes: List[Dict[str, Any]] = []
        if isinstance(payload, str):
            text = payload.strip()
            if not text:
                result.errors.append("空内容")
                return result
            if text.startswith("{"):
                try:
                    obj = json.loads(text)
                    if isinstance(obj, dict) and isinstance(obj.get("episodes"), list):
                        episodes = [e for e in obj["episodes"] if isinstance(e, dict)]
                    elif isinstance(obj, dict) and obj.get("streams"):
                        episodes = [obj]
                    else:
                        result.errors.append("JSON 需为 episode 或 {episodes:[...]}")
                        return result
                except json.JSONDecodeError:
                    # treat as jsonl
                    for i, line in enumerate(text.splitlines()):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            if isinstance(obj, dict) and isinstance(obj.get("embodied_episode"), dict):
                                episodes.append(obj["embodied_episode"])
                            elif isinstance(obj, dict) and obj.get("streams"):
                                episodes.append(obj)
                            elif isinstance(obj, dict) and isinstance(obj.get("episode"), dict):
                                episodes.append(obj["episode"])
                            else:
                                result.errors.append(f"Line {i}: not an episode")
                        except Exception as e:
                            result.errors.append(f"Line {i}: {e}")
            else:
                for i, line in enumerate(text.splitlines()):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict) and obj.get("streams"):
                            episodes.append(obj)
                        elif isinstance(obj, dict) and isinstance(obj.get("embodied_episode"), dict):
                            episodes.append(obj["embodied_episode"])
                        else:
                            result.errors.append(f"Line {i}: not an episode")
                    except Exception as e:
                        result.errors.append(f"Line {i}: {e}")
        elif isinstance(payload, dict):
            if isinstance(payload.get("episodes"), list):
                episodes = [e for e in payload["episodes"] if isinstance(e, dict)]
            elif payload.get("streams"):
                episodes = [payload]
            else:
                result.errors.append("无效 episode JSON")
                return result
        elif isinstance(payload, list):
            episodes = [e for e in payload if isinstance(e, dict)]
        else:
            result.errors.append("不支持的 payload 类型")
            return result

        result.total = len(episodes)
        for i, raw in enumerate(episodes):
            try:
                ep = normalize_episode(raw)
                streams = ep.get("streams") or []
                data_url = streams[0].get("src") if streams else None
                vla = {
                    "instruction": ep.get("instruction") or "",
                    "success": ep.get("success") if ep.get("success") in ("success", "fail", "unknown") else "unknown",
                    "segments": ep.get("segments") if isinstance(ep.get("segments"), list) else [],
                }
                # strip internal cache key from stored episode
                store_ep = {k: v for k, v in ep.items() if not str(k).startswith("_")}
                task = Task(
                    project_id=project_id,
                    data={
                        "embodied_episode": store_ep,
                        "embodied_slug": store_ep.get("case_id") or f"import_{i}",
                        "embodied_vla": vla,
                        "file_name": f"episode_{i}",
                    },
                    data_url=data_url,
                    task_metadata={
                        "source": "embodied_import",
                        "episode_index": i,
                        "has_proprioception": bool(ep.get("has_proprioception")),
                    },
                    priority=priority,
                    status=TaskStatus.PENDING,
                )
                self.db.add(task)
                result.success += 1
            except Exception as e:
                result.errors.append(f"Episode {i}: {e}")

        project.total_items = (project.total_items or 0) + result.success
        self.db.commit()
        return result

    def get_import_stats(self, project_id: int) -> Dict[str, Any]:
        """获取项目导入统计"""
        from sqlalchemy import func
        project = self._get_project(project_id)
        if not project:
            return {}

        total = self.db.query(Task).filter(Task.project_id == project_id).count()

        # Count by source
        tasks = self.db.query(Task).filter(Task.project_id == project_id).all()
        sources: Dict[str, int] = {}
        for t in tasks:
            meta = t.task_metadata or {}
            src = meta.get("source", "unknown")
            sources[src] = sources.get(src, 0) + 1

        return {
            "project_id": project_id,
            "total_tasks": total,
            "by_source": sources,
            "golden_count": sum(1 for t in tasks if t.is_golden),
            "pre_labeled_count": sum(1 for t in tasks if t.pre_label_result),
        }

    def _get_project(self, project_id: int) -> Optional[Project]:
        return self.db.query(Project).filter(Project.id == project_id).first()
