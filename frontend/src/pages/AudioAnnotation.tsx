import { useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import ModalityShell from '../components/annotation/ModalityShell'
import AudioWaveform from '../components/annotation/AudioWaveform'
import ProjectExportMenu from '../components/dataset/ProjectExportMenu'
import { useModalityWorkspace } from '../hooks/useModalityWorkspace'
import { useAutoLabel } from '../hooks/useAutoLabel'
import { useWorkbenchNav } from '../hooks/useWorkbenchNav'
import { GuidelinesAckModal, useProjectGuidelines } from '../components/annotation/GuidelinesPanel'
import { getAnnotateBackHref } from '../utils/annotationRoutes'
import type { AudioSegment } from '../services/modalityAnnotation'

function segId() {
  return `seg_${Date.now().toString(36)}`
}

export default function AudioAnnotation() {
  const { taskId = '3002' } = useParams<{ taskId: string }>()
  const [searchParams] = useSearchParams()
  const projectIdParam = searchParams.get('projectId')
  const { ws, payload, updatePayload, loading, saving, dirty, lastSavedAt, useBackend, persist, submit, reload, lock, lockBlocked, peers, connected } =
    useModalityWorkspace(taskId, 'audio')
  const auto = useAutoLabel(taskId, useBackend, reload)
  const projectId = projectIdParam ?? ws?.project_id
  const guide = useProjectGuidelines(projectId)
  const nav = useWorkbenchNav(taskId, projectId)
  const audioRef = useRef<HTMLAudioElement>(null)
  const [currentMs, setCurrentMs] = useState(0)
  const [durationMs, setDurationMs] = useState(0)
  const [markStart, setMarkStart] = useState<number | null>(null)

  const url = ws?.content.audio_url ?? ''
  const segments = payload?.segments ?? []
  const speakers = payload?.speakers ?? ['说话人 A', '说话人 B']
  const annType = ws?.ann_type ?? 'asr'
  const backHref = getAnnotateBackHref({
    projectId: projectIdParam ?? ws?.project_id,
    category: ws?.category ?? 'audio',
  })

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
      emotion: '',
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
      dirty={dirty}
      lastSavedAt={lastSavedAt}
      onSave={() => persist(payload, false)}
      onSubmit={() => submit()}
      onAutoLabel={auto.run}
      autoLabeling={auto.busy}
      onNext={nav.claimNext}
      onSkip={nav.skip}
      navBusy={nav.busy}
      guidelinesMd={guide.state?.guidelines_md ?? ''}
      rejectFeedback={ws?.last_reject_feedback}
      rejectTargets={ws?.last_reject_targets}
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
        <section className="lg:col-span-7 p-4 border-r border-[#1e1e2e] flex flex-col gap-4 overflow-y-auto">
          <audio
            ref={audioRef}
            src={url}
            controls
            preload="metadata"
            className="w-full"
            onTimeUpdate={() => setCurrentMs((audioRef.current?.currentTime ?? 0) * 1000)}
            onLoadedMetadata={() => setDurationMs((audioRef.current?.duration ?? 0) * 1000)}
          />
          <AudioWaveform
            url={url}
            currentMs={currentMs}
            durationMs={durationMs}
            segments={segments}
            onSeek={ms => {
              setCurrentMs(ms)
              if (audioRef.current) audioRef.current.currentTime = ms / 1000
            }}
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
          {annType === 'emotion_audio' && (
            <div>
              <label className="text-xs text-white/40">整段情绪</label>
              <select
                className="mt-1 w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm"
                value={payload.emotion ?? ''}
                onChange={e => updatePayload({ emotion: e.target.value })}
              >
                <option value="">未选</option>
                {['neutral', 'happy', 'sad', 'angry', 'fear', 'surprise'].map(em => (
                  <option key={em} value={em}>
                    {em}
                  </option>
                ))}
              </select>
            </div>
          )}
          {annType === 'tts_label' && (
            <div>
              <label className="text-xs text-white/40">MOS 音质 (1–5)</label>
              <input
                type="number"
                min={1}
                max={5}
                step={0.1}
                className="mt-1 w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm"
                value={payload.mos ?? ''}
                onChange={e => updatePayload({ mos: Number(e.target.value) || null })}
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
                {(annType === 'speaker_diarize' || annType === 'asr') && (
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
                {(annType === 'emotion_audio' || annType === 'tts_label') && (
                  <select
                    value={s.emotion ?? ''}
                    onChange={e => updateSeg(s.id, { emotion: e.target.value })}
                    className="w-full text-xs bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1"
                  >
                    <option value="">情绪 / 风格</option>
                    {['neutral', 'happy', 'sad', 'angry', 'fear', 'surprise'].map(em => (
                      <option key={em} value={em}>
                        {em}
                      </option>
                    ))}
                  </select>
                )}
                {annType === 'tts_label' && (
                  <input
                    className="w-full text-xs bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1"
                    placeholder="问题（杂音/截断/发音）"
                    value={s.issues ?? ''}
                    onChange={e => updateSeg(s.id, { issues: e.target.value })}
                  />
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
      <GuidelinesAckModal
        open={Boolean(guide.state?.needs_ack)}
        markdown={guide.state?.guidelines_md || ''}
        onAck={() => void guide.ack()}
      />
    </ModalityShell>
  )
}
