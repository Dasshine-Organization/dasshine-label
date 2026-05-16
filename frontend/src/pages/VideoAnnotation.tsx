import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import ModalityShell from '../components/annotation/ModalityShell'
import { useModalityWorkspace } from '../hooks/useModalityWorkspace'
import type { VideoClip } from '../services/modalityAnnotation'

function clipId() {
  return `clip_${Date.now().toString(36)}`
}

export default function VideoAnnotation() {
  const { taskId = '3003' } = useParams<{ taskId: string }>()
  const { ws, payload, updatePayload, loading, saving, lastSavedAt, useBackend, persist, submit } =
    useModalityWorkspace(taskId, 'video')
  const videoRef = useRef<HTMLVideoElement>(null)
  const [currentSec, setCurrentSec] = useState(0)
  const [duration, setDuration] = useState(0)
  const [clipStart, setClipStart] = useState<number | null>(null)

  const url = ws?.content.video_url ?? ''
  const clips = payload?.clips ?? []
  const annType = ws?.ann_type ?? 'video_action'

  function addClip() {
    const start = clipStart ?? Math.max(0, currentSec - 0.5)
    const end = Math.min(duration || currentSec + 2, currentSec + 2)
    if (end <= start) return
    const c: VideoClip = {
      id: clipId(),
      start_sec: Math.round(start * 100) / 100,
      end_sec: Math.round(end * 100) / 100,
      label: 'action',
      note: '',
    }
    updatePayload({ clips: [...clips, c].sort((a, b) => a.start_sec - b.start_sec) })
    setClipStart(null)
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
      lastSavedAt={lastSavedAt}
      onSave={() => persist(payload, false)}
      onSubmit={() => submit()}
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 h-full">
        <section className="lg:col-span-7 p-4 border-r border-[#1e1e2e] space-y-4 overflow-y-auto">
          <video
            ref={videoRef}
            src={url}
            controls
            className="w-full rounded-xl bg-black max-h-[50vh]"
            onTimeUpdate={() => setCurrentSec(videoRef.current?.currentTime ?? 0)}
            onLoadedMetadata={() => setDuration(videoRef.current?.duration ?? 0)}
          />
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
            <span className="text-white/30 self-center font-mono">
              {currentSec.toFixed(2)}s / {duration.toFixed(2)}s
            </span>
          </div>
          {annType === 'video_caption' && (
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
        </aside>
      </div>
    </ModalityShell>
  )
}
