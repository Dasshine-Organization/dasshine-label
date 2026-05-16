import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import ModalityShell from '../components/annotation/ModalityShell'
import { useModalityWorkspace } from '../hooks/useModalityWorkspace'
import type { AudioSegment } from '../services/modalityAnnotation'

function segId() {
  return `seg_${Date.now().toString(36)}`
}

export default function AudioAnnotation() {
  const { taskId = '3002' } = useParams<{ taskId: string }>()
  const { ws, payload, updatePayload, loading, saving, useBackend, persist, submit } =
    useModalityWorkspace(taskId, 'audio')
  const audioRef = useRef<HTMLAudioElement>(null)
  const [currentMs, setCurrentMs] = useState(0)
  const [durationMs, setDurationMs] = useState(0)
  const [markStart, setMarkStart] = useState<number | null>(null)

  const url = ws?.content.audio_url ?? ''
  const segments = payload?.segments ?? []
  const speakers = payload?.speakers ?? ['说话人 A', '说话人 B']
  const annType = ws?.ann_type ?? 'asr'

  function addSegment(endMs?: number) {
    const start = markStart ?? currentMs
    const end = endMs ?? Math.min(durationMs || currentMs + 3000, currentMs + 3000)
    if (end <= start) return
    const seg: AudioSegment = {
      id: segId(),
      start_ms: Math.round(start),
      end_ms: Math.round(end),
      speaker: speakers[0] ?? '说话人 A',
      text: '',
    }
    updatePayload({ segments: [...segments, seg].sort((a, b) => a.start_ms - b.start_ms) })
    setMarkStart(null)
  }

  function updateSeg(id: string, patch: Partial<AudioSegment>) {
    updatePayload({
      segments: segments.map(s => (s.id === id ? { ...s, ...patch } : s)),
    })
  }

  if (loading || !payload) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0a0a0f] text-white/40 text-sm">
        加载语音工作区…
      </div>
    )
  }

  return (
    <ModalityShell
      title={`语音标注 · ${ws?.project_name ?? taskId}`}
      subtitle={`${annType} · task #${taskId}`}
      accent="#10b981"
      useBackend={useBackend}
      saving={saving}
      onSave={() => persist(payload, false)}
      onSubmit={() => submit()}
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 h-full">
        <section className="lg:col-span-7 p-4 border-r border-[#1e1e2e] flex flex-col gap-4 overflow-y-auto">
          <audio
            ref={audioRef}
            src={url}
            controls
            className="w-full"
            onTimeUpdate={() => setCurrentMs((audioRef.current?.currentTime ?? 0) * 1000)}
            onLoadedMetadata={() => setDurationMs((audioRef.current?.duration ?? 0) * 1000)}
          />
          <div className="rounded-xl border border-[#1e1e2e] bg-[#12121a] p-3">
            <div className="flex justify-between text-[10px] text-white/35 font-mono mb-2">
              <span>{(currentMs / 1000).toFixed(2)}s</span>
              <span>{(durationMs / 1000).toFixed(2)}s</span>
            </div>
            <div className="relative h-12 bg-[#0a0a0f] rounded-lg overflow-hidden">
              {segments.map(s => {
                const left = durationMs ? (s.start_ms / durationMs) * 100 : 0
                const width = durationMs ? ((s.end_ms - s.start_ms) / durationMs) * 100 : 5
                return (
                  <div
                    key={s.id}
                    className="absolute top-1 bottom-1 rounded bg-[#10b981]/40 border border-[#10b981]/60"
                    style={{ left: `${left}%`, width: `${Math.max(width, 1)}%` }}
                    title={`${s.speaker}: ${s.text}`}
                  />
                )
              })}
              {durationMs > 0 && (
                <div
                  className="absolute top-0 bottom-0 w-0.5 bg-white/80"
                  style={{ left: `${(currentMs / durationMs) * 100}%` }}
                />
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="text-xs px-3 py-1.5 rounded-lg border border-[#10b981]/40 text-[#10b981]"
              onClick={() => setMarkStart(currentMs)}
            >
              标记起点 {(markStart != null ? `(${(markStart / 1000).toFixed(1)}s)` : '')}
            </button>
            <button
              type="button"
              className="text-xs px-3 py-1.5 rounded-lg bg-[#10b981]/15 text-[#10b981] border border-[#10b981]/35"
              onClick={() => addSegment()}
            >
              添加片段到当前位置
            </button>
          </div>
          {annType === 'asr' && (
            <div>
              <label className="text-xs text-white/40">全文转写</label>
              <textarea
                rows={4}
                className="mt-1 w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm resize-none"
                value={payload.transcript ?? ''}
                onChange={e => updatePayload({ transcript: e.target.value })}
                placeholder="可在此编辑完整 ASR 文稿…"
              />
            </div>
          )}
        </section>

        <aside className="lg:col-span-5 p-4 overflow-y-auto">
          <div className="text-[11px] text-white/40 uppercase tracking-widest mb-3">
            片段 ({segments.length})
          </div>
          <ul className="space-y-3">
            {segments.map(s => (
              <li key={s.id} className="p-3 rounded-xl border border-[#1e1e2e] bg-[#12121a] space-y-2">
                <div className="flex justify-between text-[10px] font-mono text-white/35">
                  <span>
                    {(s.start_ms / 1000).toFixed(2)}s – {(s.end_ms / 1000).toFixed(2)}s
                  </span>
                  <button
                    type="button"
                    className="text-red-400/80"
                    onClick={() => updatePayload({ segments: segments.filter(x => x.id !== s.id) })}
                  >
                    删
                  </button>
                </div>
                {annType === 'speaker_diarize' && (
                  <select
                    value={s.speaker}
                    onChange={e => updateSeg(s.id, { speaker: e.target.value })}
                    className="w-full text-xs bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1"
                  >
                    {speakers.map(sp => (
                      <option key={sp} value={sp}>
                        {sp}
                      </option>
                    ))}
                  </select>
                )}
                <textarea
                  rows={2}
                  className="w-full text-xs bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-2 py-1.5 resize-none"
                  value={s.text}
                  onChange={e => updateSeg(s.id, { text: e.target.value })}
                  placeholder="转写文本"
                />
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </ModalityShell>
  )
}
