import { useCallback, useState } from 'react'
import { message } from 'antd'
import { autoLabelApi } from '../services/api'
import { isDemoTaskId } from '../utils/annotationRoutes'

function errDetail(e: unknown): string {
  const err = e as { response?: { data?: { detail?: string } } }
  const d = err.response?.data?.detail
  return typeof d === 'string' && d ? d : '自动标注失败'
}

export function useAutoLabel(
  taskId: string | undefined,
  enabled: boolean,
  reload: () => void | Promise<void>,
) {
  const [busy, setBusy] = useState(false)

  const run = useCallback(async () => {
    if (!enabled || !taskId || !/^\d+$/.test(taskId) || isDemoTaskId(taskId)) return
    setBusy(true)
    try {
      const { data } = await autoLabelApi.process(Number(taskId))
      if (!data.success) {
        message.warning(data.message || '自动标注未产生结果')
        return
      }
      const pct = Math.round((data.confidence ?? 0) * 100)
      const n = data.results?.length ?? 0
      message.success(
        data.high_confidence
          ? `AI 预标注完成（高置信 ${pct}% · ${n} 项），可直接核对`
          : `已写入 AI 草稿（置信 ${pct}%），请人工确认`,
      )
      await reload()
    } catch (e) {
      message.error(errDetail(e))
    } finally {
      setBusy(false)
    }
  }, [taskId, enabled, reload])

  return { busy, run }
}
