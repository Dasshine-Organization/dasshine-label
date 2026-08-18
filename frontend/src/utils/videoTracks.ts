/** 视频多目标跟踪：关键帧包围盒（归一化 xywh 0–1）与线性插值。 */

export type TrackKeyframe = {
  t: number
  bbox: [number, number, number, number]
}

export type VideoTrack = {
  id: string
  track_id: number
  label: string
  color: string
  keyframes: TrackKeyframe[]
}

export function lerp(a: number, b: number, u: number) {
  return a + (b - a) * u
}

export function interpolateBbox(
  keyframes: TrackKeyframe[],
  t: number,
): [number, number, number, number] | null {
  if (!keyframes.length) return null
  const sorted = [...keyframes].sort((x, y) => x.t - y.t)
  if (t <= sorted[0].t) return sorted[0].bbox
  const last = sorted[sorted.length - 1]
  if (t >= last.t) return last.bbox
  for (let i = 0; i < sorted.length - 1; i++) {
    const a = sorted[i]
    const b = sorted[i + 1]
    if (t >= a.t && t <= b.t) {
      const span = b.t - a.t
      const u = span <= 1e-6 ? 0 : (t - a.t) / span
      return [
        lerp(a.bbox[0], b.bbox[0], u),
        lerp(a.bbox[1], b.bbox[1], u),
        lerp(a.bbox[2], b.bbox[2], u),
        lerp(a.bbox[3], b.bbox[3], u),
      ]
    }
  }
  return last.bbox
}

export function upsertKeyframe(track: VideoTrack, t: number, bbox: [number, number, number, number]): VideoTrack {
  const snapped = Math.round(t * 100) / 100
  const rest = track.keyframes.filter(k => Math.abs(k.t - snapped) > 0.04)
  return {
    ...track,
    keyframes: [...rest, { t: snapped, bbox }].sort((a, b) => a.t - b.t),
  }
}

export const TRACK_COLORS = ['#f59e0b', '#00d4ff', '#10b981', '#a78bfa', '#ef4444', '#ec4899', '#34d399']

export function nextTrackColor(existing: VideoTrack[]) {
  return TRACK_COLORS[existing.length % TRACK_COLORS.length]
}

export function nextTrackId(existing: VideoTrack[]) {
  return existing.reduce((m, t) => Math.max(m, t.track_id), 0) + 1
}
