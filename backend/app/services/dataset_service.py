"""
数据集导入服务
支持：
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

logger = logging.getLogger(__name__)

# ── Supported formats ─────────────────────────────────────────────────────────

IMAGE_EXTS  = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
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
        return {
            "batch_id":   self.batch_id,
            "total":      self.total,
            "success":    self.success,
            "skipped":    self.skipped,
            "errors":     self.errors[:20],
            "started_at": self.started_at,
            "finished_at": datetime.utcnow().isoformat(),
        }


class DatasetImportService:

    def __init__(self, db: Session):
        self.db = db

    # ── Entry point ───────────────────────────────────────────────────────────

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
        文件保存逻辑：实际项目替换为 S3/OSS 上传，此处存相对路径
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
                        # 在实际项目中这里上传到对象存储
                        fake_url = f"{base_url_prefix}/{name}"
                        task = Task(
                            project_id=project_id,
                            data={"filename": name},
                            data_url=fake_url,
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
                        img_url = f"{base_url_prefix}/{img_path}"
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
