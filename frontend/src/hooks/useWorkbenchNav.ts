import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { taskApi } from '../services/api'
import { getAnnotatePath, resolveTaskMode } from '../utils/annotationRoutes'

export function useWorkbenchNav(taskId: string, projectId?: number | string | null) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const pid = projectId != null ? Number(projectId) : undefined

  const openTask = useCallback(
    (task: Record<string, unknown>) => {
      const id = Number(task.id)
      if (!id) return
      const mode = resolveTaskMode({
        taskId: id,
        category: task.category as string | undefined,
        ann_type: task.ann_type as string | undefined,
      })
      const base = getAnnotatePath(id, mode)
      const sep = base.includes('?') ? '&' : '?'
      const q = pid && !Number.isNaN(pid) ? `${sep}projectId=${pid}` : ''
      navigate(`${base}${q}`)
    },
    [navigate, pid],
  )

  const claimNext = useCallback(async () => {
    setBusy(true)
    try {
      const { data } = await taskApi.claimNext(pid && !Number.isNaN(pid) ? pid : undefined)
      message.success('已领取下一题')
      openTask(data.task)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '领取下一题失败')
    } finally {
      setBusy(false)
    }
  }, [pid, openTask])

  const skip = useCallback(async () => {
    if (!/^\d+$/.test(taskId)) return
    setBusy(true)
    try {
      await taskApi.skip(Number(taskId))
      message.success('已跳过')
      await claimNext()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '跳过失败')
      setBusy(false)
    }
  }, [taskId, claimNext])

  return { busy, claimNext, skip }
}
