import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import { getAnnotatePath, resolveTaskMode } from '../utils/annotationRoutes'
import useAuthStore from '../store/authStore'

export type ProjectQueueTask = {
  id: number
  filename?: string
  status?: string
  category?: string
  ann_type?: string
}

export function useProjectAnnotationQueue(projectId: string | null, taskId: string) {
  const navigate = useNavigate()
  const { token } = useAuthStore()
  const [tasks, setTasks] = useState<ProjectQueueTask[]>([])
  const [loading, setLoading] = useState(false)

  const pid = projectId ? Number(projectId) : NaN

  useEffect(() => {
    if (!token || !projectId || Number.isNaN(pid)) {
      setTasks([])
      return
    }
    let cancelled = false
    setLoading(true)
    api
      .get(`/projects/${pid}/tasks`, { params: { page: 1, page_size: 500 } })
      .then(({ data }) => {
        if (cancelled) return
        const items = (data.items ?? []) as ProjectQueueTask[]
        setTasks(items)
      })
      .catch(() => {
        if (!cancelled) setTasks([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [projectId, pid, token])

  const currentIndex = tasks.findIndex(t => String(t.id) === String(taskId))
  const index = currentIndex >= 0 ? currentIndex : 0

  const goToTask = useCallback(
    (target: ProjectQueueTask) => {
      const mode = resolveTaskMode({
        taskId: target.id,
        category: target.category,
        ann_type: target.ann_type,
      })
      const base = getAnnotatePath(target.id, mode)
      const sep = base.includes('?') ? '&' : '?'
      navigate(`${base}${sep}projectId=${pid}`)
    },
    [navigate, pid],
  )

  const goPrevTask = useCallback(() => {
    if (index <= 0 || !tasks.length) return
    goToTask(tasks[index - 1])
  }, [index, tasks, goToTask])

  const goNextTask = useCallback(() => {
    if (index >= tasks.length - 1 || !tasks.length) return
    goToTask(tasks[index + 1])
  }, [index, tasks, goToTask])

  const refreshTasks = useCallback(() => {
    if (!token || !projectId || Number.isNaN(pid)) return Promise.resolve()
    return api
      .get(`/projects/${pid}/tasks`, { params: { page: 1, page_size: 500 } })
      .then(({ data }) => {
        const items = (data.items ?? []) as ProjectQueueTask[]
        setTasks(items)
      })
      .catch(() => undefined)
  }, [projectId, pid, token])

  const patchTaskStatus = useCallback((taskId: number, status: string) => {
    setTasks(prev =>
      prev.map(t => (t.id === taskId ? { ...t, status } : t)),
    )
  }, [])

  return {
    tasks,
    loading,
    taskIndex: index,
    taskTotal: tasks.length,
    hasQueue: tasks.length > 1,
    goPrevTask,
    goNextTask,
    currentTask: tasks[index],
    refreshTasks,
    patchTaskStatus,
  }
}
