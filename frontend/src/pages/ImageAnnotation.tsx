import { useParams, useSearchParams } from 'react-router-dom'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { message, Select, Button } from 'antd'
import { v4 as uuid } from 'uuid'
import useAnnotationStore, { Annotation2D } from '../store/annotationStore'
import { useAnnotationHotkeys } from '../hooks/useAnnotation'
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
  persistImageSessionSlice,
  readImageSession,
} from '../utils/imageAnnotationSession'

const MOCK_IMAGES = [
  'https://images.unsplash.com/photo-1545558014-8692077e9b5c?w=1280&q=80',
  'https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=1280&q=80',
  'https://images.unsplash.com/photo-1477959858617-67f85cf4f1df?w=1280&q=80',
  'https://images.unsplash.com/photo-1486325212027-8081e485255e?w=1280&q=80',
  'https://images.unsplash.com/photo-1498036882173-b41c28a8ba34?w=1280&q=80',
]

const PRELABEL_MODELS = [
  { id: 'yolov8_coco', label: 'YOLOv8 · COCO 检测' },
  { id: 'sam_vit_h', label: 'SAM · 无监督分割' },
  { id: 'clip_cluster', label: 'CLIP · 无监督聚类' },
  { id: 'detr_generic', label: 'DETR · 通用检测' },
] as const

function makeAIAnnotations(idx: number): Annotation2D[] {
  const templates = [
    [
      { label: 'car', color: '#00d4ff', pts: [{ x: 120, y: 200 }, { x: 360, y: 380 }], score: 0.94 },
      { label: 'person', color: '#7c3aed', pts: [{ x: 440, y: 120 }, { x: 510, y: 310 }], score: 0.88 },
      { label: 'car', color: '#00d4ff', pts: [{ x: 600, y: 210 }, { x: 820, y: 370 }], score: 0.91 },
    ],
    [
      { label: 'person', color: '#7c3aed', pts: [{ x: 80, y: 150 }, { x: 160, y: 350 }], score: 0.82 },
      { label: 'car', color: '#00d4ff', pts: [{ x: 300, y: 240 }, { x: 550, y: 400 }], score: 0.95 },
    ],
  ]
  return (templates[idx % templates.length] ?? []).map((t) => ({
    id: uuid(),
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

export default function ImageAnnotation() {
  const { taskId = '1001' } = useParams<{ taskId: string }>()
  const [searchParams] = useSearchParams()
  const pm = parseProjectMemberRole(searchParams.get('pm'))
  const creatorParam = searchParams.get('creator')
  const { user } = useAuthStore()

  const isProjectOwner = resolveIsProjectOwner(user, pm, creatorParam)
  const canAddEditLabels = canAddOrEditLabelClasses(user, pm)
  const canDeleteLabels = canDeleteLabelClasses(user, isProjectOwner)

  const frameCount = MOCK_IMAGES.length
  const [currentIdx, setCurrentIdx] = useState(0)
  const [hydrated, setHydrated] = useState(false)
  const prevIdxRef = useRef<number | null>(null)
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)

  const [aiLoading, setAiLoading] = useState(false)
  const [modelLoading, setModelLoading] = useState(false)
  const [loadedModelId, setLoadedModelId] = useState<string | null>(null)
  const [selectedModelId, setSelectedModelId] = useState<string>(PRELABEL_MODELS[0].id)

  const [showExport, setShowExport] = useState(false)
  const { annotations2d, labelClasses } = useAnnotationStore()

  const { annotations2d, saveDraft } = useAnnotationStore()

  // Hooks
  useAnnotationHotkeys()

  // 首次：从 localStorage 恢复会话（帧索引、标签集、当前帧标注）
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
  }, [taskId, frameCount])

  const persistNow = useCallback(() => {
    const { annotations2d: a2, labelClasses: lc } = useAnnotationStore.getState()
    persistImageSessionSlice(taskId, currentIdx, currentIdx, a2, lc)
    setLastSavedAt(new Date().toISOString())
  }, [taskId, currentIdx])

  // 切换图片：保存上一帧并从会话载入目标帧
  useEffect(() => {
    if (!hydrated) return
    const prev = prevIdxRef.current
    if (prev !== null && prev !== currentIdx) {
      const { annotations2d: a2, labelClasses: lc } = useAnnotationStore.getState()
      persistImageSessionSlice(taskId, prev, prev, a2, lc)
      applyFrameToStore(currentIdx, taskId)
      setLastSavedAt(new Date().toISOString())
    }
    prevIdxRef.current = currentIdx
  }, [currentIdx, taskId, hydrated])

  // 标注 / 标签变化：防抖写入当前帧
  useEffect(() => {
    if (!hydrated) return
    const t = window.setTimeout(() => {
      persistNow()
    }, 500)
    return () => window.clearTimeout(t)
  }, [annotations2d, labelClasses, currentIdx, taskId, hydrated, persistNow])

  // 定时备份
  useEffect(() => {
    if (!hydrated) return
    const id = window.setInterval(persistNow, 12_000)
    return () => window.clearInterval(id)
  }, [hydrated, persistNow])

  const currentImage = MOCK_IMAGES[currentIdx % MOCK_IMAGES.length]
  const imageName = `frame_${String(currentIdx + 1).padStart(4, '0')}.jpg`

  const goNext = () => {
    setCurrentIdx((i) => Math.min(i + 1, MOCK_IMAGES.length - 1))
  }
  const goPrev = () => {
    setCurrentIdx((i) => Math.max(i - 1, 0))
  }

  function handleLoadModel() {
    setModelLoading(true)
    window.setTimeout(() => {
      setLoadedModelId(selectedModelId)
      setModelLoading(false)
      message.success({ content: '模型已加载，可进行预标注', duration: 2 })
    }, 800)
  }

  function loadAI() {
    if (!loadedModelId) return
    setAiLoading(true)
    window.setTimeout(() => {
      const anns = makeAIAnnotations(currentIdx)
      useAnnotationStore.setState({ annotations2d: anns })
      useAnnotationStore.getState().markDirty()
      setAiLoading(false)
      message.success({ content: `AI 预标注完成（${PRELABEL_MODELS.find((m) => m.id === loadedModelId)?.label ?? loadedModelId}），生成 ${anns.length} 个候选框`, duration: 3 })
    }, 1100)
  }

  const aiCount = annotations2d.filter((a) => a.isAI).length
  const manualCount = annotations2d.filter((a) => !a.isAI).length
  const canPrelabel = Boolean(loadedModelId) && !aiLoading && !modelLoading

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0f] text-white overflow-hidden select-none">
      <AnnotationTopBar
        taskName={`Task #${taskId} — 2D 图像标注`}
        totalImages={MOCK_IMAGES.length}
        currentImage={currentIdx + 1}
        onPrev={goPrev}
        onNext={goNext}
        onExport={() => setShowExport((v) => !v)}
        saveHint={lastSavedAt ? `已保存 ${new Date(lastSavedAt).toLocaleTimeString()}` : undefined}
      />

      <div className="flex flex-1 overflow-hidden">
        <AnnotationToolbar />

        <div className="flex-1 relative overflow-hidden">
          <Canvas2D imageUrl={currentImage} />

          <div className="absolute top-3 left-1/2 -translate-x-1/2 flex flex-wrap items-center justify-center gap-2 z-20 pointer-events-auto max-w-[95vw]">
            <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-xs border border-white/10 bg-black/50 backdrop-blur-sm">
              <span className="text-white/40 whitespace-nowrap">预标注模型</span>
              <Select
                size="small"
                value={selectedModelId}
                onChange={(v) => {
                  setSelectedModelId(v)
                  setLoadedModelId(null)
                }}
                disabled={modelLoading || aiLoading}
                options={PRELABEL_MODELS.map((m) => ({ value: m.id, label: m.label }))}
                className="min-w-[200px] annotation-model-select"
                popupClassName="annotation-model-dropdown"
              />
              <Button
                size="small"
                type="primary"
                ghost
                loading={modelLoading}
                disabled={aiLoading}
                onClick={handleLoadModel}
              >
                加载模型
              </Button>
            </div>
            <button
              type="button"
              onClick={loadAI}
              disabled={!canPrelabel}
              title={!loadedModelId ? '请先加载预标注或无监督模型' : undefined}
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
            {loadedModelId && (
              <span className="text-[10px] text-emerald-400/90 bg-black/45 border border-emerald-500/25 px-2 py-1 rounded-md">
                已加载
              </span>
            )}
            {aiCount > 0 && (
              <div className="flex items-center gap-2 bg-black/50 backdrop-blur-sm border border-[#00d4ff]/20 text-[#00d4ff]/70 text-[10px] px-2.5 py-1.5 rounded-lg">
                <span className="w-1.5 h-1.5 rounded-full bg-[#00d4ff] animate-pulse" />
                {aiCount} AI 候选 · {manualCount} 人工确认
              </div>
            )}

            {/* Draft indicator per frame */}
            {MOCK_IMAGES.map((_, i) => i).filter(i => i !== currentIdx && hasDraftForFrame(i)).length > 0 && (
              <div className="flex items-center gap-1.5 bg-black/40 backdrop-blur-sm border border-[#f59e0b]/20 text-[#f59e0b]/60 text-[10px] px-2 py-1.5 rounded-lg">
                <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3 h-3">
                  <path d="M2 2h8v8H2V2zM4 2v3h4V2M3.5 8h5" strokeLinecap="round"/>
                </svg>
                其他帧有草稿
              </div>
            )}
          </div>

          {/* Export panel */}
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
