import { useQuery, useQueryClient } from '@tanstack/react-query'
import { qualityApi } from '../../services/api'

export type ReviewQueueItem = {
  id: number
  project_id: number
  project_name: string
  category?: string
  ann_type?: string
  status: string
  data_url?: string
  filename?: string
  assignee_name?: string
  submitted_at?: string
  box_count?: number
}

export function reviewQueueKey(projectId?: string | null) {
  return ['quality', 'queue', projectId ?? 'all'] as const
}

export function useReviewQueueQuery(projectId?: string | null) {
  return useQuery({
    queryKey: reviewQueueKey(projectId),
    queryFn: async () => {
      const { data } = await qualityApi.getQueue({
        project_id: projectId ? Number(projectId) : undefined,
        limit: 80,
      })
      return (data.items ?? []) as unknown as ReviewQueueItem[]
    },
    staleTime: 15_000,
  })
}

export function useInvalidateReviewQueue() {
  const qc = useQueryClient()
  return (_projectId?: string | null) =>
    qc.invalidateQueries({ queryKey: ['quality', 'queue'] })
}
