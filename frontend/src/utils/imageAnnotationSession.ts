import useAnnotationStore, { Annotation2D, LabelClass } from '../store/annotationStore'

function draftKey(taskId: string, imageIndex: number) {
  return `${taskId}:${imageIndex}`
}

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
/** 将图像会话各帧同步到 annotationStore.drafts，供草稿面板展示 */
export function syncSessionDraftsToStore(taskId: string): string | null {
  const session = readImageSession(taskId)
  if (!session) return null

  const savedAt = session.savedAt
  const store = useAnnotationStore.getState()
  const nextDrafts = { ...store.drafts }

  for (const [frameKey, anns] of Object.entries(session.frames)) {
    const imageIndex = Number.parseInt(frameKey, 10)
    if (!Number.isFinite(imageIndex)) continue
    const key = draftKey(taskId, imageIndex)
    const prev = nextDrafts[key]
    nextDrafts[key] = {
      taskId,
      imageIndex,
      annotations2d: JSON.parse(JSON.stringify(anns)) as Annotation2D[],
      boxes3d: prev?.boxes3d ?? [],
      savedAt,
      isSubmitted: prev?.isSubmitted ?? false,
    }
  }

  const meta = useAnnotationStore.getState().autoSaveMeta
  useAnnotationStore.setState({
    drafts: nextDrafts,
    currentTaskId: taskId,
    currentImageIndex: session.currentIdx,
    autoSaveMeta: {
      ...meta,
      isDirty: false,
      lastSavedAt: savedAt,
      error: null,
    },
  })

  return savedAt
}

export function persistImageSessionSlice(
  taskId: string,
  frameIndex: number,
  currentIdxForMeta: number,
  annotations2d: Annotation2D[],
  labelClasses: LabelClass[]
): string {
  const prev = readImageSession(taskId)
  const frames = { ...(prev?.frames ?? {}) }
  frames[String(frameIndex)] = JSON.parse(JSON.stringify(annotations2d)) as Annotation2D[]
  const savedAt = new Date().toISOString()
  writeImageSession({
    v: 2,
    taskId,
    currentIdx: currentIdxForMeta,
    frames,
    labelClasses: JSON.parse(JSON.stringify(labelClasses)) as LabelClass[],
    savedAt,
  })
  syncSessionDraftsToStore(taskId)
  return savedAt
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

/** 统计已有标注框的帧数（当前帧以 liveAnnotations 为准） */
/** 导出当前本地会话，用于同步到服务端草稿 */
export function exportImageSessionPayload(taskId: string): ImageAnnotationSessionV2 | null {
  const session = readImageSession(taskId)
  if (!session) return null
  const { annotations2d, labelClasses } = useAnnotationStore.getState()
  const frames = { ...session.frames, [String(session.currentIdx)]: annotations2d }
  return {
    ...session,
    frames,
    labelClasses: JSON.parse(JSON.stringify(labelClasses)) as LabelClass[],
    savedAt: new Date().toISOString(),
  }
}

/** 从服务端草稿 JSON 解析为图像会话 */
export function parseImageSessionPayload(
  taskId: string,
  payload: Record<string, unknown> | null | undefined,
): ImageAnnotationSessionV2 | null {
  if (!payload || typeof payload !== 'object') return null

  if (
    payload.v === IMAGE_SESSION_VERSION &&
    payload.frames &&
    typeof payload.frames === 'object' &&
    typeof payload.currentIdx === 'number'
  ) {
    return {
      v: IMAGE_SESSION_VERSION,
      taskId: String(payload.taskId ?? taskId),
      currentIdx: payload.currentIdx as number,
      frames: JSON.parse(JSON.stringify(payload.frames)) as Record<string, Annotation2D[]>,
      labelClasses: Array.isArray(payload.labelClasses)
        ? (JSON.parse(JSON.stringify(payload.labelClasses)) as LabelClass[])
        : [],
      savedAt: typeof payload.savedAt === 'string' ? payload.savedAt : new Date().toISOString(),
    }
  }

  if (Array.isArray(payload.annotations2d)) {
    return {
      v: IMAGE_SESSION_VERSION,
      taskId,
      currentIdx: 0,
      frames: { '0': JSON.parse(JSON.stringify(payload.annotations2d)) as Annotation2D[] },
      labelClasses: Array.isArray(payload.labelClasses)
        ? (JSON.parse(JSON.stringify(payload.labelClasses)) as LabelClass[])
        : [],
      savedAt: typeof payload.savedAt === 'string' ? payload.savedAt : new Date().toISOString(),
    }
  }

  return null
}

function sessionAnnotationCount(session: ImageAnnotationSessionV2): number {
  return Object.values(session.frames).reduce(
    (n, anns) => n + (Array.isArray(anns) ? anns.length : 0),
    0,
  )
}

/** 合并本地与服务端图像会话：有标注内容优先，时间戳较新优先 */
export function mergeImageSessions(
  local: ImageAnnotationSessionV2 | null,
  remote: ImageAnnotationSessionV2 | null,
  remoteUpdatedAt?: string | null,
): ImageAnnotationSessionV2 | null {
  if (!local && !remote) return null
  if (!local) return remote
  if (!remote) return local

  const localCount = sessionAnnotationCount(local)
  const remoteCount = sessionAnnotationCount(remote)
  if (remoteCount > 0 && localCount === 0) return remote
  if (localCount > 0 && remoteCount === 0) return local

  const localTs = Date.parse(local.savedAt) || 0
  const remoteTs = Date.parse(remote.savedAt) || Date.parse(remoteUpdatedAt ?? '') || 0
  return remoteTs >= localTs ? remote : local
}

/** 将图像会话应用到 store 与 localStorage（无确认弹窗） */
export function applyImageSessionToStore(
  session: ImageAnnotationSessionV2,
  frameCount = 1,
): number {
  writeImageSession(session)
  const idx = Math.min(Math.max(0, session.currentIdx), Math.max(0, frameCount - 1))
  const anns = session.frames[String(idx)] ?? []
  useAnnotationStore.setState({
    annotations2d: JSON.parse(JSON.stringify(anns)) as Annotation2D[],
    selectedIds2d: [],
    past: [],
    future: [],
    ...(session.labelClasses?.length
      ? {
          labelClasses: JSON.parse(JSON.stringify(session.labelClasses)) as LabelClass[],
          activeLabel: session.labelClasses[0]?.name ?? 'car',
        }
      : {}),
  })
  syncSessionDraftsToStore(session.taskId)
  return idx
}

export function countLabeledFrames(
  taskId: string,
  totalFrames: number,
  currentFrameIndex: number,
  liveAnnotations?: Annotation2D[],
): number {
  const session = readImageSession(taskId)
  let count = 0
  for (let i = 0; i < totalFrames; i++) {
    const anns =
      i === currentFrameIndex && liveAnnotations
        ? liveAnnotations
        : session?.frames[String(i)]
    if (anns && anns.length > 0) count++
  }
  return count
}
