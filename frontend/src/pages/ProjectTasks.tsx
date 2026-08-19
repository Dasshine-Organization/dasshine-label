import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { message } from 'antd'
import api, { autoLabelApi, projectApi } from '../services/api'
import ProjectExportMenu from '../components/dataset/ProjectExportMenu'
import ProjectMembersPanel from '../components/project/ProjectMembersPanel'
import ProjectQualityPanel from '../components/project/ProjectQualityPanel'
import { getAnnotatePath, getCategoryProjectsPath, resolveTaskMode } from '../utils/annotationRoutes'
import type { ProjectSummary } from '../types/project'
import { onProjectTaskStatus } from '../utils/projectTaskStatus'

type ProjectTaskItem = {
  id: number
  project_id: number
  filename?: string
  data_url?: string
  status: string
  priority: number
  assignee_name?: string
  category?: string
  ann_type?: string
  cross_validate_count?: number
  submit_progress?: { done?: number; need?: number }
}

type DispatchLog = {
  batch_id?: string
  strategy?: string
  total?: number
  assigned?: number
  failed?: number
  dispatched_at?: string
}

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  pending: { label: '待领取', color: '#f59e0b' },
  assigned: { label: '已分配', color: '#00d4ff' },
  annotating: { label: '标注中', color: '#00d4ff' },
  submitted: { label: '已提交', color: '#a78bfa' },
  reviewing: { label: '审核中', color: '#a78bfa' },
  approved: { label: '已通过', color: '#10b981' },
  rejected: { label: '已驳回', color: '#ef4444' },
}

export default function ProjectTasks() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const pid = Number(projectId)

  const [project, setProject] = useState<ProjectSummary | null>(null)
  const [items, setItems] = useState<ProjectTaskItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [dispatchLogs, setDispatchLogs] = useState<DispatchLog[]>([])
  const [stats, setStats] = useState<{
    submitted?: number
    approved?: number
    pending?: number
    dispatch_count?: number
  } | null>(null)
  const [autoBusy, setAutoBusy] = useState(false)

  const load = useCallback(async () => {
    if (!pid || Number.isNaN(pid)) return
    setLoading(true)
    try {
      const [projRes, tasksRes, logsRes, statsRes] = await Promise.all([
        projectApi.getById(pid),
        api.get(`/projects/${pid}/tasks`, { params: { page: 1, page_size: 200 } }),
        projectApi.getDispatchLogs(pid, 5).catch(() => ({ data: { logs: [] } })),
        projectApi.getStats(pid).catch(() => ({ data: null })),
      ])
      setProject(projRes.data)
      setItems(tasksRes.data.items ?? [])
      setTotal(tasksRes.data.total ?? 0)
      setDispatchLogs((logsRes.data?.logs as DispatchLog[]) ?? [])
      setStats(statsRes.data)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '加载任务失败')
    } finally {
      setLoading(false)
    }
  }, [pid])

  useEffect(() => {
    load()
  }, [load, location.key])

  useEffect(() => {
    if (!pid || Number.isNaN(pid)) return
    return onProjectTaskStatus(detail => {
      if (detail.projectId !== pid) return
      setItems(prev =>
        prev.map(t => (t.id === detail.taskId ? { ...t, status: detail.status } : t)),
      )
    })
  }, [pid])

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === 'visible') load()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [load])

  function openTask(task: ProjectTaskItem) {
    const mode = resolveTaskMode({
      taskId: task.id,
      category: task.category ?? project?.category,
      ann_type: task.ann_type,
    })
    const base = getAnnotatePath(task.id, mode)
    const sep = base.includes('?') ? '&' : '?'
    navigate(`${base}${sep}projectId=${pid}`)
  }

  async function runBatchAutoLabel() {
    setAutoBusy(true)
    try {
      const { data } = await autoLabelApi.batch(pid, 50)
      if (data.queued) {
        message.success('已排队批量预标注，稍后刷新查看进度')
      } else {
        message.success(`预标注完成 ${data.processed} 条（失败 ${data.failed}）`)
      }
      await load()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '批量预标注失败')
    } finally {
      setAutoBusy(false)
    }
  }

  const submittedCount =
    stats?.submitted ?? items.filter(t => t.status === 'submitted' || t.status === 'reviewing').length
  const canAutoLabel =
    project?.category === 'nlp' ||
    project?.category === 'audio' ||
    project?.category === 'ocr' ||
    (project?.category === 'multimodal' && project?.ann_type !== 'rlhf') ||
    (project?.category === 'video' && project?.ann_type === 'video_caption')

  return (
    <div className="p-8 max-w-6xl">
      <div className="flex items-center gap-3 mb-6">
        <Link
          to={getCategoryProjectsPath(project?.category)}
          className="text-xs text-white/30 hover:text-white/60 transition-colors"
        >
          ← 项目列表
        </Link>
      </div>

      <div className="flex items-start justify-between mb-6 gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">{project?.name ?? '项目任务'}</h1>
          <p className="text-xs text-white/30 mt-1">
            共 {total} 条数据
            {project?.category === 'image_2d' && ' · 点击任务进入 2D 标注'}
            {stats && (
              <span>
                {' '}
                · 待审 {submittedCount} · 已通过 {stats.approved ?? 0} · 分发{' '}
                {stats.dispatch_count ?? 0} 次
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <ProjectQualityPanel projectId={pid} />
          <ProjectMembersPanel projectId={pid} />
          <Link
            to={`/review?projectId=${pid}`}
            className="px-3 py-1.5 rounded-lg text-xs border border-[#a78bfa]/30 text-[#a78bfa] hover:bg-[#a78bfa]/10 transition-all"
          >
            审核队列{submittedCount ? ` (${submittedCount})` : ''}
          </Link>
          <ProjectExportMenu projectId={pid} projectName={project?.name} />
          {canAutoLabel && (
            <button
              type="button"
              onClick={() => void runBatchAutoLabel()}
              disabled={autoBusy || loading}
              className="px-3 py-1.5 rounded-lg text-xs border border-[#00d4ff]/30 text-[#00d4ff]
                hover:bg-[#00d4ff]/10 transition-all disabled:opacity-40"
            >
              {autoBusy ? '预标注中…' : 'AI 批量预标注'}
            </button>
          )}
          <button
            type="button"
            onClick={load}
            disabled={loading}
            className="px-3 py-1.5 rounded-lg text-xs border border-[#1e1e2e] text-white/40
              hover:text-white/70 hover:border-white/20 transition-all disabled:opacity-40"
          >
            {loading ? '刷新中…' : '刷新'}
          </button>
        </div>
      </div>

      {dispatchLogs.length > 0 && (
        <div className="mb-5 rounded-xl border border-[#1e1e2e] bg-[#12121a] px-4 py-3">
          <div className="text-[10px] text-white/35 uppercase tracking-wider mb-2">最近分发</div>
          <div className="space-y-1.5">
            {dispatchLogs.map((log, i) => (
              <div key={log.batch_id ?? i} className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-white/50 font-mono">
                <span>{log.dispatched_at?.replace('T', ' ').slice(0, 19) ?? '—'}</span>
                <span>{log.strategy ?? '—'}</span>
                <span className="text-[#10b981]">成功 {log.assigned ?? 0}</span>
                <span className="text-[#ef4444]/80">失败 {log.failed ?? 0}</span>
                <span className="text-white/25 truncate max-w-[140px]">{log.batch_id?.slice(0, 8)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="aspect-square bg-[#12121a] border border-[#1e1e2e] rounded-xl animate-pulse" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-24 border border-dashed border-[#1e1e2e] rounded-2xl">
          <p className="text-sm text-white/30 mb-2">暂无任务数据</p>
          <p className="text-xs text-white/20">请先在项目卡片中「导入数据」</p>
          <Link
            to={getCategoryProjectsPath(project?.category)}
            className="inline-block mt-4 text-xs text-[#00d4ff] hover:underline"
          >
            返回{project?.category ? '该类' : ''}项目管理
          </Link>
        </div>
      ) : project?.category === 'image_2d' || project?.category === 'ocr' ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
          {items.map(task => {
            const st = STATUS_LABEL[task.status] ?? { label: task.status, color: '#9ba0ad' }
            return (
              <button
                key={task.id}
                type="button"
                onClick={() => openTask(task)}
                className="group text-left bg-[#12121a] border border-[#1e1e2e] rounded-xl overflow-hidden
                  hover:border-[#00d4ff]/30 transition-all active:scale-[0.99]"
              >
                <div className="aspect-square bg-[#0a0a0f] relative overflow-hidden">
                  {task.data_url ? (
                    <img
                      src={task.data_url}
                      alt={task.filename ?? `task-${task.id}`}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      loading="lazy"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-white/15 text-xs">
                      无预览
                    </div>
                  )}
                  <span
                    className="absolute top-2 right-2 text-[10px] px-1.5 py-0.5 rounded-full"
                    style={{ background: `${st.color}22`, color: st.color }}
                  >
                    {st.label}
                  </span>
                </div>
                <div className="p-2.5">
                  <div className="text-[11px] text-white/50 truncate font-mono">
                    #{task.id} {task.filename ?? ''}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      ) : (
        <div className="bg-[#12121a] border border-[#1e1e2e] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e1e2e] text-white/30 text-xs">
                <th className="text-left px-4 py-3">ID</th>
                <th className="text-left px-4 py-3">文件</th>
                <th className="text-left px-4 py-3">状态</th>
                <th className="text-left px-4 py-3">共标</th>
                <th className="text-right px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(task => {
                const st = STATUS_LABEL[task.status] ?? { label: task.status, color: '#9ba0ad' }
                const need = task.submit_progress?.need ?? task.cross_validate_count ?? 1
                const done = task.submit_progress?.done ?? 0
                return (
                  <tr key={task.id} className="border-b border-[#1e1e2e]/50 hover:bg-white/[0.02]">
                    <td className="px-4 py-3 font-mono text-white/50">{task.id}</td>
                    <td className="px-4 py-3 text-white/70 truncate max-w-xs">
                      {task.filename ?? task.data_url ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span style={{ color: st.color }}>{st.label}</span>
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-white/40">
                      {need > 1 ? `${done}/${need}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => openTask(task)}
                        className="text-xs text-[#00d4ff] hover:underline"
                      >
                        标注
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
