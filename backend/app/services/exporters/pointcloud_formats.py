"""点云 3D：KITTI / OpenPCDet / CSV。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.exporters.common import (
    dumps_json,
    extract_boxes3d,
    rows_to_csv,
    task_file_name,
    zip_files,
)
from app.services.exporters.types import ExportArtifact


def export_kitti(tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None) -> ExportArtifact:
    _ = label_classes, project_name
    files: Dict[str, bytes] = {}
    for task in tasks:
        stem = task_file_name(task).rsplit(".", 1)[0]
        lines: List[str] = []
        for b in extract_boxes3d(task):
            # KITTI: type truncated occluded alpha bbox2d h w l x y z yaw
            line = (
                f"{b['label']} 0.00 0 -10.00 0.00 0.00 0.00 0.00 "
                f"{b['dy']:.2f} {b['dz']:.2f} {b['dx']:.2f} "
                f"{b['x']:.2f} {b['y']:.2f} {b['z']:.2f} {b['yaw']:.2f}"
            )
            lines.append(line)
        files[f"label_2/{stem}.txt"] = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
        if getattr(task, "data_url", None):
            files[f"velodyne_urls/{stem}.txt"] = str(task.data_url).encode("utf-8")
    return ExportArtifact(
        content=zip_files(files),
        filename_suffix="_kitti.zip",
        media_type="application/zip",
    )


def export_openpcdet(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes
    infos = []
    for task in tasks:
        boxes = extract_boxes3d(task)
        gt_boxes = [[b["x"], b["y"], b["z"], b["dx"], b["dy"], b["dz"], b["yaw"]] for b in boxes]
        infos.append(
            {
                "point_cloud": {
                    "lidar_idx": str(task.id),
                    "num_features": 4,
                },
                "annos": {
                    "name": [b["label"] for b in boxes],
                    "gt_boxes_lidar": gt_boxes,
                    "score": [b.get("score") for b in boxes],
                },
                "frame_id": task_file_name(task),
                "data_url": getattr(task, "data_url", None),
                "task_id": task.id,
            }
        )
    payload = {
        "schema": "dasshine.openpcdet_lite.v1",
        "project": project_name,
        "infos": infos,
    }
    return ExportArtifact(
        content=dumps_json(payload),
        filename_suffix="_openpcdet.json",
        media_type="application/json",
    )


def export_pointcloud_csv(
    tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None
) -> ExportArtifact:
    _ = label_classes, project_name
    rows: List[List[Any]] = []
    for task in tasks:
        boxes = extract_boxes3d(task)
        if not boxes:
            rows.append([task.id, task_file_name(task), getattr(task, "data_url", ""), "", "", "", "", "", "", ""])
            continue
        for b in boxes:
            rows.append(
                [
                    task.id,
                    task_file_name(task),
                    getattr(task, "data_url", ""),
                    b["label"],
                    b["x"],
                    b["y"],
                    b["z"],
                    b["dx"],
                    b["dy"],
                    b["dz"],
                    b["yaw"],
                ]
            )
    text = rows_to_csv(
        ["task_id", "file_name", "data_url", "label", "x", "y", "z", "dx", "dy", "dz", "yaw"],
        rows,
    )
    return ExportArtifact(
        content=text.encode("utf-8"),
        filename_suffix="_pointcloud.csv",
        media_type="text/csv",
    )
