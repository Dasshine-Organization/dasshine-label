import { useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import ModalityShell from '../components/annotation/ModalityShell'
import ProjectExportMenu from '../components/dataset/ProjectExportMenu'
import { useModalityWorkspace } from '../hooks/useModalityWorkspace'
import { getAnnotateBackHref } from '../utils/annotationRoutes'
import type { TextSpan } from '../services/modalityAnnotation'

function uid() {
  return `sp_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
}

export default function TextAnnotation() {
  const { taskId = '3001' } = useParams<{ taskId: string }>()
  const [searchParams] = useSearchParams()
  const projectIdParam = searchParams.get('projectId')
  const { ws, payload, updatePayload, loading, saving, dirty, lastSavedAt, useBackend, persist, submit } =
    useModalityWorkspace(taskId, 'text', 'ner')

  const [activeLabel, setActiveLabel] = useState('PER')
  const text = ws?.content.text ?? ''
  const annType = ws?.ann_type ?? 'ner'
  const labels = ws?.label_classes ?? []

  const spans = payload?.spans ?? []
  const backHref = getAnnotateBackHref({
    projectId: projectIdParam ?? ws?.project_id,
    category: ws?.category ?? 'nlp',
  })

  const highlighted = useMemo(() => {
    if (!text) return null
    const sorted = [...spans].sort((a, b) => a.start - b.start)
    const parts: { t: string; span?: TextSpan }[] = []
    let cursor = 0
    for (const s of sorted) {
      if (s.start > cursor) parts.push({ t: text.slice(cursor, s.start) })
      parts.push({ t: text.slice(s.start, s.end), span: s })
      cursor = s.end
    }
    if (cursor < text.length) parts.push({ t: text.slice(cursor) })
    return parts
  }, [text, spans])

  function addSpanFromSelection() {
    const sel = window.getSelection()
    if (!sel || sel.isCollapsed || !text) return
    const raw = sel.toString()
    if (!raw.trim()) return
    const start = text.indexOf(raw, 0)
    if (start < 0) return
    const end = start + raw.length
    const overlap = spans.some(s => !(end <= s.start || start >= s.end))
    if (overlap) return
    const labelDef = labels.find(l => l.id === activeLabel)
    updatePayload({
      spans: [
        ...spans,
        {
          id: uid(),
          start,
          end,
          label: activeLabel,
          text: raw,
          color: labelDef?.color,
        } as TextSpan & { color?: string },
      ],
    })
    sel.removeAllRanges()
  }

  function removeSpan(id: string) {
    updatePayload({ spans: spans.filter(s => s.id !== id) })
  }

  if (loading || !payload) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0a0a0f] text-white/40 text-sm">
        加载语料工作区…
      </div>
    )
  }

  return (
    <ModalityShell
      title={`文本标注 · ${ws?.project_name ?? taskId}`}
      subtitle={`${annType} · task #${taskId}`}
      accent="#ec4899"
      useBackend={useBackend}
      saving={saving}
      dirty={dirty}
      lastSavedAt={lastSavedAt}
      onSave={() => persist(payload, false)}
      onSubmit={() => submit()}
      backHref={backHref}
      backLabel="← 返回"
      headerExtra={
        <ProjectExportMenu
          projectId={projectIdParam ?? ws?.project_id}
          projectName={ws?.project_name}
          compact
        />
      }
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 h-full">
        <section className="lg:col-span-8 p-4 md:p-6 overflow-y-auto border-r border-[#1e1e2e]">
          <div className="text-[11px] text-white/40 uppercase tracking-widest mb-3">原文</div>
          <div
            className="rounded-xl border border-[#1e1e2e] bg-[#12121a] p-4 text-sm leading-relaxed text-white/85 select-text"
            onMouseUp={annType === 'ner' || annType === 're' ? addSpanFromSelection : undefined}
          >
            {highlighted?.map((p, i) =>
              p.span ? (
                <mark
                  key={i}
                  className="rounded px-0.5 mx-0.5"
                  style={{
                    background: `${labels.find(l => l.id === p.span!.label)?.color ?? '#ec4899'}44`,
                    color: labels.find(l => l.id === p.span!.label)?.color ?? '#f9a8d4',
                  }}
                >
                  {p.t}
                </mark>
              ) : (
                <span key={i}>{p.t}</span>
              ),
            )}
          </div>
          {(annType === 'ner' || annType === 're') && (
            <p className="text-[10px] text-white/30 mt-2">
              选中文字后自动打上当前标签「{activeLabel}」。共 {spans.length} 个实体。
            </p>
          )}

          {annType === 'sentiment' && (
            <div className="mt-6 space-y-2">
              <label className="text-xs text-white/40">情感极性</label>
              <div className="flex gap-2 flex-wrap">
                {['positive', 'neutral', 'negative'].map(v => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => updatePayload({ sentiment: v })}
                    className={`text-xs px-3 py-1.5 rounded-lg border ${
                      payload.sentiment === v
                        ? 'border-[#ec4899] bg-[#ec4899]/20 text-[#f9a8d4]'
                        : 'border-[#1e1e2e] text-white/50'
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
          )}

          {annType === 'text_classify' && (
            <div className="mt-6">
              <label className="text-xs text-white/40">分类标签（逗号分隔）</label>
              <input
                className="mt-1 w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm"
                value={(payload.classification_labels ?? []).join(', ')}
                onChange={e =>
                  updatePayload({
                    classification_labels: e.target.value.split(/[,，]/).map(s => s.trim()).filter(Boolean),
                  })
                }
              />
            </div>
          )}

          {(annType === 'summarization' || annType === 'translation') && (
            <div className="mt-6">
              <label className="text-xs text-white/40">
                {annType === 'summarization' ? '摘要' : '译文'}
              </label>
              <textarea
                rows={5}
                className="mt-1 w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm resize-none"
                value={annType === 'summarization' ? payload.summary ?? '' : payload.translation ?? ''}
                onChange={e =>
                  updatePayload(
                    annType === 'summarization'
                      ? { summary: e.target.value }
                      : { translation: e.target.value },
                  )
                }
              />
            </div>
          )}

          {annType === 'qa_pair' && (
            <div className="mt-6 space-y-3">
              {(payload.qa_pairs ?? [{ question: '', answer: '' }]).map((qa, idx) => (
                <div key={idx} className="space-y-2 p-3 rounded-lg border border-[#1e1e2e] bg-[#0a0a0f]">
                  <input
                    placeholder="问题"
                    className="w-full bg-transparent border-b border-[#1e1e2e] pb-2 text-sm"
                    value={qa.question}
                    onChange={e => {
                      const next = [...(payload.qa_pairs ?? [])]
                      next[idx] = { ...next[idx], question: e.target.value }
                      updatePayload({ qa_pairs: next })
                    }}
                  />
                  <textarea
                    placeholder="答案"
                    rows={2}
                    className="w-full bg-transparent text-sm resize-none"
                    value={qa.answer}
                    onChange={e => {
                      const next = [...(payload.qa_pairs ?? [])]
                      next[idx] = { ...next[idx], answer: e.target.value }
                      updatePayload({ qa_pairs: next })
                    }}
                  />
                </div>
              ))}
              <button
                type="button"
                className="text-xs text-[#ec4899]"
                onClick={() =>
                  updatePayload({
                    qa_pairs: [...(payload.qa_pairs ?? []), { question: '', answer: '' }],
                  })
                }
              >
                + 添加问答对
              </button>
            </div>
          )}
        </section>

        <aside className="lg:col-span-4 p-4 overflow-y-auto space-y-4">
          {(annType === 'ner' || annType === 're') && (
            <>
              <div className="text-[11px] text-white/40 uppercase tracking-widest">实体类型</div>
              <div className="flex flex-wrap gap-1.5">
                {labels.map(l => (
                  <button
                    key={l.id}
                    type="button"
                    onClick={() => setActiveLabel(l.id)}
                    className={`text-xs px-2 py-1 rounded border ${
                      activeLabel === l.id ? 'ring-1 ring-offset-1 ring-offset-[#0a0a0f]' : ''
                    }`}
                    style={{
                      borderColor: `${l.color}55`,
                      background: activeLabel === l.id ? `${l.color}22` : 'transparent',
                      color: l.color,
                    }}
                  >
                    {l.name}
                  </button>
                ))}
              </div>
              <div className="text-[11px] text-white/40 uppercase tracking-widest">已标实体</div>
              <ul className="space-y-2 max-h-[50vh] overflow-y-auto">
                {spans.map(s => (
                  <li
                    key={s.id}
                    className="flex items-start justify-between gap-2 text-xs p-2 rounded-lg bg-[#12121a] border border-[#1e1e2e]"
                  >
                    <div>
                      <span className="font-mono text-[#ec4899]">{s.label}</span>
                      <div className="text-white/70 mt-0.5">{s.text}</div>
                      <div className="text-white/25 font-mono text-[10px]">
                        [{s.start}, {s.end})
                      </div>
                    </div>
                    <button type="button" className="text-red-400/80" onClick={() => removeSpan(s.id)}>
                      删
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </aside>
      </div>
    </ModalityShell>
  )
}
