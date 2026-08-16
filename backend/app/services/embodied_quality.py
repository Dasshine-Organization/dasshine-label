"""具身标注质量摘要。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def compute_embodied_quality(
    payload: Optional[Dict[str, Any]] = None,
    *,
    vla: Optional[Dict[str, Any]] = None,
    episode: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """统计指令空缺、区间覆盖、抓取/轨迹/偏好、成败。"""
    payload = payload if isinstance(payload, dict) else {}
    vla = vla if isinstance(vla, dict) else {}
    episode = episode if isinstance(episode, dict) else {}

    instruction = str(
        payload.get("instruction")
        if payload.get("instruction") is not None
        else vla.get("instruction") or episode.get("instruction") or ""
    ).strip()
    success = str(payload.get("success") or vla.get("success") or "unknown")
    if success not in ("success", "fail", "unknown"):
        success = "unknown"

    segments: List[Dict[str, Any]] = []
    for s in payload.get("segments") or vla.get("segments") or []:
        if isinstance(s, dict):
            segments.append(s)
    grasps = payload.get("grasps") or vla.get("grasps") or []
    trajectory = payload.get("trajectory") or vla.get("trajectory") or []
    preferences = payload.get("preferences") or vla.get("preferences") or []
    frames = payload.get("frames") if isinstance(payload.get("frames"), list) else []
    total_frames = int(
        len(frames)
        or payload.get("total_frames")
        or episode.get("total_frames")
        or 0
    )

    covered = set()
    for s in segments:
        try:
            a = int(s.get("start_frame", 0))
            b = int(s.get("end_frame", a))
        except (TypeError, ValueError):
            continue
        if b < a:
            a, b = b, a
        for i in range(max(0, a), b + 1):
            covered.add(i)
    coverage = (len(covered) / total_frames) if total_frames > 0 else 0.0

    grasp_oob = 0
    for g in grasps:
        if not isinstance(g, dict):
            continue
        try:
            f = int(g.get("frame", 0))
        except (TypeError, ValueError):
            grasp_oob += 1
            continue
        if total_frames > 0 and (f < 0 or f >= total_frames):
            grasp_oob += 1

    return {
        "instruction_empty": not bool(instruction),
        "instruction_len": len(instruction),
        "success": success,
        "segment_count": len(segments),
        "segment_coverage": round(coverage, 4),
        "grasp_count": len(grasps) if isinstance(grasps, list) else 0,
        "grasp_out_of_bounds": grasp_oob,
        "trajectory_points": len(trajectory) if isinstance(trajectory, list) else 0,
        "preference_count": len(preferences) if isinstance(preferences, list) else 0,
        "total_frames": total_frames,
        "committed_frames": len(payload.get("committed_frames") or []),
    }
