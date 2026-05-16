import { useCallback, useEffect, useRef, useState } from 'react'
import { message } from 'antd'
import useAuthStore from '../store/authStore'
import { isDemoTaskId } from '../utils/annotationRoutes'
import {
  modalityApi,
  offlineAudioWorkspace,
  offlineMultimodalWorkspace,
  offlineTextWorkspace,
  offlineVideoWorkspace,
  type ModalityPayload,
  type ModalityWorkspace,
} from '../services/modalityAnnotation'

type ModalityKind = 'text' | 'audio' | 'video' | 'multimodal'

function offlineFor(kind: ModalityKind, taskId: string, annType?: string): ModalityWorkspace {
  if (kind === 'audio') return offlineAudioWorkspace(taskId)
  if (kind === 'video') return offlineVideoWorkspace(taskId)
  if (kind === 'multimodal') return offlineMultimodalWorkspace(taskId)
  return offlineTextWorkspace(taskId, annType)
}

export function useModalityWorkspace(
  taskId: string,
  kind: ModalityKind,
  annTypeHint?: string,
) {
  const { token } = useAuthStore()
  const [ws, setWs] = useState<ModalityWorkspace | null>(null)
  const [payload, setPayload] = useState<ModalityPayload | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const [useBackend, setUseBackend] = useState(false)
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const startRef = useRef(Date.now())

  const load = useCallback(async () => {
    setLoading(true)
    try {
      if (token && /^\d+$/.test(taskId) && !isDemoTaskId(taskId)) {
        const data = await modalityApi.getWorkspace(taskId)
        setWs(data)
        setPayload(data.payload)
        setLastSavedAt(data.draft_updated_at ?? null)
        setUseBackend(true)
      } else {
        const data = offlineFor(kind, taskId, annTypeHint)
        setWs(data)
        setPayload(data.payload)
        setUseBackend(false)
      }
    } catch {
      const data = offlineFor(kind, taskId, annTypeHint)
      setWs(data)
      setPayload(data.payload)
      setUseBackend(false)
    } finally {
      setLoading(false)
    }
  }, [taskId, token, kind, annTypeHint])

  useEffect(() => {
    load()
  }, [load])

  const persist = useCallback(
    async (next: ModalityPayload, silent = true) => {
      if (!useBackend || !/^\d+$/.test(taskId) || isDemoTaskId(taskId)) return
      setSaving(true)
      try {
        await modalityApi.saveWorkspace(taskId, next)
        const at = new Date().toISOString()
        setLastSavedAt(at)
        if (!silent) message.success('草稿已保存')
      } catch {
        if (!silent) message.error('保存失败')
      } finally {
        setSaving(false)
      }
    },
    [taskId, useBackend],
  )

  const updatePayload = useCallback(
    (patch: Partial<ModalityPayload> | ((p: ModalityPayload) => ModalityPayload)) => {
      setPayload(prev => {
        if (!prev) return prev
        const next = typeof patch === 'function' ? patch(prev) : { ...prev, ...patch }
        if (saveTimer.current) clearTimeout(saveTimer.current)
        saveTimer.current = setTimeout(() => persist(next), 2000)
        return next
      })
    },
    [persist],
  )

  const submit = useCallback(async () => {
    if (!payload) return
    if (useBackend && /^\d+$/.test(taskId) && !isDemoTaskId(taskId)) {
      const workTime = Math.round((Date.now() - startRef.current) / 1000)
      await modalityApi.submit(taskId, payload, workTime)
      message.success('已提交标注')
    } else {
      message.info('离线模式：请登录后提交到服务器')
    }
  }, [payload, taskId, useBackend])

  return {
    ws,
    payload,
    setPayload,
    updatePayload,
    loading,
    saving,
    lastSavedAt,
    useBackend,
    persist,
    submit,
    reload: load,
  }
}
