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
        return ep
    return None


def resolve_episode(task_data: Optional[Dict[str, Any]], slug: Optional[str]) -> Dict[str, Any]:
    custom = episode_from_task_data(task_data)
    if custom:
        return custom
    return episode_for_slug(slug or "demo")
