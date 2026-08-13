import { useQuery } from '@tanstack/react-query'
import { taskApi } from '../../services/api'
import useAuthStore from '../../store/authStore'

export type TaskListRow = {
  id: number
  project_id?: number
  project: string
  type: string
  category?: string
  ann_type?: string
  status: string
  priority: number
  reward: number
}

export function tasksQueryKey(token: string | null) {
  return ['tasks', 'list', token ? 'auth' : 'guest'] as const
}

export function useTasksQuery() {
  const { token } = useAuthStore()
  return useQuery({
    queryKey: tasksQueryKey(token),
    queryFn: async (): Promise<TaskListRow[]> => {
      if (!token) return []
      const { data } = await taskApi.getList({ page: 1, page_size: 100 })
      return (Array.isArray(data) ? data : []).map((t: Record<string, unknown>) => ({
        id: Number(t.id),
        project_id: t.project_id != null ? Number(t.project_id) : undefined,
        project: String(t.project ?? ''),
        type: String(t.ann_type ?? t.type ?? ''),
        category: t.category as string | undefined,
        ann_type: t.ann_type as string | undefined,
        status: String(t.status ?? 'pending'),
        priority: Number(t.priority ?? 5),
        reward: Number(t.reward ?? 0.1),
      }))
    },
    enabled: Boolean(token),
    staleTime: 20_000,
  })
}
