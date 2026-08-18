import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { message } from 'antd'
import { v4 as uuid } from 'uuid'
import useAnnotationStore from '../store/annotationStore'
import { useAnnotationHotkeys } from '../hooks/useAnnotation'
import '../components/annotation/annotation.css'

import AnnotationTopBar from '../components/annotation/AnnotationTopBar'
import AnnotationToolbar from '../components/annotation/AnnotationToolbar'
import Scene3DWorkspace from '../components/annotation/3d/Scene3DWorkspace'
import RightPanel from '../components/annotation/RightPanel'
import ExportPanel from '../components/annotation/ExportPanel'
import CollabPresenceBar from '../components/CollabPresenceBar'
import useAuthStore from '../store/authStore'
import type { Box3D } from '../store/annotationStore'
import { taskApi } from '../services/api'
import { useYjsCollab } from '../hooks/useYjsCollab'
import { getAnnotateBackHref, isDemoTaskId } from '../utils/annotationRoutes'
import { useProjectAnnotationQueue } from '../hooks/useProjectAnnotationQueue'
import { emitProjectTaskStatus } from '../utils/projectTaskStatus'
import {
  applyPointCloudSessionToStore,
  countPointCloudLabeled,
  exportPointCloudSessionPayload,
  mergePointCloudSessions,
  parsePointCloudPayload,
  persistPointCloudSession,
  readPointCloudSession,
} from '../utils/pointCloudAnnotationSession'
import { acknowledgeManualDraftSave } from '../utils/draftSaveNotify'

const TASK_STATUS_LABEL: Record<string, string> = {
  pending: '待领取',
  assigned: '已分配',
  annotating: '标注中',
  submitted: '已提交',
  approved: '已通过',
}

export default function PointCloudAnnotation() {
  const { taskId = '1001' } = useParams<{ taskId: string }>()
  const [searchParams] = useSearchParams()
  const projectId = searchParams.get('projectId')
  const { token } = useAuthStore()
  const projectQueue = useProjectAnnotationQueue(projectId, taskId)

  const [showExport, setShowExport] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [hydrated, setHydrated] = useState(false)
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const [pointCloudUrl, setPointCloudUrl] = useState<string | undefined>(undefined)
  const { boxes3d, labelClasses, pointLabels } = useAnnotationStore()

  const numericTaskId = Number(taskId)
  const useBackendTask =
    Boolean(token) &&
    Number.isFinite(numericTaskId) &&
    numericTaskId > 0 &&
    !isDemoTaskId(taskId)

  const { peers, connected, pushDraft } = useYjsCollab(
    taskId,
    useBackendTask,
    useCallback((draft: Record<string, unknown>) => {
      const boxes = draft.boxes3d
      if (Array.isArray(boxes)) {
        useAnnotationStore.setState({ boxes3d: boxes as Box3D[] })
      }
      if (draft.pointLabels && typeof draft.pointLabels === 'object') {
        useAnnotationStore.setState({
          pointLabels: draft.pointLabels as Record<string, string>,
        })
      }
    }, []),
  )

  useEffect(() => {
    if (!useBackendTask || !connected) return
    pushDraft({ boxes3d, labelClasses, pointLabels })
  }, [boxes3d, labelClasses, pointLabels, useBackendTask, connected, pushDraft])

  const workStartRef = useRef(Date.now())
  const syncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const notifyTaskStatus = useCallback(
    (status: string) => {
      if (!useBackendTask) return
      projectQueue.patchTaskStatus(numericTaskId, status)
      if (projectId) {
        emitProjectTaskStatus({
          projectId: Number(projectId),
          taskId: numericTaskId,
          status,
        })
      }
    },
    [useBackendTask, projectQueue, numericTaskId, projectId],
  )

  const syncToServer = useCallback(async () => {
    if (!useBackendTask) return
    const payload = exportPointCloudSessionPayload(taskId)
    if (!payload) return
    try {
      const { data } = await taskApi.saveAnnotationDraft(
        numericTaskId,
        payload as unknown as Record<string, unknown>,
      )
      if (data.task_status) notifyTaskStatus(data.task_status)
    } catch {
      /* 离线或网络异常时保留本地会话 */
    }
  }, [useBackendTask, taskId, numericTaskId, notifyTaskStatus])

  const persistNow = useCallback(
    (showSavedToast = false) => {
      const { boxes3d: b3, labelClasses: lc } = useAnnotationStore.getState()
      const savedAt = persistPointCloudSession(taskId, b3, lc)
      setLastSavedAt(savedAt)
      if (showSavedToast) acknowledgeManualDraftSave()
      if (useBackendTask) {
        if (syncTimerRef.current) clearTimeout(syncTimerRef.current)
        syncTimerRef.current = setTimeout(() => {
          void syncToServer()
        }, 800)
      }
    },
    [taskId, useBackendTask, syncToServer],
  )

  const handleSubmit = useCallback(async () => {
    persistNow(true)
    if (!useBackendTask) {
      message.success({ content: '标注已提交', duration: 2 })
      return
    }
    const payload = exportPointCloudSessionPayload(taskId)
    if (!payload || payload.boxes3d.length === 0) {
      message.warning('暂无 3D 标注可提交')
      return
    }
    try {
      const workTime = Math.round((Date.now() - workStartRef.current) / 1000)
      const { data } = await taskApi.submitPointCloudAnnotation(numericTaskId, {
        payload: payload as unknown as Record<string, unknown>,
        work_time: workTime,
      })
      if (data.task_status) notifyTaskStatus(data.task_status)
      await projectQueue.refreshTasks()
      message.success({ content: data.message ?? '标注已提交', duration: 2 })
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '提交失败'
      message.error(detail)
    }
  }, [
    persistNow,
    useBackendTask,
    taskId,
    numericTaskId,
    notifyTaskStatus,
    projectQueue.refreshTasks,
  ])

  useEffect(() => {
    let cancelled = false
    workStartRef.current = Date.now()
    setHydrated(false)
    setPointCloudUrl(undefined)
    useAnnotationStore.getState().setMode('3d')
    useAnnotationStore.getState().setCurrentTask(taskId, 0)
    useAnnotationStore.setState({
      boxes3d: [],
      selectedIds3d: [],
      past: [],
      future: [],
      autoSaveMeta: {
        lastSavedAt: null,
        isDirty: false,
        saveCount: 0,
        error: null,
      },
    })

    ;(async () => {
      try {
        const local = readPointCloudSession(taskId)
        let merged = local

        if (useBackendTask) {
          try {
            const { data: task } = await taskApi.getById(numericTaskId)
            if (!cancelled && task?.data_url) {
              setPointCloudUrl(String(task.data_url))
            }
          } catch {
            /* 无 data_url 时回退 demo / 合成点云 */
          }
          try {
            const { data } = await taskApi.getAnnotationDraft(numericTaskId)
            if (cancelled) return
            const remote = parsePointCloudPayload(
              taskId,
              (data.payload ?? {}) as Record<string, unknown>,
            )
            merged = mergePointCloudSessions(local, remote, data.updated_at ?? null)
          } catch {
            /* 使用本地会话 */
          }
        } else {
          setPointCloudUrl(undefined)
        }

        if (cancelled) return
        if (merged) {
          applyPointCloudSessionToStore(merged)
          setLastSavedAt(merged.savedAt)
        }
      } finally {
        if (!cancelled) setHydrated(true)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [taskId, useBackendTask, numericTaskId])

  useEffect(() => {
    if (!hydrated) return
    const t = window.setTimeout(() => persistNow(), 500)
    return () => window.clearTimeout(t)
  }, [boxes3d, labelClasses, taskId, hydrated, persistNow])

  useEffect(() => {
    if (!hydrated) return
    const id = window.setInterval(() => persistNow(), 12_000)
    return () => window.clearInterval(id)
  }, [hydrated, persistNow])

  useAnnotationHotkeys({ onSave: () => persistNow(true) })

  const labeledFrames = useMemo(() => countPointCloudLabeled(boxes3d), [boxes3d])

  function loadAI3D() {
    setAiLoading(true)
    setTimeout(() => {
      const boxes = [
        {
          id: uuid(),
          label: 'car',
          color: '#00d4ff',
          center: { x: 6, y: 0.55, z: -1.5 },
          size: { x: 4.2, y: 1.5, z: 1.9 },
          rotation: { x: 0, y: 0.15, z: 0 },
          visible: true,
          locked: false,
          score: 0.92,
          isAI: true,
        },
        {
          id: uuid(),
          label: 'car',
          color: '#a78bfa',
          center: { x: -4, y: 0.5, z: 4.5 },
          size: { x: 3.8, y: 1.4, z: 1.7 },
          rotation: { x: 0, y: 1.2, z: 0 },
          visible: true,
          locked: false,
          score: 0.86,
          isAI: true,
        },
        {
          id: uuid(),
          label: 'truck',
          color: '#10b981',
          center: { x: 1.5, y: 0.85, z: -8 },
          size: { x: 7.5, y: 2.8, z: 2.2 },
          rotation: { x: 0, y: -0.05, z: 0 },
          visible: true,
          locked: false,
          score: 0.78,
          isAI: true,
        },
      ]
      useAnnotationStore.setState({ boxes3d: boxes })
      useAnnotationStore.getState().markDirty()
      setAiLoading(false)
      message.success({ content: `AI 3D 预标注完成，生成 ${boxes.length} 个包围盒`, duration: 3 })
    }, 1400)
  }

  if (!hydrated) {
    return (
      <div className="flex flex-col h-screen bg-[#0a0a0f] text-white items-center justify-center">
        <span className="w-8 h-8 border-2 border-[#00d4ff]/20 border-t-[#00d4ff] rounded-full animate-spin" />
        <p className="text-xs text-white/40 mt-4">加载标注数据…</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0f] text-white overflow-hidden select-none">
      <CollabPresenceBar peers={peers} connected={connected} />
      <AnnotationTopBar
        taskName={`Task #${taskId} — 自动驾驶点云标注（路口场景）`}
        totalImages={1}
        currentImage={1}
        labeledFrames={labeledFrames}
        onExport={() => setShowExport(v => !v)}
        saveHint={
          lastSavedAt ? `已保存 ${new Date(lastSavedAt).toLocaleTimeString()}` : undefined
        }
        onManualSave={() => persistNow(true)}
        onSubmit={() => void handleSubmit()}
        backHref={getAnnotateBackHref({ projectId, category: 'pointcloud_3d' })}
        projectTaskIndex={projectQueue.hasQueue ? projectQueue.taskIndex : undefined}
        projectTaskTotal={projectQueue.hasQueue ? projectQueue.taskTotal : undefined}
        onPrevTask={projectQueue.hasQueue ? projectQueue.goPrevTask : undefined}
        onNextTask={projectQueue.hasQueue ? projectQueue.goNextTask : undefined}
        taskStatusLabel={
          projectQueue.currentTask?.status
            ? TASK_STATUS_LABEL[projectQueue.currentTask.status] ??
              projectQueue.currentTask.status
            : undefined
        }
      />
      <div className="flex flex-1 overflow-hidden">
        <AnnotationToolbar />
        <div className="flex-1 relative overflow-hidden">
          <Scene3DWorkspace taskId={taskId} pointCloudUrl={pointCloudUrl} />

          <div className="absolute top-3 left-1/2 -translate-x-1/2 flex items-center gap-2 z-20 pointer-events-auto">
            <button
              onClick={loadAI3D}
              disabled={aiLoading}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border backdrop-blur-sm transition-all active:scale-95
                ${
                  aiLoading
                    ? 'bg-black/40 border-[#a78bfa]/15 text-[#a78bfa]/40 cursor-not-allowed'
                    : 'bg-black/50 border-[#a78bfa]/30 text-[#a78bfa] hover:bg-[#7c3aed]/15'
                }`}
            >
              {aiLoading ? (
                <span className="w-3 h-3 border border-[#a78bfa]/30 border-t-[#a78bfa] rounded-full animate-spin" />
              ) : (
                <svg
                  viewBox="0 0 16 16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  className="w-3.5 h-3.5"
                >
                  <path
                    d="M8 1l1.5 3 3.5.5-2.5 2.5.5 3.5L8 9l-3 1.5.5-3.5L3 4.5 6.5 4 8 1z"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
              {aiLoading ? 'AI 3D 预标注中…' : 'AI 3D 预标注'}
            </button>
            {boxes3d.filter(b => b.isAI).length > 0 && (
              <div className="flex items-center gap-2 bg-black/50 backdrop-blur-sm border border-[#a78bfa]/20 text-[#a78bfa]/70 text-[10px] px-2.5 py-1.5 rounded-lg">
                <span className="w-1.5 h-1.5 rounded-full bg-[#a78bfa] animate-pulse" />
                {boxes3d.filter(b => b.isAI).length} AI 候选 3D 框
              </div>
            )}
          </div>

          {showExport && (
            <div className="absolute top-12 right-4 z-30">
              <ExportPanel taskId={taskId} onClose={() => setShowExport(false)} />
            </div>
          )}
        </div>
        <RightPanel taskId={taskId} />
      </div>
    </div>
  )
}
