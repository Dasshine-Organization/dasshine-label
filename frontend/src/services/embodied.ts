import api from './api'
import type {
  ActionLabelDef,
  CameraStream,
  EmbodiedDemoAttribution,
  EmbodiedDemoEpisode,
  FrameAnnotation,
} from '../mocks/embodiedDemoData'

export type EmbodiedWorkspaceState = {
  task_id: number
  task_ref: string
  user_id: number
  action_labels: ActionLabelDef[]
  frame_actions: Record<number, FrameAnnotation>
  committed_frames: number[]
  updated_at?: string | null
}

type EpisodeDto = {
  case_id: 'mars' | 'aloha'
  project_name: string
  clip_duration_sec: number
  fps: number
  total_frames: number
  streams: Array<{
    id: string
    label: string
    src: string
    fallback_src?: string | null
    object_position?: string | null
    scale?: number | null
  }>
  attribution: { title: string; detail_url: string; note: string }
}

function mapEpisode(dto: EpisodeDto): EmbodiedDemoEpisode {
  const streams: CameraStream[] = dto.streams.map(s => ({
    id: s.id,
    label: s.label,
    src: s.src,
    fallbackSrc: s.fallback_src ?? undefined,
    objectPosition: s.object_position ?? undefined,
    scale: s.scale ?? undefined,
  }))
  const attribution: EmbodiedDemoAttribution = {
    title: dto.attribution.title,
    detailUrl: dto.attribution.detail_url,
    note: dto.attribution.note,
  }
  return {
    caseId: dto.case_id,
    projectName: dto.project_name,
    clipDurationSec: dto.clip_duration_sec,
    fps: dto.fps,
    totalFrames: dto.total_frames,
    streams,
    attribution,
  }
}

export function isNumericTaskRef(taskId: string): boolean {
  return /^\d+$/.test(taskId)
}

export const embodiedApi = {
  getEpisode: async (taskRef: string): Promise<EmbodiedDemoEpisode> => {
    const { data } = await api.get<EpisodeDto>(`/embodied/tasks/${taskRef}/episode`)
    return mapEpisode(data)
  },

  getWorkspace: async (taskRef: string): Promise<EmbodiedWorkspaceState> => {
    const { data } = await api.get<{
      task_id: number
      task_ref: string
      user_id: number
      action_labels: ActionLabelDef[]
      frame_actions: Record<string, { action_id: string; note?: string }>
      committed_frames: number[]
      updated_at?: string | null
    }>(`/embodied/tasks/${taskRef}/workspace`)
    const frameActions: Record<number, FrameAnnotation> = {}
    for (const [k, v] of Object.entries(data.frame_actions || {})) {
      frameActions[Number(k)] = { actionId: v.action_id, note: v.note }
    }
    return {
      task_id: data.task_id,
      task_ref: data.task_ref,
      user_id: data.user_id,
      action_labels: data.action_labels,
      frame_actions: frameActions,
      committed_frames: data.committed_frames,
      updated_at: data.updated_at,
    }
  },

  saveWorkspace: async (
    taskRef: string,
    payload: {
      action_labels: ActionLabelDef[]
      frame_actions: Record<number, FrameAnnotation>
      committed_frames: number[]
    },
  ): Promise<EmbodiedWorkspaceState> => {
    const frame_actions: Record<number, { action_id: string; note?: string }> = {}
    for (const [k, v] of Object.entries(payload.frame_actions)) {
      frame_actions[Number(k)] = { action_id: v.actionId, note: v.note }
    }
    const { data } = await api.put(`/embodied/tasks/${taskRef}/workspace`, {
      action_labels: payload.action_labels,
      frame_actions,
      committed_frames: payload.committed_frames,
    })
    const frameActions: Record<number, FrameAnnotation> = {}
    for (const [k, v] of Object.entries(data.frame_actions || {})) {
      frameActions[Number(k)] = { actionId: v.action_id, note: v.note }
    }
    return {
      task_id: data.task_id,
      task_ref: data.task_ref,
      user_id: data.user_id,
      action_labels: data.action_labels,
      frame_actions: frameActions,
      committed_frames: data.committed_frames,
      updated_at: data.updated_at,
    }
  },

  patchFrame: (
    taskRef: string,
    frameIndex: number,
    body: { action_id?: string; note?: string; commit?: boolean },
  ) => api.patch(`/embodied/tasks/${taskRef}/frames/${frameIndex}`, body),

  exportJson: (taskRef: string) =>
    api.post(`/embodied/tasks/${taskRef}/export`, { format: 'json' }, { responseType: 'blob' }),

  exportTorqueCsv: (taskRef: string) =>
    api.post(`/embodied/tasks/${taskRef}/export`, { format: 'torque_csv' }, { responseType: 'blob' }),

  submit: (taskRef: string, workTimeSec: number) =>
    api.post(`/embodied/tasks/${taskRef}/submit`, { work_time: workTimeSec }),
}
