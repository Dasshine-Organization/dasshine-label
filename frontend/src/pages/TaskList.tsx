import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { taskApi } from '../services/api'
import { DEMO_TASK_ROUTES, getAnnotatePath, resolveTaskMode } from '../utils/annotationRoutes'
import useAuthStore from '../store/authStore'

type Status = 'all' | 'pending' | 'in_progress' | 'submitted' | 'approved'

type TaskRow = {
  id: number
  project: string
  type: string
  category?: string
  ann_type?: string
  status: string
  priority: number
  reward: number
}

const STATUS_MAP: Record<string, { label: string; color: string; tab?: Status }> = {
  pending: { label: '待领取', color: '#f59e0b', tab: 'pending' },
  assigned: { label: '已分配', color: '#00d4ff', tab: 'assigned' },
  annotating: { label: '进行中', color: '#00d4ff', tab: 'annotating' },
  pre_labeling: { label: '预标注中', color: '#a78bfa' },
  submitted: { label: '审核中', color: '#a78bfa', tab: 'submitted' },
  reviewing: { label: '审核中', color: '#a78bfa', tab: 'submitted' },
  approved: { label: '已完成', color: '#10b981', tab: 'approved' },
  rejected: { label: '已驳回', color: '#ef4444' },
}

const MOCK_TASKS: TaskRow[] = Object.entries(DEMO_TASK_ROUTES).map(([id, meta]) => ({
  id: Number.parseInt(id, 10) || 0,
  project: meta.label,
  type: meta.label,
  category: meta.category,
  status: 'pending',
  priority: 5,
  reward: 1,
})).filter(t => t.id > 0)

function priorityLabel(p: number) {
  if (p >= 8) return { label: '高', color: '#ef4444' }
  if (p >= 5) return { label: '中', color: '#f59e0b' }
  return { label: '低', color: '#9ba0ad' }
}

export default function TaskList() {
  const navigate = useNavigate()
  const { token } = useAuthStore()
  const [activeStatus, setActiveStatus] = useState<Status>('all')
  const [tasks, setTasks] = useState<TaskRow[]>(MOCK_TASKS)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!token) {
      setTasks(MOCK_TASKS)
      return
    }
    setLoading(true)
    try {
      const { data } = await taskApi.getList({ page: 1, page_size: 100 })
      const rows: TaskRow[] = (Array.isArray(data) ? data : []).map((t: Record<string, unknown>) => ({
        id: Number(t.id),
        project: String(t.project ?? ''),
        type: String(t.ann_type ?? t.type ?? ''),
        category: t.category as string | undefined,
        ann_type: t.ann_type as string | undefined,
        status: String(t.status ?? 'pending'),
        priority: Number(t.priority ?? 5),
        reward: Number(t.reward ?? 0.1),
      }))
      if (rows.length) setTasks(rows)
      else setTasks(MOCK_TASKS)
    } catch {
      setTasks(MOCK_TASKS)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    load()
  }, [load])

  const filtered = tasks.filter(t => {
    if (activeStatus === 'all') return true
    if (activeStatus === 'in_progress') return t.status === 'annotating' || t.status === 'assigned'
    const st = STATUS_MAP[t.status]
    return st?.tab === activeStatus || t.status === activeStatus
  })

  const TABS: { key: Status | 'in_progress'; label: string }[] = [
    { key: 'all', label: `全部 (${tasks.length})` },
    { key: 'pending', label: '待领取' },
    { key: 'in_progress', label: '进行中' },
    { key: 'submitted', label: '审核中' },
    { key: 'approved', label: '已完成' },
  ]

  function startTask(task: TaskRow) {
    const mode = resolveTaskMode({
      taskId: task.id,
      category: task.category,
      ann_type: task.ann_type,
      type: task.type,
      project: task.project,
    })
    navigate(getAnnotatePath(task.id, mode))
  }

  async function claimAndStart(task: TaskRow) {
    if (token && task.status === 'pending') {
      try {
        await taskApi.claim(task.id)
        message.success('已领取任务')
        await load()
      } catch {
        message.warning('领取失败，仍进入工作台（演示）')
      }
    }
    startTask(task)
  }

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-semibold">任务列表</h1>
        {loading && <span className="text-xs text-white/30">同步中…</span>}
      </div>

      <div className="flex gap-1 mb-6 bg-[#12121a] border border-[#1e1e2e] rounded-xl p-1 w-fit flex-wrap">
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveStatus(tab.key as Status)}
            className={`px-3 py-1.5 rounded-lg text-xs transition-all
              ${activeStatus === tab.key
                ? 'bg-[#00d4ff]/10 text-[#00d4ff] ring-1 ring-[#00d4ff]/20'
                : 'text-white/40 hover:text-white/70'}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1e1e2e]">
              {['任务 ID', '项目', '类型', '优先级', '状态', '奖励', '操作'].map(h => (
                <th
                  key={h}
                  className="px-4 py-3 text-left text-[11px] text-white/30 font-medium uppercase tracking-wider"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((task, i) => {
              const st = STATUS_MAP[task.status] ?? { label: task.status, color: '#9ba0ad' }
              const pr = priorityLabel(task.priority)
              const canStart = ['pending', 'assigned', 'annotating'].includes(task.status)
              return (
                <tr
                  key={task.id}
                  className={`border-b border-[#1e1e2e]/50 hover:bg-white/[0.02] transition-colors
                    ${i === filtered.length - 1 ? 'border-b-0' : ''}`}
                >
                  <td className="px-4 py-3 font-mono text-white/50 text-xs">#{task.id}</td>
                  <td className="px-4 py-3 text-white/70">{task.project}</td>
                  <td className="px-4 py-3 text-white/50 text-xs">{task.type}</td>
                  <td className="px-4 py-3">
                    <span
                      className="text-xs px-2 py-0.5 rounded"
                      style={{ background: `${pr.color}15`, color: pr.color }}
                    >
                      {pr.label}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="text-xs px-2 py-0.5 rounded"
                      style={{ background: `${st.color}15`, color: st.color }}
                    >
                      {st.label}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-[#10b981] font-mono text-xs">¥{task.reward.toFixed(2)}</td>
                  <td className="px-4 py-3">
                    {canStart && (
                      <button
                        onClick={() => claimAndStart(task)}
                        className="text-xs px-3 py-1.5 rounded-lg bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/20
                          hover:bg-[#00d4ff]/20 active:scale-95 transition-all"
                      >
                        {task.status === 'pending' ? '领取并标注' : '继续标注'}
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
