import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { message } from 'antd'
import { taskApi } from '../services/api'
import { getAnnotatePath, resolveTaskMode } from '../utils/annotationRoutes'
import { CATEGORY_HUB_BY_ID } from '../utils/categoryHubs'
import useAuthStore from '../store/authStore'
import { useTasksQuery, type TaskListRow } from '../hooks/queries/useTasks'

type Status = 'all' | 'pending' | 'in_progress' | 'submitted' | 'approved'

type TaskRow = TaskListRow

const STATUS_MAP: Record<string, { label: string; color: string; tab?: Status }> = {
  pending: { label: '待领取', color: '#f59e0b', tab: 'pending' },
  assigned: { label: '已分配', color: '#00d4ff', tab: 'in_progress' },
  annotating: { label: '进行中', color: '#00d4ff', tab: 'in_progress' },
  pre_labeling: { label: '预标注中', color: '#a78bfa' },
  submitted: { label: '审核中', color: '#a78bfa', tab: 'submitted' },
  reviewing: { label: '审核中', color: '#a78bfa', tab: 'submitted' },
  approved: { label: '已完成', color: '#10b981', tab: 'approved' },
  rejected: { label: '已驳回', color: '#ef4444' },
}

const CATEGORY_LABEL: Record<string, string> = Object.fromEntries(
  Object.entries(CATEGORY_HUB_BY_ID).map(([id, h]) => [id, h.label]),
)

const ANN_TO_CAT: Record<string, string> = {
  bbox_2d: 'image_2d', polygon: 'image_2d', polyline: 'image_2d',
  keypoint: 'image_2d', segmentation: 'image_2d', classification: 'image_2d',
  bbox_3d: 'pointcloud_3d', lidar_seg: 'pointcloud_3d', lane_3d: 'pointcloud_3d',
  video_tracking: 'video', video_action: 'video', video_caption: 'video',
  asr: 'audio', tts_label: 'audio', speaker_diarize: 'audio', emotion_audio: 'audio',
  ner: 'nlp', re: 'nlp', sentiment: 'nlp', text_classify: 'nlp',
  qa_pair: 'nlp', summarization: 'nlp', translation: 'nlp',
  robot_traj: 'embodied', robot_action: 'embodied', robot_grasp: 'embodied', robot_scene: 'embodied',
  ocr_text: 'ocr', ocr_layout: 'ocr', ocr_table: 'ocr',
  image_caption: 'multimodal', vqa: 'multimodal', rlhf: 'multimodal',
}

function resolveTaskCategory(t: TaskRow): string {
  const c = (t.category ?? '').toLowerCase()
  if (c) return c
  const ann = (t.ann_type ?? t.type ?? '').toLowerCase()
  return ANN_TO_CAT[ann] ?? ''
}

function priorityLabel(p: number) {
  if (p >= 8) return { label: '高', color: '#ef4444' }
  if (p >= 5) return { label: '中', color: '#f59e0b' }
  return { label: '低', color: '#9ba0ad' }
}

export default function TaskList() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const categoryFilter = searchParams.get('category')
  const { token } = useAuthStore()
  const [activeStatus, setActiveStatus] = useState<Status>('all')
  const {
    data: apiTasks = [],
    isLoading,
    isError,
    refetch,
  } = useTasksQuery()

  const tasks = token ? apiTasks : []
  const loading = Boolean(token) && isLoading

  useEffect(() => {
    if (isError && token) message.error('加载任务失败')
  }, [isError, token])

  const load = () => refetch()

  const filtered = useMemo(() => {
    return tasks.filter(t => {
      if (categoryFilter) {
        const cat = resolveTaskCategory(t)
        if (cat !== categoryFilter) return false
      }
      if (activeStatus === 'all') return true
      if (activeStatus === 'in_progress') return t.status === 'annotating' || t.status === 'assigned'
      const st = STATUS_MAP[t.status]
      return st?.tab === activeStatus || t.status === activeStatus
    })
  }, [tasks, activeStatus, categoryFilter])

  const TABS: { key: Status | 'in_progress'; label: string }[] = [
    { key: 'all', label: `全部 (${filtered.length})` },
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
    const base = getAnnotatePath(task.id, mode)
    if (task.project_id) {
      const sep = base.includes('?') ? '&' : '?'
      navigate(`${base}${sep}projectId=${task.project_id}`)
      return
    }
    navigate(base)
  }

  async function claimAndStart(task: TaskRow) {
    if (token && task.status === 'pending') {
      try {
        await taskApi.claim(task.id)
        message.success('已领取任务')
        await load()
      } catch {
        message.error('领取失败，请稍后重试')
        return
      }
    }
    startTask(task)
  }

  const title =
    categoryFilter && CATEGORY_LABEL[categoryFilter]
      ? `${CATEGORY_LABEL[categoryFilter]}任务`
      : '任务列表'

  return (
    <div className="p-8 max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold">{title}</h1>
          {categoryFilter && (
            <p className="text-xs text-white/30 mt-1">
              仅显示「{CATEGORY_LABEL[categoryFilter] ?? categoryFilter}」相关任务
            </p>
          )}
        </div>
        {loading && <span className="text-xs text-white/30">同步中…</span>}
      </div>

      <div className="flex gap-1 mb-6 bg-[#12121a] border border-[#1e1e2e] rounded-xl p-1 w-fit flex-wrap">
        {TABS.map(tab => (
          <button
            key={tab.key}
            type="button"
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
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-xs text-white/30">
                  {categoryFilter
                    ? `暂无「${CATEGORY_LABEL[categoryFilter] ?? categoryFilter}」任务`
                    : '暂无任务'}
                </td>
              </tr>
            ) : (
              filtered.map((task, i) => {
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
                          type="button"
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
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
