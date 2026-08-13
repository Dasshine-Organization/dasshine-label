"""图像 2D：COCO / YOLO / VOC。"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from xml.dom import minidom

from app.services.coco_export import build_coco_from_tasks
from app.services.exporters.common import (
    bbox_xywh,
    build_class_map,
    class_names_ordered,
    dumps_json,
    extract_boxes2d,
    task_file_name,
    task_image_size,
    zip_files,
)
from app.services.exporters.types import ExportArtifact


def export_coco(tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None) -> ExportArtifact:
    coco = build_coco_from_tasks(tasks, project_name, label_classes)
    return ExportArtifact(
        content=dumps_json(coco),
        filename_suffix="_coco.json",
        media_type="application/json",
    )


def export_yolo(tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None) -> ExportArtifact:
    discovered = []
    for task in tasks:
        for box in extract_boxes2d(task):
            discovered.append(str(box.get("label") or box.get("category") or "object"))
    cat_map = build_class_map(label_classes, discovered)
    names = class_names_ordered(cat_map)

    files: Dict[str, bytes] = {
        "classes.txt": ("\n".join(names) + ("\n" if names else "")).encode("utf-8"),
        "manifest.json": dumps_json(
            {
                "schema": "dasshine.yolo_export.v1",
                "project": project_name,
                "classes": names,
                "note": "labels use normalized cx cy w h when image size known; else pixel xywh in comment line",
            }
        ),
    }

    for task in tasks:
        stem = task_file_name(task).rsplit(".", 1)[0]
        w, h = task_image_size(task, None)
        lines: List[str] = []
        for box in extract_boxes2d(task):
            xywh = bbox_xywh(box)
            if not xywh:
                continue
            x, y, bw, bh = xywh
            label = str(box.get("label") or box.get("category") or "object")
            cls_id = cat_map.get(label, 0)
            if w > 0 and h > 0:
                cx = (x + bw / 2) / w
                cy = (y + bh / 2) / h
                nw = bw / w
                nh = bh / h
                lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
            else:
                lines.append(f"{cls_id} {x:.2f} {y:.2f} {bw:.2f} {bh:.2f}  # pixel_xywh size_unknown")
        files[f"labels/{stem}.txt"] = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
        if getattr(task, "data_url", None):
            files[f"images_urls/{stem}.txt"] = str(task.data_url).encode("utf-8")

    return ExportArtifact(
        content=zip_files(files),
        filename_suffix="_yolo.zip",
        media_type="application/zip",
    )


def _xml_escape_text(elem: ET.Element) -> str:
    rough = ET.tostring(elem, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def export_voc(tasks: List[Any], project_name: str, label_classes: Optional[List[Dict]] = None) -> ExportArtifact:
    _ = label_classes
    files: Dict[str, bytes] = {}
    for task in tasks:
        file_name = task_file_name(task)
        w, h = task_image_size(task, None)
        root = ET.Element("annotation")
        ET.SubElement(root, "folder").text = project_name
        ET.SubElement(root, "filename").text = file_name
        ET.SubElement(root, "path").text = getattr(task, "data_url", None) or file_name
        source = ET.SubElement(root, "source")
        ET.SubElement(source, "database").text = "Dasshine"
        size_el = ET.SubElement(root, "size")
        ET.SubElement(size_el, "width").text = str(w or 0)
        ET.SubElement(size_el, "height").text = str(h or 0)
        ET.SubElement(size_el, "depth").text = "3"
        ET.SubElement(root, "segmented").text = "0"

        for box in extract_boxes2d(task):
            xywh = bbox_xywh(box)
            if not xywh:
                continue
            x, y, bw, bh = xywh
            obj = ET.SubElement(root, "object")
            ET.SubElement(obj, "name").text = str(box.get("label") or box.get("category") or "object")
            ET.SubElement(obj, "pose").text = "Unspecified"
            ET.SubElement(obj, "truncated").text = "0"
            ET.SubElement(obj, "difficult").text = "0"
            bnd = ET.SubElement(obj, "bndbox")
            ET.SubElement(bnd, "xmin").text = str(int(round(x)))
            ET.SubElement(bnd, "ymin").text = str(int(round(y)))
            ET.SubElement(bnd, "xmax").text = str(int(round(x + bw)))
            ET.SubElement(bnd, "ymax").text = str(int(round(y + bh)))

        stem = file_name.rsplit(".", 1)[0]
        xml_str = _xml_escape_text(root)
        # strip XML declaration duplicate if minidom adds it
        files[f"Annotations/{stem}.xml"] = xml_str.encode("utf-8")

    return ExportArtifact(
        content=zip_files(files),
        filename_suffix="_voc.zip",
        media_type="application/zip",
    )
