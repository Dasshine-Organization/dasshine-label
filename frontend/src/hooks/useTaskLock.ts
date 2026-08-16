/** 任务标注占用锁（心跳 + TTL）。 */

import { useEffect, useState } from 'react'
import { taskApi } from '../services/api'
import { isDemoTaskId } from '../utils/annotationRoutes'
import useAuthStore from '../store/authStore'

export type TaskLockState = {
  acquired: boolean
  locked: boolean
  holderUsername: string | null
  holderUserId: number | null
  expiresAt: string | null
}

const EMPTY: TaskLockState = {
  acquired: false,
  locked: false,
  holderUsername: null,
  holderUserId: null,
  expiresAt: null,
}

/**
 * 打开工作台时抢占锁；每 45s 心跳；卸载释放。
 * 未抢到时 readOnlyHint=true，应禁用编辑。
 */
export function useTaskLock(taskId: string | undefined, enabled = true) {
  const token = useAuthStore(s => s.token)
  const [lock, setLock] = useState<TaskLockState>(EMPTY)

  useEffect(() => {
    if (!enabled || !token || !taskId || !/^\d+$/.test(taskId) || isDemoTaskId(taskId)) {
      setLock(EMPTY)
      return
    }
    const id = Number(taskId)
    let cancelled = false
    let timer: ReturnType<typeof setInterval> | null = null

    const map = (data: Record<string, unknown>): TaskLockState => ({
      acquired: Boolean(data.acquired),
      locked: Boolean(data.locked),
      holderUsername: (data.holder_username as string) || null,
      holderUserId: typeof data.holder_user_id === 'number' ? data.holder_user_id : null,
      expiresAt: (data.expires_at as string) || null,
    })

    async function acquire() {
      try {
        const { data } = await taskApi.acquireLock(id)
        if (!cancelled) setLock(map(data as Record<string, unknown>))
      } catch {
        if (!cancelled) setLock(EMPTY)
      }
    }

    async function heartbeat() {
      try {
        const { data } = await taskApi.acquireLock(id)
        if (!cancelled) setLock(map(data as Record<string, unknown>))
      } catch {
        /* ignore */
      }
    }

    acquire()
    timer = setInterval(heartbeat, 45_000)

    return () => {
      cancelled = true
      if (timer) clearInterval(timer)
      taskApi.releaseLock(id).catch(() => undefined)
    }
  }, [taskId, token, enabled])

  const blocked = lock.locked && !lock.acquired

  return { lock, blocked, readOnly: blocked }
}
