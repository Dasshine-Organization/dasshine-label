import { useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import ModalityShell from '../components/annotation/ModalityShell'
import ProjectExportMenu from '../components/dataset/ProjectExportMenu'
import { useModalityWorkspace } from '../hooks/useModalityWorkspace'
import { getAnnotateBackHref } from '../utils/annotationRoutes'
import type { VideoClip } from '../services/modalityAnnotation'
import {
  interpolateBbox,
  nextTrackColor,
  nextTrackId,
  upsertKeyframe,
  type VideoTrack,
} from '../utils/videoTracks'

function clipId() {
  return `clip_${Date.now().toString(36)}`
}

function trackUid() {
  return `trk_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
}

export default function VideoAnnotation() {
  const { taskId = '3003' } = useParams<{ taskId: string }>()
  const [searchParams] = useSearchParams()
  const projectIdParam = searchParams.get('projectId')
  const { ws, payload, updatePayload, loading, saving, dirty, lastSavedAt, useBackend, persist, submit, lock, lockBlocked, peers, connected } =
    useModalityWorkspace(taskId, 'video')
  const videoRef = useRef<HTMLVideoElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const [currentSec, setCurrentSec] = useState(0)
  const [duration, setDuration] = useState(0)
  const [clipStart, setClipStart] = useState<number | null>(null)
  const [activeTrackId, setActiveTrackId] = useState<string | null>(null)
  const [drawing, setDrawing] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null)
  const [paused, setPaused] = useState(true)

  const url = ws?.content.video_url ?? ''
  const clips = payload?.clips ?? []
  const tracks: VideoTrack[] = (payload?.tracks ?? []) as VideoTrack[]
  const labels = ws?.label_classes ?? []
  const annType = ws?.ann_type ?? 'video_action'
  const isTracking = annType === 'video_tracking'
  const isCaption = annType === 'video_caption'
  const backHref = getAnnotateBackHref({
    projectId: projectIdParam ?? ws?.project_id,
    category: ws?.category ?? 'video',
  })

  function addClip() {
    const start = clipStart ?? Math.max(0, currentSec - 0.5)
    const end = Math.min(duration || currentSec + 2, currentSec + 2)
    if (end <= start) return
    const c: VideoClip = {
      id: clipId(),
      start_sec: Math.round(start * 100) / 100,
      end_sec: Math.round(end * 100) / 100,
      label: labels[0]?.name || labels[0]?.id || 'action',
      note: '',
    }
    updatePayload({ clips: [...clips, c].sort((a, b) => a.start_sec - b.start_sec) })
    setClipStart(null)
  }

  function addTrack() {
    const id = trackUid()
    const track: VideoTrack = {
      id,
      track_id: nextTrackId(tracks),
      label: labels[0]?.name || labels[0]?.id || 'object',
      color: nextTrackColor(tracks),
      keyframes: [],
    }
    updatePayload({ tracks: [...tracks, track] })
    setActiveTrackId(id)
    videoRef.current?.pause()
  }

  function patchTrack(id: string, patch: Partial<VideoTrack>) {
    updatePayload({ tracks: tracks.map(t => (t.id === id ? { ...t, ...patch } : t)) })
  }

  function toNorm(clientX: number, clientY: number) {
    const box = overlayRef.current
    if (!box) return { x: 0, y: 0 }
    const r = box.getBoundingClientRect()
    return {
      x: Math.max(0, Math.min(1, (clientX - r.left) / Math.max(1, r.width))),
      y: Math.max(0, Math.min(1, (clientY - r.top) / Math.max(1, r.height))),
    }
  }

  function onPointerDown(e: React.PointerEvent) {
    if (!isTracking || !paused || e.button !== 0) return
    let tid = activeTrackId
    if (!tid) {
      const id = trackUid()
      const track: VideoTrack = {
        id,
        track_id: nextTrackId(tracks),
        label: labels[0]?.name || 'object',
        color: nextTrackColor(tracks),
        keyframes: [],
      }
      updatePayload({ tracks: [...tracks, track] })
      setActiveTrackId(id)
      tid = id
    }
    const p = toNorm(e.clientX, e.clientY)
    setDrawing({ x0: p.x, y0: p.y, x1: p.x, y1: p.y })
    ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
  }

  function onPointerMove(e: React.PointerEvent) {
    if (!drawing) return
    const p = toNorm(e.clientX, e.clientY)
    setDrawing({ ...drawing, x1: p.x, y1: p.y })
  }

  function onPointerUp() {
    if (!drawing || !activeTrackId) {
      setDrawing(null)
      return
    }
    const x = Math.min(drawing.x0, drawing.x1)
    const y = Math.min(drawing.y0, drawing.y1)
    const w = Math.abs(drawing.x1 - drawing.x0)
    const h = Math.abs(drawing.y1 - drawing.y0)
    setDrawing(null)
    if (w < 0.01 || h < 0.01) return
    const track = tracks.find(t => t.id === activeTrackId)
    if (!track) return
    patchTrack(activeTrackId, upsertKeyframe(track, currentSec, [x, y, w, h]))
  }

  if (loading || !payload) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0a0a0f] text-white/40 text-sm">
        加载视频工作区…
      </div>
    )
  }

  return (
    <ModalityShell
      title={`视频标注 · ${ws?.project_name ?? taskId}`}
      subtitle={`${annType} · task #${taskId}`}
      accent="#f59e0b"
      useBackend={useBackend}
      saving={saving}
      dirty={dirty}
      lastSavedAt={lastSavedAt}
      onSave={() => persist(payload, false)}
      onSubmit={() => submit()}
      backHref={backHref}
      backLabel="← 返回"
      lock={lock}
      lockBlocked={lockBlocked}
      peers={peers}
      connected={connected}
      headerExtra={
        <ProjectExportMenu
          projectId={projectIdParam ?? ws?.project_id}
          projectName={ws?.project_name}
          compact
        />
      }
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 h-full">
        <section className="lg:col-span-7 p-4 border-r border-[#1e1e2e] space-y-4 overflow-y-auto">
          <div className="relative w-full bg-black rounded-xl overflow-hidden">
            <video
              ref={videoRef}
              src={url}
              controls
              className="w-full max-h-[50vh] block"
              onTimeUpdate={() => setCurrentSec(videoRef.current?.currentTime ?? 0)}
              onLoadedMetadata={() => setDuration(videoRef.current?.duration ?? 0)}
              onPause={() => setPaused(true)}
              onPlay={() => setPaused(false)}
            />
            {isTracking && (
              <div
                ref={overlayRef}
                className="absolute inset-0 bottom-12 z-10"
                style={{ pointerEvents: paused ? 'auto' : 'none', cursor: paused ? 'crosshair' : 'default' }}
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
              >
                {tracks.map(tr => {
                  const box = interpolateBbox(tr.keyframes, currentSec)
                  if (!box) return null
                  const [x, y, w, h] = box
                  return (
                    <div
                      key={tr.id}
                      className="absolute border-2 pointer-events-none"
                      style={{
                        left: `${x * 100}%`,
                        top: `${y * 100}%`,
                        width: `${w * 100}%`,
                        height: `${h * 100}%`,
                        borderColor: tr.color,
                        boxShadow: tr.id === activeTrackId ? `0 0 0 1px ${tr.color}` : undefined,
                      }}
                    >
                      <span
                        className="absolute -top-5 left-0 text-[10px] px-1 font-mono"
                        style={{ background: tr.color, color: '#0a0a0f' }}
                      >
                        #{tr.track_id} {tr.label}
                      </span>
                    </div>
                  )
                })}
                {drawing && (
                  <div
                    className="absolute border border-dashed border-white/70 pointer-events-none"
                    style={{
                      left: `${Math.min(drawing.x0, drawing.x1) * 100}%`,
                      top: `${Math.min(drawing.y0, drawing.y1) * 100}%`,
                      width: `${Math.abs(drawing.x1 - drawing.x0) * 100}%`,
                      height: `${Math.abs(drawing.y1 - drawing.y0) * 100}%`,
                    }}
                  />
                )}
              </div>
            )}
          </div>
          <div className="relative h-10 bg-[#12121a] rounded-lg border border-[#1e1e2e] overflow-hidden">
            {clips.map(c => {
              const left = duration ? (c.start_sec / duration) * 100 : 0
              const w = duration ? ((c.end_sec - c.start_sec) / duration) * 100 : 5
              return (
                <div
                  key={c.id}
                  className="absolute top-1 bottom-1 rounded bg-[#f59e0b]/35 border border-[#f59e0b]/50"
                  style={{ left: `${left}%`, width: `${Math.max(w, 1)}%` }}
                />
              )
            })}
            {duration > 0 && (
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-white"
                style={{ left: `${(currentSec / duration) * 100}%` }}
              />
            )}
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            {isTracking && (
              <>
                <button
                  type="button"
                  className="px-3 py-1.5 rounded-lg bg-[#f59e0b]/15 border border-[#f59e0b]/35 text-[#fbbf24]"
                  onClick={addTrack}
                >
                  新建轨迹
                </button>
                <span className="text-white/35 self-center">
                  {paused ? '暂停后拖拽画框，写入当前时间关键帧（线性插值）' : '播放中显示插值框'}
                </span>
              </>
            )}
            {!isCaption && (
              <>
                <button
                  type="button"
                  className="px-3 py-1.5 rounded-lg border border-[#f59e0b]/40 text-[#f59e0b]"
                  onClick={() => setClipStart(currentSec)}
                >
                  片段起点 {clipStart != null ? `(${clipStart.toFixed(2)}s)` : ''}
                </button>
                <button
                  type="button"
                  className="px-3 py-1.5 rounded-lg bg-[#f59e0b]/15 border border-[#f59e0b]/35 text-[#fbbf24]"
                  onClick={addClip}
                >
                  添加动作片段
                </button>
              </>
            )}
            <span className="text-white/30 self-center font-mono">
              {currentSec.toFixed(2)}s / {duration.toFixed(2)}s
            </span>
          </div>
          {isCaption && (
            <div>
              <label className="text-xs text-white/40">视频描述 / 字幕</label>
              <textarea
                rows={4}
                className="mt-1 w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm resize-none"
                value={payload.caption ?? ''}
                onChange={e => updatePayload({ caption: e.target.value })}
              />
            </div>
          )}
        </section>
        <aside className="lg:col-span-5 p-4 overflow-y-auto space-y-3">
          {isTracking && (
            <>
              <div className="text-[11px] text-white/40 uppercase tracking-widest">
                轨迹 ({tracks.length})
              </div>
              {tracks.map(tr => (
                <div
                  key={tr.id}
                  className={`p-3 rounded-xl border bg-[#12121a] space-y-2 ${
                    tr.id === activeTrackId ? 'border-[#f59e0b]/50' : 'border-[#1e1e2e]'
                  }`}
                >
                  <div className="flex justify-between items-center text-[10px] font-mono text-white/35">
                    <button type="button" onClick={() => setActiveTrackId(tr.id)} style={{ color: tr.color }}>
                      #{tr.track_id} · {tr.keyframes.length} 关键帧
                    </button>
                    <button
                      type="button"
                      className="text-red-400/80"
                      onClick={() => {
                        updatePayload({ tracks: tracks.filter(x => x.id !== tr.id) })
                        if (activeTrackId === tr.id) setActiveTrackId(null)
                      }}
                    >
                      删
                    </button>
                  </div>
                  <input
                    className="w-full text-xs bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1"
                    value={tr.label}
                    onChange={e => patchTrack(tr.id, { label: e.target.value })}
                    placeholder="类别"
                  />
                </div>
              ))}
            </>
          )}
          {!isCaption && (
            <>
              <div className="text-[11px] text-white/40 uppercase tracking-widest">
                时序片段 ({clips.length})
              </div>
              {clips.map(c => (
                <div key={c.id} className="p-3 rounded-xl border border-[#1e1e2e] bg-[#12121a] space-y-2">
                  <div className="flex justify-between text-[10px] font-mono text-white/35">
                    <span>
                      {c.start_sec.toFixed(2)}s – {c.end_sec.toFixed(2)}s
                    </span>
                    <button
                      type="button"
                      className="text-red-400/80"
                      onClick={() => updatePayload({ clips: clips.filter(x => x.id !== c.id) })}
                    >
                      删
                    </button>
                  </div>
                  <input
                    className="w-full text-xs bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1"
                    value={c.label}
                    onChange={e =>
                      updatePayload({
                        clips: clips.map(x => (x.id === c.id ? { ...x, label: e.target.value } : x)),
                      })
                    }
                    placeholder="动作标签"
                  />
                  <textarea
                    rows={2}
                    className="w-full text-xs bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-2 py-1.5 resize-none"
                    value={c.note ?? ''}
                    onChange={e =>
                      updatePayload({
                        clips: clips.map(x => (x.id === c.id ? { ...x, note: e.target.value } : x)),
                      })
                    }
                    placeholder="备注"
                  />
                </div>
              ))}
            </>
          )}
        </aside>
      </div>
    </ModalityShell>
  )
}
