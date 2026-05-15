import useAnnotationStore, { Annotation2D, LabelClass } from '../store/annotationStore'

export const IMAGE_SESSION_VERSION = 2 as const

export interface ImageAnnotationSessionV2 {
  v: typeof IMAGE_SESSION_VERSION
  taskId: string
  currentIdx: number
  frames: Record<string, Annotation2D[]>
  labelClasses: LabelClass[]
  savedAt: string
}

export function imageSessionStorageKey(taskId: string) {
  return `dasshine_image_session_${taskId}`
}

export function readImageSession(taskId: string): ImageAnnotationSessionV2 | null {
  try {
    const raw = localStorage.getItem(imageSessionStorageKey(taskId))
    if (!raw) return null
    const data = JSON.parse(raw) as Partial<ImageAnnotationSessionV2> & { annotations2d?: Annotation2D[] }
    if (data.v === 2 && data.taskId && data.frames && typeof data.currentIdx === 'number') {
      return data as ImageAnnotationSessionV2
    }
    if (data.taskId && Array.isArray(data.annotations2d)) {
      return {
        v: 2,
        taskId: data.taskId,
        currentIdx: 0,
        frames: { '0': data.annotations2d },
        labelClasses: [],
        savedAt: data.savedAt ?? new Date().toISOString(),
      }
    }
  } catch {
    /* ignore */
  }
  return null
}

export function writeImageSession(session: ImageAnnotationSessionV2) {
  try {
    localStorage.setItem(imageSessionStorageKey(session.taskId), JSON.stringify(session))
  } catch {
    /* quota */
  }
}

/** 将当前画布写入会话并持久化（保留其它帧缓存） */
export function persistImageSessionSlice(
  taskId: string,
  frameIndex: number,
  currentIdxForMeta: number,
  annotations2d: Annotation2D[],
  labelClasses: LabelClass[]
) {
  const prev = readImageSession(taskId)
  const frames = { ...(prev?.frames ?? {}) }
  frames[String(frameIndex)] = JSON.parse(JSON.stringify(annotations2d)) as Annotation2D[]
  writeImageSession({
    v: 2,
    taskId,
    currentIdx: currentIdxForMeta,
    frames,
    labelClasses: JSON.parse(JSON.stringify(labelClasses)) as LabelClass[],
    savedAt: new Date().toISOString(),
  })
}

/** 从会话读取某一帧到 store（清空选择/history） */
export function applyFrameToStore(frameIndex: number, taskId: string) {
  const s = readImageSession(taskId)
  const anns = s?.frames[String(frameIndex)] ?? []
  useAnnotationStore.setState({
    annotations2d: JSON.parse(JSON.stringify(anns)) as Annotation2D[],
    selectedIds2d: [],
    past: [],
    future: [],
  })
}
