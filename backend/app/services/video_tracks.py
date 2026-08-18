"""视频 MOT：关键帧包围盒线性插值。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

BBox = Tuple[float, float, float, float]


def interpolate_bbox(keyframes: Sequence[Dict[str, Any]], t: float) -> Optional[BBox]:
    if not keyframes:
        return None
    sorted_kf = sorted(
        (k for k in keyframes if isinstance(k, dict) and "bbox" in k),
        key=lambda k: float(k.get("t") or 0),
    )
    if not sorted_kf:
        return None

    def _bbox(k: Dict[str, Any]) -> BBox:
        b = k.get("bbox") or [0, 0, 0, 0]
        return (float(b[0]), float(b[1]), float(b[2]), float(b[3]))

    if t <= float(sorted_kf[0].get("t") or 0):
        return _bbox(sorted_kf[0])
    last = sorted_kf[-1]
    if t >= float(last.get("t") or 0):
        return _bbox(last)
    for i in range(len(sorted_kf) - 1):
        a, b = sorted_kf[i], sorted_kf[i + 1]
        ta, tb = float(a.get("t") or 0), float(b.get("t") or 0)
        if ta <= t <= tb:
            span = tb - ta
            u = 0.0 if span <= 1e-6 else (t - ta) / span
            ax, ay, aw, ah = _bbox(a)
            bx, by, bw, bh = _bbox(b)
            return (
                ax + (bx - ax) * u,
                ay + (by - ay) * u,
                aw + (bw - aw) * u,
                ah + (bh - ah) * u,
            )
    return _bbox(last)


def sampled_track_boxes(track: Dict[str, Any], fps: float = 5.0) -> List[Dict[str, Any]]:
    """按 fps 采样插值框，供 MOT / jsonl 导出。"""
    kfs = track.get("keyframes") or []
    if not isinstance(kfs, list) or not kfs:
        return []
    times = [float(k.get("t") or 0) for k in kfs if isinstance(k, dict)]
    if not times:
        return []
    t0, t1 = min(times), max(times)
    step = 1.0 / max(fps, 0.5)
    out: List[Dict[str, Any]] = []
    t = t0
    frame = 0
    while t <= t1 + 1e-6:
        box = interpolate_bbox(kfs, t)
        if box:
            out.append(
                {
                    "frame": frame,
                    "t": round(t, 3),
                    "bbox": [round(v, 4) for v in box],
                    "track_id": track.get("track_id"),
                    "label": track.get("label"),
                }
            )
        t += step
        frame += 1
    return out
