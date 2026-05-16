import api from './api'

export type PrelabelModelStatus =
  | 'available'
  | 'config_required'
  | 'unavailable'
  | 'loaded'

export type PrelabelModelProvider = 'local' | 'cloud' | 'http' | 'demo'

export interface PrelabelModelInfo {
  id: string
  label: string
  provider: PrelabelModelProvider
  kind: string
  description?: string
  status: PrelabelModelStatus
  status_message: string
  loaded: boolean
  config_keys?: string[]
}

export interface PrelabelLoadResult {
  success: boolean
  model_id: string
  status: string
  status_message: string
  load_time_ms?: number
  provider?: string
}

export interface PrelabelRunResult {
  success: boolean
  task_id: number
  model_id: string
  confidence: number
  annotations2d: Array<{
    id: string
    type: string
    label: string
    color: string
    points: { x: number; y: number }[]
    visible: boolean
    locked: boolean
    score?: number
    isAI?: boolean
  }>
  inference_source: string
  message: string
}

const STATUS_LABEL: Record<PrelabelModelStatus, string> = {
  available: '可用',
  config_required: '需配置',
  unavailable: '不可用',
  loaded: '已加载',
}

const PROVIDER_LABEL: Record<PrelabelModelProvider, string> = {
  local: '本地',
  cloud: '云服务',
  http: 'HTTP',
  demo: '演示',
}

export function formatPrelabelOptionLabel(m: PrelabelModelInfo): string {
  const st = STATUS_LABEL[m.status] ?? m.status
  const pv = PROVIDER_LABEL[m.provider] ?? m.provider
  return `${m.label} · ${pv} · ${st}`
}

export function canLoadPrelabelModel(m: PrelabelModelInfo): boolean {
  return m.status === 'available' || m.status === 'loaded'
}

function parseTaskId(taskId: string): number | null {
  const n = Number.parseInt(taskId, 10)
  return Number.isFinite(n) ? n : null
}

export const prelabelApi = {
  listModels: () =>
    api.get<{ models: PrelabelModelInfo[] }>('/prelabel-models'),

  getTaskStatus: (taskId: string) => {
    const id = parseTaskId(taskId)
    if (id == null) return Promise.reject(new Error('invalid task id'))
    return api.get<{
      task_id: number
      loaded_model: {
        model_id: string
        status: string
        status_message: string
        label: string
        in_memory: boolean
      } | null
      models: PrelabelModelInfo[]
    }>(`/tasks/${id}/prelabel/status`)
  },

  loadModel: (taskId: string, modelId: string) => {
    const id = parseTaskId(taskId)
    if (id == null) return Promise.reject(new Error('invalid task id'))
    return api.post<PrelabelLoadResult>(`/tasks/${id}/prelabel/load`, { model_id: modelId })
  },

  unloadModel: (taskId: string) => {
    const id = parseTaskId(taskId)
    if (id == null) return Promise.reject(new Error('invalid task id'))
    return api.post(`/tasks/${id}/prelabel/unload`)
  },

  run: (
    taskId: string,
    body: { model_id?: string; frame_index: number; image_url: string },
  ) => {
    const id = parseTaskId(taskId)
    if (id == null) return Promise.reject(new Error('invalid task id'))
    return api.post<PrelabelRunResult>(`/tasks/${id}/prelabel/run`, body)
  },
}
