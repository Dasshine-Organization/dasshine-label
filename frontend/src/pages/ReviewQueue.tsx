import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { message } from 'antd'
import { qualityApi } from '../services/api'
import { getAnnotatePath, resolveTaskMode } from '../utils/annotationRoutes'
import {
  useInvalidateReviewQueue,
  useReviewQueueQuery,
} from '../hooks/queries/useReviewQueue'

type ReviewDetail = {
  id: number
  project_id: number
  project_name: string
  category?: string
  status: string
  data_url?: string
  filename?: string
  width?: number
  height?: number
  assignee_name?: string
  annotations2d: Array<{
    id?: string
    type?: string
    label?: string
    color?: string
    points?: Array<{ x: number; y: number } | [number, number]>
    bbox?: number[]
  }>
  embodied_preview?: {
    instruction?: string
    success?: string
    segments?: Array<{ start_frame?: number; end_frame?: number; action_id?: string }>
    grasps?: unknown[]
    trajectory_points?: number
    preferences?: number
    streams?: Array<{ id?: string; label?: string; src: string }>
    joints_source?: string
    force_source?: string
    tactile_source?: string
    total_frames?: number
  } | null
  last_reject_feedback?: string
}

function boxStyle(ann: ReviewDetail['annotations2d'][0], imgW: number, imgH: number) {
  let x = 0
  let y = 0
  let w = 0
  let h = 0
  if (ann.bbox && ann.bbox.length >= 4) {
    ;[x, y, w, h] = ann.bbox
  } else if (ann.points && ann.points.length >= 2) {
    const toXY = (p: { x: number; y: number } | [number, number]) =>
      Array.isArray(p) ? { x: p[0], y: p[1] } : { x: p.x, y: p.y }
    const a = toXY(ann.points[0])
    const b = toXY(ann.points[1])
    x = Math.min(a.x, b.x)
    y = Math.min(a.y, b.y)
    w = Math.abs(b.x - a.x)
    h = Math.abs(b.y - a.y)
  }
  if (!imgW || !imgH) return null
  return {
    left: `${(x / imgW) * 100}%`,
    top: `${(y / imgH) * 100}%`,
    width: `${(w / imgW) * 100}%`,
    height: `${(h / imgH) * 100}%`,
    borderColor: ann.color || '#a78bfa',
  }
}

export default function ReviewQueue() {
  const [searchParams] = useSearchParams()
  const projectFilter = searchParams.get('projectId')
  const { data: items = [], isLoading: loading, isError, error, refetch } = useReviewQueueQuery(projectFilter)
  const invalidateQueue = useInvalidateReviewQueue()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [detail, setDetail] = useState<ReviewDetail | null>(null)
  const [feedback, setFeedback] = useState('')
  const [acting, setActing] = useState(false)
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 })

  useEffect(() => {
    if (isError) {
      const err = error as { response?: { data?: { detail?: string } } }
      message.error(err?.response?.data?.detail ?? '加载审核队列失败')
    }
  }, [isError, error])

  useEffect(() => {
    setSelectedId(prev => {
      if (prev && items.some(i => i.id === prev)) return prev
      return items[0]?.id ?? null
    })
  }, [items])

  const load = () => {
    void invalidateQueue(projectFilter)
    return refetch()
  }

  useEffect(() => {
    if (!selectedId) {
      setDetail(null)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const { data } = await qualityApi.getTaskDetail(selectedId)
        if (!cancelled) {
          setDetail(data)
          setFeedback('')
          setImgSize({
            w: Number(data.width) || 0,
            h: Number(data.height) || 0,
          })
        }
      } catch {
        if (!cancelled) {
          setDetail(null)
          message.error('加载审核详情失败')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [selectedId])

  const title = useMemo(
    () =>
      projectFilter ? `项目 #${projectFilter} 审核队列` : '审核工作台',
    [projectFilter],
  )

  async function decide(decision: 'approved' | 'rejected') {
    if (!selectedId) return
    if (decision === 'rejected' && !feedback.trim()) {
      message.warning('驳回请填写反馈意见')
      return
    }
    setActing(true)
    try {
      const { data } = await qualityApi.review({
        task_id: selectedId,
        decision,
        feedback: feedback.trim() || undefined,
      })
      message.success(data.message ?? (decision === 'approved' ? '已通过' : '已驳回'))
      setSelectedId(null)
      setDetail(null)
      await load()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '审核失败')
    } finally {
      setActing(false)
    }
  }

  function openAnnotate() {
    if (!detail) return
    const mode = resolveTaskMode({
      taskId: detail.id,
      category: detail.category,
    })
    const base = getAnnotatePath(detail.id, mode)
    const sep = base.includes('?') ? '&' : '?'
    window.open(`${base}${sep}projectId=${detail.project_id}`, '_blank')
  }

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 className="text-xl font-semibold">{title}</h1>
          <p className="text-xs text-white/30 mt-1">
            审核已提交任务 · 通过后可导出 COCO · 驳回回流标注中
          </p>
        </div>
        <div className="flex items-center gap-2">
          {projectFilter && (
            <Link
              to={`/projects/${projectFilter}/tasks`}
              className="text-xs px-3 py-1.5 rounded-lg border border-[#1e1e2e] text-white/40 hover:text-white/70"
            >
              项目任务
            </Link>
          )}
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="text-xs px-3 py-1.5 rounded-lg border border-[#1e1e2e] text-white/40 hover:text-white/70 disabled:opacity-40"
          >
            {loading ? '刷新中…' : '刷新'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 min-h-[60vh]">
        <aside className="lg:col-span-4 bg-[#12121a] border border-[#1e1e2e] rounded-xl overflow-hidden flex flex-col">
          <div className="px-3 py-2 border-b border-[#1e1e2e] text-[11px] text-white/35 uppercase tracking-wider">
            待审 {items.length}
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading && items.length === 0 ? (
              <div className="p-6 text-xs text-white/30 text-center">加载中…</div>
            ) : items.length === 0 ? (
              <div className="p-8 text-center text-xs text-white/30">暂无待审核任务</div>
            ) : (
              items.map(item => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedId(item.id)}
                  className={`w-full text-left px-3 py-3 border-b border-[#1e1e2e]/60 transition-colors
                    ${selectedId === item.id ? 'bg-[#a78bfa]/10' : 'hover:bg-white/[0.02]'}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs text-white/60">#{item.id}</span>
                    <span className="text-[10px] text-[#a78bfa]">{item.status}</span>
                  </div>
                  <div className="text-xs text-white/70 truncate mt-1">{item.project_name}</div>
                  <div className="text-[10px] text-white/30 mt-0.5 truncate">
                    {item.assignee_name ?? '未分配'} · {item.box_count ?? 0} 框
                  </div>
                </button>
              ))
            )}
          </div>
        </aside>

        <section className="lg:col-span-8 bg-[#12121a] border border-[#1e1e2e] rounded-xl overflow-hidden flex flex-col">
          {!detail ? (
            <div className="flex-1 flex items-center justify-center text-xs text-white/30">
              选择左侧任务开始审核
            </div>
          ) : (
            <>
              <div className="px-4 py-3 border-b border-[#1e1e2e] flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="text-sm text-white/80">
                    #{detail.id} · {detail.project_name}
                  </div>
                  <div className="text-[11px] text-white/35 mt-0.5">
                    {detail.assignee_name ?? '—'} · {detail.filename ?? detail.data_url ?? ''}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={openAnnotate}
                  className="text-xs text-[#00d4ff] hover:underline"
                >
                  在工作台查看
                </button>
              </div>

              <div className="flex-1 relative bg-[#0a0a0f] min-h-[280px] flex items-center justify-center overflow-hidden">
                {detail.embodied_preview ? (
                  <div className="w-full h-full p-4 overflow-y-auto space-y-3">
                    <div className="text-xs text-white/70 space-y-1">
                      <div>
                        <span className="text-white/35">指令：</span>
                        {detail.embodied_preview.instruction || '（空）'}
                      </div>
                      <div>
                        <span className="text-white/35">结果：</span>
                        {detail.embodied_preview.success || 'unknown'}
                        {detail.embodied_preview.joints_source && (
                          <span className="text-white/30 ml-2">
                            · joints={detail.embodied_preview.joints_source}
                          </span>
                        )}
                      </div>
                      <div className="text-white/35">
                        区间 {(detail.embodied_preview.segments || []).length} · 抓取{' '}
                        {(detail.embodied_preview.grasps || []).length} · 轨迹点{' '}
                        {detail.embodied_preview.trajectory_points ?? 0} · 偏好{' '}
                        {detail.embodied_preview.preferences ?? 0}
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {(detail.embodied_preview.streams || []).map((s, i) => (
                        <div
                          key={s.id ?? i}
                          className="rounded-lg border border-[#1e1e2e] overflow-hidden bg-black aspect-video relative"
                        >
                          <video
                            src={s.src}
                            muted
                            playsInline
                            preload="metadata"
                            className="w-full h-full object-cover"
                          />
                          <div className="absolute bottom-1 left-1 text-[10px] text-white/70 bg-black/50 px-1 rounded">
                            {s.label || s.id || `cam${i}`}
                          </div>
                        </div>
                      ))}
                    </div>
                    {(detail.embodied_preview.segments || []).length > 0 && (
                      <div className="text-[11px] text-white/45 font-mono space-y-0.5">
                        {(detail.embodied_preview.segments || []).slice(0, 8).map((s, i) => (
                          <div key={i}>
                            [{s.start_frame}–{s.end_frame}] {s.action_id}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : detail.data_url ? (
                  <div className="relative max-w-full max-h-[52vh]">
                    <img
                      src={detail.data_url}
                      alt=""
                      className="max-h-[52vh] max-w-full object-contain"
                      onLoad={e => {
                        const img = e.currentTarget
                        if (!imgSize.w || !imgSize.h) {
                          setImgSize({ w: img.naturalWidth, h: img.naturalHeight })
                        }
                      }}
                    />
                    {imgSize.w > 0 &&
                      detail.annotations2d.map((ann, i) => {
                        const st = boxStyle(ann, imgSize.w, imgSize.h)
                        if (!st) return null
                        return (
                          <div
                            key={ann.id ?? i}
                            className="absolute border-2 pointer-events-none"
                            style={st}
                            title={ann.label}
                          />
                        )
                      })}
                  </div>
                ) : (
                  <div className="text-xs text-white/30 p-8 text-center">
                    无预览图（非图像任务可在工作台查看标注）
                    <div className="mt-2 font-mono text-white/40">
                      {detail.annotations2d.length} 条标注对象
                    </div>
                  </div>
                )}
              </div>

              <div className="p-4 border-t border-[#1e1e2e] space-y-3">
                {detail.last_reject_feedback && (
                  <div className="text-[11px] text-[#f59e0b]/90 bg-[#f59e0b]/10 border border-[#f59e0b]/20 rounded-lg px-3 py-2">
                    上次驳回：{detail.last_reject_feedback}
                  </div>
                )}
                <textarea
                  rows={2}
                  value={feedback}
                  onChange={e => setFeedback(e.target.value)}
                  placeholder="审核意见（驳回时必填）"
                  className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white/80 resize-none"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={acting}
                    onClick={() => decide('rejected')}
                    className="flex-1 py-2.5 rounded-xl text-sm border border-[#ef4444]/35 text-[#ef4444] hover:bg-[#ef4444]/10 disabled:opacity-40"
                  >
                    驳回回流
                  </button>
                  <button
                    type="button"
                    disabled={acting}
                    onClick={() => decide('approved')}
                    className="flex-1 py-2.5 rounded-xl text-sm font-medium bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/35 hover:bg-[#10b981]/30 disabled:opacity-40"
                  >
                    通过
                  </button>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
