import { useCallback, useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { message } from 'antd'
import api, { projectApi } from '../services/api'
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
}

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  pending: { label: '待领取', color: '#f59e0b' },
  assigned: { label: '已分配', color: '#00d4ff' },
  annotating: { label: '标注中', color: '#00d4ff' },
  submitted: { label: '已提交', color: '#a78bfa' },
  approved: { label: '已通过', color: '#10b981' },
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

  const load = useCallback(async () => {
    if (!pid || Number.isNaN(pid)) return
    setLoading(true)
    try {
      const [projRes, tasksRes] = await Promise.all([
        projectApi.getById(pid),
        api.get(`/projects/${pid}/tasks`, { params: { page: 1, page_size: 200 } }),
      ])
      setProject(projRes.data)
      setItems(tasksRes.data.items ?? [])
      setTotal(tasksRes.data.total ?? 0)
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

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">{project?.name ?? '项目任务'}</h1>
          <p className="text-xs text-white/30 mt-1">
            共 {total} 条数据
            {project?.category === 'image_2d' && ' · 点击任务进入 2D 标注'}
          </p>
        </div>
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
      ) : project?.category === 'image_2d' ? (
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
                <th className="text-right px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(task => {
                const st = STATUS_LABEL[task.status] ?? { label: task.status, color: '#9ba0ad' }
                return (
                  <tr key={task.id} className="border-b border-[#1e1e2e]/50 hover:bg-white/[0.02]">
                    <td className="px-4 py-3 font-mono text-white/50">{task.id}</td>
                    <td className="px-4 py-3 text-white/70 truncate max-w-xs">
                      {task.filename ?? task.data_url ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span style={{ color: st.color }}>{st.label}</span>
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