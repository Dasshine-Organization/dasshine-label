import { useCallback, useEffect, useRef, useState } from 'react'
import { message } from 'antd'
import { notifyDraftSaved } from '../utils/draftSaveNotify'
import useAuthStore from '../store/authStore'
import { isDemoTaskId } from '../utils/annotationRoutes'
import { useTaskLock } from './useTaskLock'
import {
  modalityApi,
  offlineAudioWorkspace,
  offlineMultimodalWorkspace,
  offlineTextWorkspace,
  offlineVideoWorkspace,
  type ModalityPayload,
  type ModalityWorkspace,
} from '../services/modalityAnnotation'

type ModalityKind = 'text' | 'audio' | 'video' | 'multimodal' | 'ocr'

function offlineFor(kind: ModalityKind, taskId: string, annType?: string): ModalityWorkspace {
  if (kind === 'audio') return offlineAudioWorkspace(taskId)
  if (kind === 'video') return offlineVideoWorkspace(taskId)
  if (kind === 'multimodal') return offlineMultimodalWorkspace(taskId)
  if (kind === 'ocr') {
    return {
      task_id: Number.parseInt(taskId, 10) || 0,
      project_id: 0,
      project_name: 'OCR 标注（离线）',
      category: 'ocr',
      ann_type: annType || 'ocr_text',
      modality: 'ocr',
      content: {
        image_url:
          'https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png',
      },
      payload: { schema: 'dasshine.modality.v1', modality: 'ocr', ann_type: 'ocr_text', spans: [] },
      label_classes: [
        { id: 'text', name: '文字', color: '#06b6d4' },
        { id: 'title', name: '标题', color: '#f97316' },
      ],
    }
  }
  return offlineTextWorkspace(taskId, annType)
}

function localDraftKey(kind: ModalityKind, taskId: string) {
  return `dasshine_modality_draft_${kind}_${taskId}`
}

function readLocalDraft(kind: ModalityKind, taskId: string): {
  payload: ModalityPayload
  savedAt: string
} | null {
  try {
    const raw = localStorage.getItem(localDraftKey(kind, taskId))
    if (!raw) return null
    const data = JSON.parse(raw) as { payload?: ModalityPayload; savedAt?: string }
    if (data.payload && typeof data.payload === 'object') {
      return {
        payload: data.payload,
        savedAt: data.savedAt ?? new Date().toISOString(),
      }
    }
  } catch {
    /* ignore */
  }
  return null
}

function writeLocalDraft(kind: ModalityKind, taskId: string, payload: ModalityPayload): string {
  const savedAt = new Date().toISOString()
  try {
    localStorage.setItem(localDraftKey(kind, taskId), JSON.stringify({ payload, savedAt }))
  } catch {
    /* quota */
  }
  return savedAt
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
  const [dirty, setDirty] = useState(false)
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const startRef = useRef(Date.now())
  const { lock, blocked: lockBlocked } = useTaskLock(
    taskId,
    Boolean(token && /^\d+$/.test(taskId) && !isDemoTaskId(taskId)),
  )

  const load = useCallback(async () => {
    setLoading(true)
    try {
      if (token && /^\d+$/.test(taskId) && !isDemoTaskId(taskId)) {
        const data = await modalityApi.getWorkspace(taskId)
        const local = readLocalDraft(kind, taskId)
        // 服务端有草稿优先；否则用本地
        const serverEmpty =
          !data.payload ||
          (typeof data.payload === 'object' && Object.keys(data.payload).length === 0)
        if (serverEmpty && local) {
          setWs(data)
          setPayload(local.payload)
          setLastSavedAt(local.savedAt)
        } else {
          setWs(data)
          setPayload(data.payload)
          setLastSavedAt(data.draft_updated_at ?? local?.savedAt ?? null)
        }
        setUseBackend(true)
      } else {
        const data = offlineFor(kind, taskId, annTypeHint)
        const local = readLocalDraft(kind, taskId)
        setWs(data)
        setPayload(local?.payload ?? data.payload)
        setLastSavedAt(local?.savedAt ?? null)
        setUseBackend(false)
      }
    } catch {
      const data = offlineFor(kind, taskId, annTypeHint)
      const local = readLocalDraft(kind, taskId)
      setWs(data)
      setPayload(local?.payload ?? data.payload)
      setLastSavedAt(local?.savedAt ?? null)
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
      setSaving(true)
      try {
        const at = writeLocalDraft(kind, taskId, next)
        setLastSavedAt(at)
        setDirty(false)

        if (useBackend && /^\d+$/.test(taskId) && !isDemoTaskId(taskId)) {
          await modalityApi.saveWorkspace(taskId, next)
        }

        if (!silent) notifyDraftSaved()
      } catch {
        if (!silent) message.error('保存失败')
      } finally {
        setSaving(false)
      }
    },
    [taskId, useBackend, kind],
  )

  const updatePayload = useCallback(
    (patch: Partial<ModalityPayload> | ((p: ModalityPayload) => ModalityPayload)) => {
      if (lockBlocked) {
        message.warning('任务已被他人占用，暂不可编辑')
        return
      }
      setPayload(prev => {
        if (!prev) return prev
        const next = typeof patch === 'function' ? patch(prev) : { ...prev, ...patch }
        setDirty(true)
        if (saveTimer.current) clearTimeout(saveTimer.current)
        saveTimer.current = setTimeout(() => persist(next), 2000)
        return next
      })
    },
    [persist, lockBlocked],
  )

  const submit = useCallback(async () => {
    if (!payload) return
    if (lockBlocked) {
      message.warning('任务已被他人占用，暂不可提交')
      return
    }
    writeLocalDraft(kind, taskId, payload)
    if (useBackend && /^\d+$/.test(taskId) && !isDemoTaskId(taskId)) {
      const workTime = Math.round((Date.now() - startRef.current) / 1000)
      await modalityApi.submit(taskId, payload, workTime)
      message.success('已提交标注')
    } else {
      message.info('离线模式：草稿已保存在本地，登录后可提交到服务器')
    }
  }, [payload, taskId, useBackend, kind, lockBlocked])

  return {
    ws,
    payload,
    setPayload,
    updatePayload,
    loading,
    saving,
    dirty,
    lastSavedAt,
    useBackend,
    persist,
    submit,
    reload: load,
    lock,
    lockBlocked,
  }
}
