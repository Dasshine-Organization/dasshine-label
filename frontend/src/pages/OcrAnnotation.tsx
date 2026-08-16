import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { message } from 'antd'
import ProjectExportMenu from '../components/dataset/ProjectExportMenu'
import TaskLockBanner from '../components/TaskLockBanner'
import { useModalityWorkspace } from '../hooks/useModalityWorkspace'
import { getAnnotateBackHref } from '../utils/annotationRoutes'

type OcrSpan = {
  id: string
  text: string
  label: string
  bbox: [number, number, number, number] // xywh in natural image pixels
}

function asOcrSpans(raw: unknown): OcrSpan[] {
  if (!Array.isArray(raw)) return []
  return raw
    .filter((s): s is Record<string, unknown> => !!s && typeof s === 'object')
    .map((s, i) => {
      const bbox = Array.isArray(s.bbox) && s.bbox.length >= 4
        ? ([Number(s.bbox[0]), Number(s.bbox[1]), Number(s.bbox[2]), Number(s.bbox[3])] as [
            number,
            number,
            number,
            number,
          ])
        : ([0, 0, 0, 0] as [number, number, number, number])
      return {
        id: String(s.id || `ocr_${i}`),
        text: String(s.text || s.label || ''),
        label: String(s.label || 'text'),
        bbox,
      }
    })
}

export default function OcrAnnotation() {
  const { taskId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const projectIdParam = searchParams.get('projectId')
  const {
    ws,
    payload,
    setPayload,
    loading,
    saving,
    lastSavedAt,
    useBackend,
    persist,
    submit,
    lock,
    lockBlocked,
  } = useModalityWorkspace(taskId, 'ocr', 'ocr_text')

  const imgRef = useRef<HTMLImageElement>(null)
  const [natural, setNatural] = useState({ w: 1, h: 1 })
  const [drawing, setDrawing] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(
    null,
  )
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const spans = asOcrSpans(payload?.spans)
  const imageUrl = ws?.content?.image_url || ''

  useEffect(() => {
    if (!payload || payload.modality === 'ocr') return
    setPayload({ ...payload, modality: 'ocr', spans: payload.spans || [] })
  }, [payload, setPayload])

  const updateSpans = useCallback(
    (next: OcrSpan[]) => {
      if (!payload) return
      setPayload({ ...payload, modality: 'ocr', spans: next as never })
    },
    [payload, setPayload],
  )

  const toNatural = (clientX: number, clientY: number) => {
    const img = imgRef.current
    if (!img) return { x: 0, y: 0 }
    const rect = img.getBoundingClientRect()
    const sx = natural.w / Math.max(1, rect.width)
    const sy = natural.h / Math.max(1, rect.height)
    return {
      x: Math.max(0, Math.min(natural.w, (clientX - rect.left) * sx)),
      y: Math.max(0, Math.min(natural.h, (clientY - rect.top) * sy)),
    }
  }

  const onPointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return
    const p = toNatural(e.clientX, e.clientY)
    setDrawing({ x0: p.x, y0: p.y, x1: p.x, y1: p.y })
    ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
  }

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drawing) return
    const p = toNatural(e.clientX, e.clientY)
    setDrawing({ ...drawing, x1: p.x, y1: p.y })
  }

  const onPointerUp = () => {
    if (!drawing) return
    const x = Math.min(drawing.x0, drawing.x1)
    const y = Math.min(drawing.y0, drawing.y1)
    const w = Math.abs(drawing.x1 - drawing.x0)
    const h = Math.abs(drawing.y1 - drawing.y0)
    setDrawing(null)
    if (w < 4 || h < 4) return
    const id = `ocr_${Date.now().toString(36)}`
    const next: OcrSpan = { id, text: '', label: 'text', bbox: [x, y, w, h] }
    updateSpans([...spans, next])
    setSelectedId(id)
  }

  const displayScale = () => {
    const img = imgRef.current
    if (!img) return { sx: 1, sy: 1 }
    const rect = img.getBoundingClientRect()
    return { sx: rect.width / Math.max(1, natural.w), sy: rect.height / Math.max(1, natural.h) }
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await persist(true)
      await submit()
      message.success('OCR 标注已提交')
    } catch {
      message.error('提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading || !ws || !payload) {
    return <div className="min-h-screen bg-[#0a0a0f] text-white/40 p-8">加载 OCR 工作台…</div>
  }

  const { sx, sy } = displayScale()
  const selected = spans.find(s => s.id === selectedId)

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white flex flex-col">
      <TaskLockBanner lock={lock} blocked={lockBlocked} />
      <header className="flex items-center gap-3 px-4 py-3 border-b border-[#1e1e2e] bg-[#12121a]">
        <button
          type="button"
          onClick={() => navigate(getAnnotateBackHref(searchParams))}
          className="text-xs text-white/50 hover:text-white"
        >
          ← 返回
        </button>
        <div className="min-w-0">
          <div className="text-sm font-medium truncate">{ws.project_name}</div>
          <div className="text-[10px] text-white/35 font-mono">OCR · task {ws.task_id}</div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[10px] text-white/30">
            {saving ? '保存中…' : lastSavedAt ? `已存 ${new Date(lastSavedAt).toLocaleTimeString()}` : ''}
          </span>
          <ProjectExportMenu projectId={projectIdParam || String(ws.project_id)} projectName={ws.project_name} compact />
          <button
            type="button"
            onClick={() => void persist(true)}
            className="text-xs px-3 py-1.5 rounded-lg border border-[#1e1e2e] text-white/60"
          >
            保存草稿
          </button>
          <button
            type="button"
            disabled={submitting || !useBackend}
            onClick={() => void handleSubmit()}
            className="text-xs px-3 py-1.5 rounded-lg bg-[#06b6d4]/20 text-[#06b6d4] border border-[#06b6d4]/35 disabled:opacity-40"
          >
            {submitting ? '提交中…' : '提交审核'}
          </button>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-1 xl:grid-cols-12 gap-4 p-4">
        <section className="xl:col-span-8 min-h-[360px] rounded-xl border border-[#1e1e2e] bg-[#12121a] overflow-hidden relative flex items-center justify-center">
          {imageUrl ? (
            <div className="relative max-w-full max-h-[70vh]">
              <img
                ref={imgRef}
                src={imageUrl}
                alt=""
                className="max-h-[70vh] max-w-full object-contain select-none"
                draggable={false}
                onLoad={e => {
                  const el = e.currentTarget
                  setNatural({ w: el.naturalWidth || 1, h: el.naturalHeight || 1 })
                }}
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
              />
              {spans.map(s => {
                const [x, y, w, h] = s.bbox
                return (
                  <div
                    key={s.id}
                    className={`absolute border-2 pointer-events-none ${
                      s.id === selectedId ? 'border-[#f97316]' : 'border-[#06b6d4]'
                    }`}
                    style={{
                      left: x * sx,
                      top: y * sy,
                      width: w * sx,
                      height: h * sy,
                    }}
                    title={s.text || s.label}
                  />
                )
              })}
              {drawing && (
                <div
                  className="absolute border border-dashed border-white/50 pointer-events-none"
                  style={{
                    left: Math.min(drawing.x0, drawing.x1) * sx,
                    top: Math.min(drawing.y0, drawing.y1) * sy,
                    width: Math.abs(drawing.x1 - drawing.x0) * sx,
                    height: Math.abs(drawing.y1 - drawing.y0) * sy,
                  }}
                />
              )}
            </div>
          ) : (
            <div className="text-sm text-white/35 p-8 text-center space-y-2">
              <p>当前任务没有图像 URL。</p>
              <p className="text-xs">请用「导入」上传图片，或在任务 data_url 中配置图片地址。</p>
              <Link to={`/projects/${ws.project_id}/tasks`} className="text-[#00d4ff] text-xs hover:underline">
                返回任务列表
              </Link>
            </div>
          )}
        </section>

        <section className="xl:col-span-4 space-y-3">
          <div className="rounded-xl border border-[#1e1e2e] bg-[#12121a] p-4 space-y-2">
            <div className="text-[11px] text-white/40 uppercase tracking-widest">文字框 {spans.length}</div>
            <p className="text-[10px] text-white/30">在图像上拖拽绘制框，再填写识别文字。导出对齐 coco_text / paddleocr。</p>
            <div className="max-h-[40vh] overflow-y-auto space-y-2">
              {spans.map(s => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSelectedId(s.id)}
                  className={`w-full text-left rounded-lg border px-2 py-2 text-xs ${
                    selectedId === s.id ? 'border-[#f97316]/50 bg-[#f97316]/10' : 'border-[#1e1e2e]'
                  }`}
                >
                  <div className="font-mono text-white/35 text-[10px]">
                    [{s.bbox.map(n => Math.round(n)).join(',')}]
                  </div>
                  <div className="truncate text-white/80">{s.text || '（未填文字）'}</div>
                </button>
              ))}
            </div>
          </div>

          {selected && (
            <div className="rounded-xl border border-[#1e1e2e] bg-[#12121a] p-4 space-y-2">
              <div className="text-[11px] text-white/40">编辑选中框</div>
              <label className="block text-[11px] text-white/40">识别文字</label>
              <textarea
                value={selected.text}
                rows={3}
                onChange={e =>
                  updateSpans(spans.map(s => (s.id === selected.id ? { ...s, text: e.target.value } : s)))
                }
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-2 py-2 text-sm"
              />
              <label className="block text-[11px] text-white/40">标签</label>
              <select
                value={selected.label}
                onChange={e =>
                  updateSpans(spans.map(s => (s.id === selected.id ? { ...s, label: e.target.value } : s)))
                }
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-2 py-2 text-sm"
              >
                {(ws.label_classes || [{ id: 'text', name: '文字' }]).map(c => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="text-xs text-red-400"
                onClick={() => {
                  updateSpans(spans.filter(s => s.id !== selected.id))
                  setSelectedId(null)
                }}
              >
                删除此框
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
