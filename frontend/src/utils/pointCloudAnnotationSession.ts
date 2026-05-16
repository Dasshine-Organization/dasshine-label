import useAnnotationStore, { Box3D, LabelClass } from '../store/annotationStore'

export const POINTCLOUD_SESSION_SCHEMA = 'dasshine.pointcloud3d.v1' as const

export interface PointCloudAnnotationSession {
  schema: typeof POINTCLOUD_SESSION_SCHEMA
  taskId: string
  boxes3d: Box3D[]
  labelClasses: LabelClass[]
  savedAt: string
}

export function pointCloudSessionStorageKey(taskId: string) {
  return `dasshine_pointcloud_session_${taskId}`
}

function draftKey(taskId: string, imageIndex: number) {
  return `${taskId}:${imageIndex}`
}

export function readPointCloudSession(taskId: string): PointCloudAnnotationSession | null {
  try {
    const raw = localStorage.getItem(pointCloudSessionStorageKey(taskId))
    if (!raw) return null
    const data = JSON.parse(raw) as Partial<PointCloudAnnotationSession>
    if (data.schema === POINTCLOUD_SESSION_SCHEMA && data.taskId === taskId && Array.isArray(data.boxes3d)) {
      return data as PointCloudAnnotationSession
    }
  } catch {
    /* ignore */
  }
  return null
}

export function writePointCloudSession(session: PointCloudAnnotationSession) {
  try {
    localStorage.setItem(pointCloudSessionStorageKey(session.taskId), JSON.stringify(session))
  } catch {
    /* quota */
  }
}

/** 从任意服务端草稿 JSON 解析为点云会话 */
export function parsePointCloudPayload(
  taskId: string,
  payload: Record<string, unknown> | null | undefined,
): PointCloudAnnotationSession | null {
  if (!payload || typeof payload !== 'object') return null

  const schema = payload.schema as string | undefined
  const boxes = payload.boxes3d
  if (schema === POINTCLOUD_SESSION_SCHEMA && Array.isArray(boxes)) {
    return {
      schema: POINTCLOUD_SESSION_SCHEMA,
      taskId: String(payload.taskId ?? taskId),
      boxes3d: JSON.parse(JSON.stringify(boxes)) as Box3D[],
      labelClasses: Array.isArray(payload.labelClasses)
        ? (JSON.parse(JSON.stringify(payload.labelClasses)) as LabelClass[])
        : [],
      savedAt: typeof payload.savedAt === 'string' ? payload.savedAt : new Date().toISOString(),
    }
  }

  if (Array.isArray(boxes) && boxes.length >= 0) {
    return {
      schema: POINTCLOUD_SESSION_SCHEMA,
      taskId,
      boxes3d: JSON.parse(JSON.stringify(boxes)) as Box3D[],
      labelClasses: Array.isArray(payload.labelClasses)
        ? (JSON.parse(JSON.stringify(payload.labelClasses)) as LabelClass[])
        : [],
      savedAt: typeof payload.savedAt === 'string' ? payload.savedAt : new Date().toISOString(),
    }
  }

  return null
}

export function syncPointCloudDraftToStore(taskId: string, savedAt: string, boxes3d: Box3D[]) {
  const key = draftKey(taskId, 0)
  const store = useAnnotationStore.getState()
  useAnnotationStore.setState({
    drafts: {
      ...store.drafts,
      [key]: {
        taskId,
        imageIndex: 0,
        annotations2d: [],
        boxes3d: JSON.parse(JSON.stringify(boxes3d)) as Box3D[],
        savedAt,
        isSubmitted: false,
      },
    },
    currentTaskId: taskId,
    currentImageIndex: 0,
  })
}

export function applyPointCloudSessionToStore(session: PointCloudAnnotationSession) {
  const meta = useAnnotationStore.getState().autoSaveMeta
  useAnnotationStore.setState({
    boxes3d: JSON.parse(JSON.stringify(session.boxes3d)) as Box3D[],
    selectedIds3d: [],
    past: [],
    future: [],
    ...(session.labelClasses?.length
      ? {
          labelClasses: JSON.parse(JSON.stringify(session.labelClasses)) as LabelClass[],
          activeLabel: session.labelClasses[0]?.name ?? 'car',
        }
      : {}),
    autoSaveMeta: {
      ...meta,
      isDirty: false,
      lastSavedAt: session.savedAt,
      error: null,
    },
  })
  syncPointCloudDraftToStore(session.taskId, session.savedAt, session.boxes3d)
}

export function persistPointCloudSession(
  taskId: string,
  boxes3d: Box3D[],
  labelClasses: LabelClass[],
): string {
  const savedAt = new Date().toISOString()
  const session: PointCloudAnnotationSession = {
    schema: POINTCLOUD_SESSION_SCHEMA,
    taskId,
    boxes3d: JSON.parse(JSON.stringify(boxes3d)) as Box3D[],
    labelClasses: JSON.parse(JSON.stringify(labelClasses)) as LabelClass[],
    savedAt,
  }
  writePointCloudSession(session)
  syncPointCloudDraftToStore(taskId, savedAt, session.boxes3d)
  const meta = useAnnotationStore.getState().autoSaveMeta
  useAnnotationStore.setState({
    autoSaveMeta: { ...meta, isDirty: false, lastSavedAt: savedAt, error: null },
  })
  return savedAt
}

export function exportPointCloudSessionPayload(taskId: string): PointCloudAnnotationSession | null {
  const { boxes3d, labelClasses } = useAnnotationStore.getState()
  return {
    schema: POINTCLOUD_SESSION_SCHEMA,
    taskId,
    boxes3d: JSON.parse(JSON.stringify(boxes3d)) as Box3D[],
    labelClasses: JSON.parse(JSON.stringify(labelClasses)) as LabelClass[],
    savedAt: new Date().toISOString(),
  }
}

export function countPointCloudLabeled(boxes3d: Box3D[]): number {
  return boxes3d.length > 0 ? 1 : 0
}

/** 合并本地与服务端草稿，优先较新的 savedAt；服务端有框时优先保证框不丢 */
export function mergePointCloudSessions(
  local: PointCloudAnnotationSession | null,
  remote: PointCloudAnnotationSession | null,
  remoteUpdatedAt?: string | null,
): PointCloudAnnotationSession | null {
  if (!local && !remote) return null
  if (!local) return remote
  if (!remote) return local

  const localTs = Date.parse(local.savedAt) || 0
  const remoteTs = Date.parse(remote.savedAt) || Date.parse(remoteUpdatedAt ?? '') || 0

  if (remote.boxes3d.length > 0 && local.boxes3d.length === 0) return remote
  if (local.boxes3d.length > 0 && remote.boxes3d.length === 0) return local
  return remoteTs >= localTs ? remote : local
}
