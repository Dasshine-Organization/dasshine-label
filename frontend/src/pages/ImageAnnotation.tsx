import { useParams, useSearchParams } from 'react-router-dom'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { message, Select, Button, Tooltip } from 'antd'
import useAnnotationStore, { Annotation2D } from '../store/annotationStore'
import { useAnnotationHotkeys, useDraftManager } from '../hooks/useAnnotation'
import '../components/annotation/annotation.css'

import AnnotationTopBar from '../components/annotation/AnnotationTopBar'
import AnnotationToolbar from '../components/annotation/AnnotationToolbar'
import Canvas2D from '../components/annotation/2d/Canvas2D'
import RightPanel from '../components/annotation/RightPanel'
import ExportPanel from '../components/annotation/ExportPanel'
import useAuthStore from '../store/authStore'
import {
  canAddOrEditLabelClasses,
  canDeleteLabelClasses,
  parseProjectMemberRole,
  resolveIsProjectOwner,
} from '../utils/imageAnnotationPermissions'
import {
  applyFrameToStore,
  countLabeledFrames,
  exportImageSessionPayload,
  persistImageSessionSlice,
  readImageSession,
  syncSessionDraftsToStore,
} from '../utils/imageAnnotationSession'
import { useProjectAnnotationQueue } from '../hooks/useProjectAnnotationQueue'
import { emitProjectTaskStatus } from '../utils/projectTaskStatus'
import {
  canLoadPrelabelModel,
  formatPrelabelOptionLabel,
  prelabelApi,
  type PrelabelModelInfo,
} from '../services/prelabel'
import { taskApi } from '../services/api'
import { isDemoTaskId } from '../utils/annotationRoutes'

const MOCK_IMAGES = [
  'https://images.unsplash.com/photo-1545558014-8692077e9b5c?w=1280&q=80',
  'https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=1280&q=80',
  'https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=1280&q=80',
  'https://images.unsplash.com/photo-1486325212027-8081e485255e?w=1280&q=80',
  'https://images.unsplash.com/photo-1498036882173-b41c28a8ba34?w=1280&q=80',
]

/** 离线演示：无后端时的固定候选框 */
function offlineDemoAnnotations(idx: number): Annotation2D[] {
  const templates = [
    [
      { label: 'car', color: '#00d4ff', pts: [{ x: 120, y: 200 }, { x: 360, y: 380 }], score: 0.94 },
      { label: 'person', color: '#7c3aed', pts: [{ x: 440, y: 120 }, { x: 510, y: 310 }], score: 0.88 },
    ],
    [
      { label: 'person', color: '#7c3aed', pts: [{ x: 80, y: 150 }, { x: 160, y: 350 }], score: 0.82 },
      { label: 'car', color: '#00d4ff', pts: [{ x: 300, y: 240 }, { x: 550, y: 400 }], score: 0.95 },
    ],
  ]
  const tpl = templates[idx % templates.length] ?? []
  return tpl.map(t => ({
    id: crypto.randomUUID(),
    type: 'bbox' as const,
    label: t.label,
    color: t.color,
    points: t.pts,
    visible: true,
    locked: false,
    score: t.score,
    isAI: true,
  }))
}

const TASK_STATUS_LABEL: Record<string, string> = {
  pending: '待领取',
  assigned: '已分配',
  annotating: '标注中',
  submitted: '已提交',
  approved: '已通过',
}

const FALLBACK_MODELS: PrelabelModelInfo[] = [
  {
    id: 'demo_template',
    label: '演示模板（离线）',
    provider: 'demo',
    kind: 'supervised',
    status: 'available',
    status_message: '未连接后端时使用',
    loaded: false,
  },
]

function statusBadgeClass(status: PrelabelModelInfo['status']): string {
  switch (status) {
    case 'loaded':
      return 'text-emerald-400/90 border-emerald-500/30 bg-emerald-500/10'
    case 'available':
      return 'text-[#00d4ff]/90 border-[#00d4ff]/30 bg-[#00d4ff]/10'
    case 'config_required':
      return 'text-amber-400/90 border-amber-500/30 bg-amber-500/10'
    default:
      return 'text-white/35 border-white/15 bg-white/5'
  }
}

export default function ImageAnnotation() {
  const { taskId = '1001' } = useParams<{ taskId: string }>()
  const [searchParams] = useSearchParams()
  const pm = parseProjectMemberRole(searchParams.get('pm'))
  const creatorParam = searchParams.get('creator')
  const projectId = searchParams.get('projectId')
  const { user, token } = useAuthStore()
  const projectQueue = useProjectAnnotationQueue(projectId, taskId)

  const isProjectOwner = resolveIsProjectOwner(user, pm, creatorParam)
  const canAddEditLabels = canAddOrEditLabelClasses(user, pm)
  const canDeleteLabels = canDeleteLabelClasses(user, isProjectOwner)

  const [taskImageUrl, setTaskImageUrl] = useState<string | null>(null)
  const [taskImageName, setTaskImageName] = useState<string | null>(null)
  const [, setTaskLoading] = useState(false)
  const imageSources = taskImageUrl ? [taskImageUrl] : MOCK_IMAGES
  const frameCount = imageSources.length
  const [currentIdx, setCurrentIdx] = useState(0)
  const [hydrated, setHydrated] = useState(false)
  const prevIdxRef = useRef<number | null>(null)
  const workStartRef = useRef(Date.now())
  const syncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)

  const numericTaskId = Number(taskId)
  const useBackendTask =
    Boolean(token) &&
    Number.isFinite(numericTaskId) &&
    numericTaskId > 0 &&
    !isDemoTaskId(taskId)

  const [models, setModels] = useState<PrelabelModelInfo[]>(FALLBACK_MODELS)
  const [modelsLoading, setModelsLoading] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [modelLoading, setModelLoading] = useState(false)
  const [loadedModelId, setLoadedModelId] = useState<string | null>(null)
  const [loadStatusMessage, setLoadStatusMessage] = useState<string | null>(null)
  const [selectedModelId, setSelectedModelId] = useState<string>('demo_template')
  const [useBackendPrelabel, setUseBackendPrelabel] = useState(false)

  const [showExport, setShowExport] = useState(false)
  const { annotations2d, labelClasses } = useAnnotationStore()
  const { hasDraftForFrame } = useDraftManager(taskId)

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
    const payload = exportImageSessionPayload(taskId)
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

  const persistNow = useCallback((showSavedToast = false) => {
    const { annotations2d: a2, labelClasses: lc } = useAnnotationStore.getState()
    const savedAt = persistImageSessionSlice(taskId, currentIdx, currentIdx, a2, lc)
    setLastSavedAt(savedAt)
    if (showSavedToast) {
      const meta = useAnnotationStore.getState().autoSaveMeta
      useAnnotationStore.setState({
        autoSaveMeta: { ...meta, saveCount: meta.saveCount + 1 },
      })
    }
    if (useBackendTask) {
      if (syncTimerRef.current) clearTimeout(syncTimerRef.current)
      syncTimerRef.current = setTimeout(() => {
        void syncToServer()
      }, 800)
    }
  }, [taskId, currentIdx, useBackendTask, syncToServer])

  const handleSubmit = useCallback(async () => {
    persistNow(true)
    if (!useBackendTask) {
      message.success({ content: '标注已提交', duration: 2 })
      return
    }
    const payload = exportImageSessionPayload(taskId)
    if (!payload) {
      message.warning('暂无标注内容可提交')
      return
    }
    try {
      const workTime = Math.round((Date.now() - workStartRef.current) / 1000)
      const { data } = await taskApi.submitImageAnnotation(numericTaskId, {
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
    workStartRef.current = Date.now()
  }, [taskId])

  useAnnotationHotkeys({ onSave: () => persistNow(true) })

  useEffect(() => {
    useAnnotationStore.getState().setCurrentTask(taskId, currentIdx)
  }, [taskId, currentIdx])

  useEffect(() => {
    const id = Number(taskId)
    if (!token || !Number.isFinite(id) || id <= 0 || isDemoTaskId(taskId)) {
      setTaskImageUrl(null)
      setTaskImageName(null)
      return
    }
    let cancelled = false
    setTaskLoading(true)
    taskApi
      .getById(id)
      .then(({ data }) => {
        if (cancelled) return
        if (data.data_url) {
          setTaskImageUrl(data.data_url)
          setTaskImageName(data.filename ?? `task_${id}`)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setTaskImageUrl(null)
        }
      })
      .finally(() => {
        if (!cancelled) setTaskLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [taskId, token])

  const refreshModels = useCallback(async () => {
    if (!token) {
      setModels(FALLBACK_MODELS)
      setUseBackendPrelabel(false)
      return
    }
    setModelsLoading(true)
    try {
      const { data } = await prelabelApi.getTaskStatus(taskId)
      const list = data.models?.length ? data.models : FALLBACK_MODELS
      setModels(list)
      setUseBackendPrelabel(true)
      setSelectedModelId(prev => {
        if (list.some(m => m.id === prev)) return prev
        return list.find(m => canLoadPrelabelModel(m))?.id ?? prev
      })
      if (data.loaded_model?.in_memory) {
        setLoadedModelId(data.loaded_model.model_id)
        setLoadStatusMessage(data.loaded_model.status_message)
        setSelectedModelId(data.loaded_model.model_id)
      }
    } catch {
      try {
        const { data } = await prelabelApi.listModels()
        setModels(data.models?.length ? data.models : FALLBACK_MODELS)
        setUseBackendPrelabel(true)
      } catch {
        setModels(FALLBACK_MODELS)
        setUseBackendPrelabel(false)
      }
    } finally {
      setModelsLoading(false)
    }
  }, [taskId, token])

  useEffect(() => {
    refreshModels()
  }, [refreshModels])

  const selectedModel = models.find(m => m.id === selectedModelId)
  const loadedModel = models.find(m => m.id === loadedModelId)

  useLayoutEffect(() => {
    const s = readImageSession(taskId)
    if (!s) {
      setHydrated(true)
      prevIdxRef.current = 0
      return
    }
    const idx = Math.min(Math.max(0, s.currentIdx), frameCount - 1)
    setCurrentIdx(idx)
    const anns = s.frames[String(idx)] ?? []
    if (s.labelClasses?.length) {
      useAnnotationStore.setState({
        labelClasses: s.labelClasses,
        activeLabel: s.labelClasses[0]?.name ?? 'car',
        annotations2d: JSON.parse(JSON.stringify(anns)) as Annotation2D[],
        selectedIds2d: [],
        past: [],
        future: [],
      })
    } else {
      useAnnotationStore.setState({
        annotations2d: JSON.parse(JSON.stringify(anns)) as Annotation2D[],
        selectedIds2d: [],
        past: [],
        future: [],
      })
    }
    prevIdxRef.current = idx
    setHydrated(true)
    setLastSavedAt(s.savedAt ?? null)
    syncSessionDraftsToStore(taskId)
  }, [taskId, frameCount])

  useEffect(() => {
    if (!hydrated) return
    const prev = prevIdxRef.current
    if (prev !== null && prev !== currentIdx) {
      const { annotations2d: a2, labelClasses: lc } = useAnnotationStore.getState()
      persistImageSessionSlice(taskId, prev, prev, a2, lc)
      applyFrameToStore(currentIdx, taskId)
      setLastSavedAt(new Date().toISOString())
      syncSessionDraftsToStore(taskId)
    }
    prevIdxRef.current = currentIdx
  }, [currentIdx, taskId, hydrated])

  useEffect(() => {
    if (!hydrated) return
    const t = window.setTimeout(() => {
      persistNow()
    }, 500)
    return () => window.clearTimeout(t)
  }, [annotations2d, labelClasses, currentIdx, taskId, hydrated, persistNow])

  useEffect(() => {
    if (!hydrated) return
    const id = window.setInterval(persistNow, 12_000)
    return () => window.clearInterval(id)
  }, [hydrated, persistNow])

  const currentImage = imageSources[currentIdx % imageSources.length]
  const imageName =
    taskImageName ?? `frame_${String(currentIdx + 1).padStart(4, '0')}.jpg`

  const goNext = () => {
    setCurrentIdx(i => Math.min(i + 1, imageSources.length - 1))
  }
  const goPrev = () => {
    setCurrentIdx(i => Math.max(i - 1, 0))
  }

  async function handleLoadModel() {
    const model = models.find(m => m.id === selectedModelId)
    if (!model) return
    if (!canLoadPrelabelModel(model)) {
      message.warning(model.status_message || '该模型当前不可用')
      return
    }

    setModelLoading(true)
    setLoadStatusMessage(null)
    try {
      if (useBackendPrelabel) {
        const { data } = await prelabelApi.loadModel(taskId, selectedModelId)
        setLoadedModelId(data.model_id)
        setLoadStatusMessage(data.status_message)
        await refreshModels()
        message.success({ content: data.status_message || '模型已加载', duration: 2.5 })
      } else {
        setLoadedModelId(selectedModelId)
        setLoadStatusMessage('离线演示模式')
        message.success({ content: '演示模型已就绪', duration: 2 })
      }
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '模型加载失败'
      message.error(detail)
      setLoadedModelId(null)
    } finally {
      setModelLoading(false)
    }
  }

  async function loadAI() {
    if (!loadedModelId) return
    setAiLoading(true)
    try {
      if (useBackendPrelabel) {
        const { data } = await prelabelApi.run(taskId, {
          model_id: loadedModelId,
          frame_index: currentIdx,
          image_url: currentImage,
        })
        useAnnotationStore.setState({
          annotations2d: data.annotations2d as Annotation2D[],
        })
        useAnnotationStore.getState().markDirty()
        const src =
          data.inference_source === 'demo'
            ? '演示'
            : data.inference_source === 'local'
              ? '本地'
              : data.inference_source === 'cloud'
                ? '云服务'
                : data.inference_source
        message.success({
          content: `${data.message || '预标注完成'}（${src}）· ${data.annotations2d.length} 框 · 置信 ${(data.confidence * 100).toFixed(0)}%`,
          duration: 3.5,
        })
      } else if (loadedModelId === 'demo_template') {
        const anns = offlineDemoAnnotations(currentIdx)
        useAnnotationStore.setState({ annotations2d: anns })
        useAnnotationStore.getState().markDirty()
        message.success({ content: `离线演示预标注 · ${anns.length} 个候选框`, duration: 2.5 })
      } else {
        message.warning('请登录并连接后端以使用真实预标注模型')
      }
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '预标注失败'
      message.error(detail)
    } finally {
      setAiLoading(false)
    }
  }

  const labeledFrames = useMemo(
    () => countLabeledFrames(taskId, frameCount, currentIdx, annotations2d),
    [taskId, frameCount, currentIdx, annotations2d],
  )

  const otherFrameDrafts = useMemo(
    () =>
      Array.from({ length: frameCount }, (_, i) => i).filter(
        i => i !== currentIdx && hasDraftForFrame(i),
      ).length,
    [frameCount, currentIdx, hasDraftForFrame],
  )

  const aiCount = annotations2d.filter(a => a.isAI).length
  const manualCount = annotations2d.filter(a => !a.isAI).length
  const canPrelabel = Boolean(loadedModelId) && !aiLoading && !modelLoading
  const selectDisabled = modelLoading || aiLoading || modelsLoading

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0f] text-white overflow-hidden select-none">
      <AnnotationTopBar
        taskName={
          taskImageName
            ? taskImageName
            : `Task #${taskId} — 2D 图像标注`
        }
        totalImages={frameCount}
        currentImage={currentIdx + 1}
        labeledFrames={labeledFrames}
        onPrev={goPrev}
        onNext={goNext}
        onExport={() => setShowExport(v => !v)}
        saveHint={lastSavedAt ? `已保存 ${new Date(lastSavedAt).toLocaleTimeString()}` : undefined}
        onManualSave={() => persistNow(true)}
        onSubmit={() => void handleSubmit()}
        projectTaskIndex={projectQueue.hasQueue ? projectQueue.taskIndex : undefined}
        projectTaskTotal={projectQueue.hasQueue ? projectQueue.taskTotal : undefined}
        onPrevTask={projectQueue.hasQueue ? projectQueue.goPrevTask : undefined}
        onNextTask={projectQueue.hasQueue ? projectQueue.goNextTask : undefined}
        taskStatusLabel={
          projectQueue.currentTask?.status
            ? TASK_STATUS_LABEL[projectQueue.currentTask.status] ?? projectQueue.currentTask.status
            : undefined
        }
      />

      <div className="flex flex-1 overflow-hidden">
        <AnnotationToolbar />

        <div className="flex-1 relative overflow-hidden">
          <Canvas2D imageUrl={currentImage} />

          <div className="absolute top-3 left-1/2 -translate-x-1/2 flex flex-wrap items-center justify-center gap-2 z-20 pointer-events-auto max-w-[95vw]">
            <div className="flex flex-col gap-1 px-2 py-1.5 rounded-lg text-xs border border-white/10 bg-black/50 backdrop-blur-sm max-w-[min(100%,520px)]">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-white/40 whitespace-nowrap">预标注模型</span>
                <Select
                  size="small"
                  value={selectedModelId}
                  onChange={v => {
                    setSelectedModelId(v)
                    if (v !== loadedModelId) setLoadedModelId(null)
                    setLoadStatusMessage(null)
                  }}
                  disabled={selectDisabled}
                  loading={modelsLoading}
                  options={models.map(m => ({
                    value: m.id,
                    label: formatPrelabelOptionLabel(m),
                    disabled: !canLoadPrelabelModel(m) && m.status !== 'loaded',
                  }))}
                  className="min-w-[220px] flex-1 annotation-model-select"
                  popupClassName="annotation-model-dropdown"
                />
                <Button
                  size="small"
                  type="primary"
                  ghost
                  loading={modelLoading}
                  disabled={aiLoading || !selectedModel || !canLoadPrelabelModel(selectedModel)}
                  onClick={handleLoadModel}
                >
                  加载模型
                </Button>
              </div>
              {selectedModel && (
                <p className="text-[10px] text-white/35 leading-snug m-0 pl-0.5">
                  {selectedModel.description || selectedModel.status_message}
                </p>
              )}
            </div>

            <button
              type="button"
              onClick={loadAI}
              disabled={!canPrelabel}
              title={!loadedModelId ? '请先加载可用模型' : undefined}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border backdrop-blur-sm transition-all active:scale-95
                ${!canPrelabel
                  ? 'bg-black/40 border-white/10 text-white/25 cursor-not-allowed'
                  : aiLoading
                    ? 'bg-black/40 border-[#00d4ff]/15 text-[#00d4ff]/40 cursor-not-allowed'
                    : 'bg-black/50 border-[#00d4ff]/30 text-[#00d4ff] hover:bg-[#00d4ff]/15'}`}
            >
              {aiLoading ? (
                <span className="w-3 h-3 border border-[#00d4ff]/30 border-t-[#00d4ff] rounded-full animate-spin" />
              ) : (
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
                  <path
                    d="M8 1l1.5 3 3.5.5-2.5 2.5.5 3.5L8 9l-3 1.5.5-3.5L3 4.5 6.5 4 8 1z"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
              {aiLoading ? 'AI 预标注中…' : 'AI 预标注'}
            </button>

            {loadedModel && (
              <Tooltip title={loadStatusMessage || loadedModel.status_message}>
                <span
                  className={`text-[10px] px-2 py-1 rounded-md border ${statusBadgeClass(loadedModel.status === 'loaded' ? 'loaded' : loadedModel.status)}`}
                >
                  {loadedModel.label}
                  {useBackendPrelabel ? ` · ${loadStatusMessage ?? '已加载'}` : ' · 离线'}
                </span>
              </Tooltip>
            )}

            {aiCount > 0 && (
              <div className="flex items-center gap-2 bg-black/50 backdrop-blur-sm border border-[#00d4ff]/20 text-[#00d4ff]/70 text-[10px] px-2.5 py-1.5 rounded-lg">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00d4ff] animate-pulse" />
                {aiCount} AI 候选 · {manualCount} 人工确认
              </div>
            )}

            {otherFrameDrafts > 0 && (
              <div className="flex items-center gap-1.5 bg-black/40 backdrop-blur-sm border border-[#f59e0b]/20 text-[#f59e0b]/60 text-[10px] px-2 py-1.5 rounded-lg">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3 h-3">
                  <path d="M2 2h8v8H2V2zM4 2v3h4V2M3.5 8h5" strokeLinecap="round" />
                </svg>
                其他帧有草稿
              </div>
            )}
          </div>

          {showExport && (
            <div className="absolute top-12 right-4 z-30">
              <ExportPanel
                taskId={taskId}
                imageName={imageName}
                imageWidth={1280}
                imageHeight={720}
                onClose={() => setShowExport(false)}
              />
            </div>
          )}
        </div>

        <RightPanel
          taskId={taskId}
          currentImageIndex={currentIdx}
          onDraftLoad={(draft) => setCurrentIdx(draft.imageIndex)}
          labelClassAcl={
            canAddEditLabels || canDeleteLabels
              ? { canAddEdit: canAddEditLabels, canDelete: canDeleteLabels }
              : undefined
          }
        />
      </div>
    </div>
  )
}