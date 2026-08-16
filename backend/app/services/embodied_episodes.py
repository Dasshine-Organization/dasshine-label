"""
内置具身演示 episode 配置（与前端 embodiedDemoData 对齐）
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

MARS_ARM_DEMO_WEBM = (
    "https://upload.wikimedia.org/wikipedia/commons/b/bb/"
    "PIA24664-MarsInSightLander-CleaningSolarPanel-20210522.webm"
)
ALOHA_CHUNK0 = (
    "https://huggingface.co/datasets/lerobot/aloha_static_coffee/"
    "resolve/main/videos/chunk-000"
)
ALOHA_CHUNK0_MIRROR = (
    "https://hf-mirror.com/datasets/lerobot/aloha_static_coffee/"
    "resolve/main/videos/chunk-000"
)

DEFAULT_ACTION_LABELS: List[Dict[str, str]] = [
    {"id": "idle", "label": "待机"},
    {"id": "reach", "label": "伸手接近"},
    {"id": "align", "label": "对准目标"},
    {"id": "grasp", "label": "闭合抓取"},
    {"id": "lift", "label": "抬升"},
    {"id": "transport", "label": "移运"},
    {"id": "place", "label": "放置释放"},
    {"id": "retract", "label": "回原点"},
]

JOINT_NAMES = [
    "base_yaw",
    "shoulder_pitch",
    "elbow_pitch",
    "wrist_pitch",
    "wrist_roll",
    "gripper",
]


def _mars_episode() -> Dict[str, Any]:
    clip_duration_sec = 2.0
    fps = 12
    total_frames = round(clip_duration_sec * fps)
    return {
        "case_id": "mars",
        "project_name": "具身示例 · InSight 机械臂（单源多裁剪）",
        "clip_duration_sec": clip_duration_sec,
        "fps": fps,
        "total_frames": total_frames,
        "streams": [
            {"id": "cam_main", "label": "主视角", "src": MARS_ARM_DEMO_WEBM, "object_position": "50% 52%"},
            {"id": "cam_arm", "label": "机械臂区域", "src": MARS_ARM_DEMO_WEBM, "object_position": "58% 62%", "scale": 1.45},
            {"id": "cam_panel", "label": "太阳能板", "src": MARS_ARM_DEMO_WEBM, "object_position": "42% 38%", "scale": 1.25},
            {"id": "cam_left", "label": "左侧取景", "src": MARS_ARM_DEMO_WEBM, "object_position": "28% 55%", "scale": 1.2},
            {"id": "cam_top", "label": "偏俯视", "src": MARS_ARM_DEMO_WEBM, "object_position": "50% 35%", "scale": 1.15},
            {"id": "cam_coarse", "label": "远景", "src": MARS_ARM_DEMO_WEBM, "object_position": "50% 50%", "scale": 1.0},
            {"id": "cam_far_left", "label": "极左带", "src": MARS_ARM_DEMO_WEBM, "object_position": "18% 48%", "scale": 1.12},
            {"id": "cam_far_right", "label": "极右带", "src": MARS_ARM_DEMO_WEBM, "object_position": "82% 52%", "scale": 1.12},
        ],
        "attribution": {
            "title": "PIA24664 — InSight lander cleaning solar panel with sand (2021-05-22)",
            "detail_url": (
                "https://commons.wikimedia.org/wiki/"
                "File:PIA24664-MarsInSightLander-CleaningSolarPanel-20210522.webm"
            ),
            "note": "NASA / JPL-Caltech · 公有领域 · 本页仅截取前 2s 作标注演示",
        },
    }


def _aloha_episode() -> Dict[str, Any]:
    clip_duration_sec = 2.0
    fps = 12
    total_frames = round(clip_duration_sec * fps)

    def cam(cam_id: str, label: str) -> Dict[str, Any]:
        path = f"observation.images.{cam_id}"
        return {
            "id": cam_id,
            "label": label,
            "src": f"{ALOHA_CHUNK0}/{path}/episode_000000.mp4",
            "fallback_src": f"{ALOHA_CHUNK0_MIRROR}/{path}/episode_000000.mp4",
        }

    return {
        "case_id": "aloha",
        "project_name": "多视角案例 · ALOHA 制咖啡（LeRobot 四路真实相机）",
        "clip_duration_sec": clip_duration_sec,
        "fps": fps,
        "total_frames": total_frames,
        "streams": [
            cam("cam_high", "高位全局"),
            cam("cam_low", "低位全局"),
            cam("cam_left_wrist", "左腕第一视角"),
            cam("cam_right_wrist", "右腕第一视角"),
        ],
        "attribution": {
            "title": "lerobot/aloha_static_coffee — episode 000000",
            "detail_url": "https://huggingface.co/datasets/lerobot/aloha_static_coffee",
            "note": (
                "四路为不同 MP4（同一 episode）。主站 huggingface.co；"
                "失败时将自动尝试 hf-mirror.com。"
            ),
        },
    }


def episode_for_slug(slug: str) -> Dict[str, Any]:
    if slug in ("2002", "embodied-aloha", "aloha"):
        return _aloha_episode()
    return _mars_episode()


def episode_from_task_data(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not data:
        return None
    ep = data.get("embodied_episode")
    if isinstance(ep, dict) and ep.get("streams"):
        return normalize_episode(ep)
    return None


def normalize_episode(ep: Dict[str, Any]) -> Dict[str, Any]:
    """补齐自定义 episode 必填字段，保留 proprioception / instruction。"""
    out = dict(ep)
    out.setdefault("case_id", str(ep.get("case_id") or "custom"))
    out.setdefault("project_name", str(ep.get("project_name") or "Embodied episode"))
    fps = int(ep.get("fps") or 12)
    clip = float(ep.get("clip_duration_sec") or 0)
    total = int(ep.get("total_frames") or 0)
    if total <= 0 and clip > 0:
        total = max(1, round(clip * fps))
    if clip <= 0 and total > 0:
        clip = total / max(1, fps)
    if total <= 0:
        total = 24
        clip = clip or 2.0
    out["fps"] = fps
    out["clip_duration_sec"] = clip
    out["total_frames"] = total
    out.setdefault("instruction", ep.get("instruction") or ep.get("task") or "")
    out.setdefault("success", ep.get("success") or "unknown")
    if not isinstance(out.get("attribution"), dict):
        out["attribution"] = {
            "title": out.get("project_name") or "custom episode",
            "detail_url": "",
            "note": "imported episode",
        }
    streams = []
    for s in ep.get("streams") or []:
        if not isinstance(s, dict) or not s.get("src"):
            continue
        row = {
            "id": str(s.get("id") or f"cam{len(streams)}"),
            "label": str(s.get("label") or s.get("id") or "cam"),
            "src": str(s.get("src")),
        }
        if s.get("fallback_src"):
            row["fallback_src"] = str(s.get("fallback_src"))
        if s.get("object_position"):
            row["object_position"] = str(s.get("object_position"))
        if s.get("scale") is not None:
            try:
                row["scale"] = float(s.get("scale"))
            except (TypeError, ValueError):
                pass
        intr = s.get("intrinsics")
        if isinstance(intr, dict):
            row["intrinsics"] = {
                "fx": float(intr.get("fx", 0) or 0),
                "fy": float(intr.get("fy", 0) or 0),
                "cx": float(intr.get("cx", 0) or 0),
                "cy": float(intr.get("cy", 0) or 0),
                "width": float(intr.get("width", 0) or 0),
                "height": float(intr.get("height", 0) or 0),
            }
        extr = s.get("extrinsics")
        if isinstance(extr, dict):
            pos = extr.get("position") if isinstance(extr.get("position"), dict) else {}
            ori = extr.get("orientation") if isinstance(extr.get("orientation"), dict) else {}
            row["extrinsics"] = {
                "position": {
                    "x": float(pos.get("x", 0) or 0),
                    "y": float(pos.get("y", 0) or 0),
                    "z": float(pos.get("z", 0) or 0),
                },
                "orientation": {
                    "roll": float(ori.get("roll", 0) or 0),
                    "pitch": float(ori.get("pitch", 0) or 0),
                    "yaw": float(ori.get("yaw", 0) or 0),
                },
            }
        streams.append(row)
    if streams:
        out["streams"] = streams
    # index proprioception by frame for fast lookup
    prop = ep.get("proprioception") or ep.get("frames_proprio") or []
    by_idx: Dict[int, Dict[str, Any]] = {}
    if isinstance(prop, list):
        for row in prop:
            if not isinstance(row, dict):
                continue
            try:
                idx = int(row.get("index", row.get("frame_index", -1)))
            except (TypeError, ValueError):
                continue
            if idx < 0:
                continue
            by_idx[idx] = row
    out["_proprio_by_index"] = by_idx
    out["has_proprioception"] = bool(by_idx)
    return out


def resolve_episode(task_data: Optional[Dict[str, Any]], slug: Optional[str]) -> Dict[str, Any]:
    custom = episode_from_task_data(task_data)
    if custom:
        return custom
    return normalize_episode(episode_for_slug(slug or "demo"))
