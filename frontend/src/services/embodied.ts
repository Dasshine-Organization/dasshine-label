import api from './api'
import type {
  ActionLabelDef,
  CameraStream,
  EmbodiedDemoAttribution,
  EmbodiedDemoEpisode,
  FrameAnnotation,
} from '../mocks/embodiedDemoData'

export type ActionSegment = {
  id: string
  startFrame: number
  endFrame: number
  actionId: string
  note?: string
}

export type GraspPose = {
  id: string
  frame: number
  position: { x: number; y: number; z: number }
  orientation: { roll: number; pitch: number; yaw: number }
  width: number
  label: string
}

export type TrajectoryPoint = {
  frame: number
  ee: { x: number; y: number; z: number; roll: number; pitch: number; yaw: number }
  gripper: number
}

export type PreferencePair = {
  id: string
  prompt: string
  chosen: string
  rejected: string
  winner: 'a' | 'b' | 'tie'
}

export type EmbodiedWorkspaceState = {
  task_id: number
  task_ref: string
  user_id: number
  action_labels: ActionLabelDef[]
  frame_actions: Record<number, FrameAnnotation>
  committed_frames: number[]
  instruction: string
  success: 'success' | 'fail' | 'unknown'
  segments: ActionSegment[]
  grasps: GraspPose[]
  trajectory: TrajectoryPoint[]
  preferences: PreferencePair[]
  updated_at?: string | null
}

type EpisodeDto = {
  case_id: string
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
  instruction?: string
  success?: 'success' | 'fail' | 'unknown'
  has_proprioception?: boolean
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
    instruction: dto.instruction || '',
    success: dto.success || 'unknown',
    hasProprioception: Boolean(dto.has_proprioception),
  }
}

function mapWorkspace(data: {
  task_id: number
  task_ref: string
  user_id: number
  action_labels: ActionLabelDef[]
  frame_actions: Record<string, { action_id: string; note?: string }>
  committed_frames: number[]
  instruction?: string
  success?: string
  segments?: Array<{
    id: string
    start_frame: number
    end_frame: number
    action_id: string
    note?: string
  }>
  grasps?: Array<{
    id: string
    frame: number
    position: { x: number; y: number; z: number }
    orientation: { roll: number; pitch: number; yaw: number }
    width: number
    label: string
  }>
  trajectory?: Array<{
    frame: number
    ee: { x: number; y: number; z: number; roll: number; pitch: number; yaw: number }
    gripper: number
  }>
  preferences?: Array<{
    id: string
    prompt: string
    chosen: string
    rejected: string
    winner: string
  }>
  updated_at?: string | null
}): EmbodiedWorkspaceState {
  const frameActions: Record<number, FrameAnnotation> = {}
  for (const [k, v] of Object.entries(data.frame_actions || {})) {
    frameActions[Number(k)] = { actionId: v.action_id, note: v.note }
  }
  const success = data.success
  return {
    task_id: data.task_id,
    task_ref: data.task_ref,
    user_id: data.user_id,
    action_labels: data.action_labels,
    frame_actions: frameActions,
    committed_frames: data.committed_frames,
    instruction: data.instruction || '',
    success: success === 'success' || success === 'fail' ? success : 'unknown',
    segments: (data.segments || []).map(s => ({
      id: s.id,
      startFrame: s.start_frame,
      endFrame: s.end_frame,
      actionId: s.action_id,
      note: s.note,
    })),
    grasps: (data.grasps || []).map(g => ({
      id: g.id,
      frame: g.frame,
      position: g.position,
      orientation: g.orientation,
      width: g.width,
      label: g.label,
    })),
    trajectory: (data.trajectory || []).map(t => ({
      frame: t.frame,
      ee: t.ee,
      gripper: t.gripper,
    })),
    preferences: (data.preferences || []).map(p => ({
      id: p.id,
      prompt: p.prompt || '',
      chosen: p.chosen || '',
      rejected: p.rejected || '',
      winner: p.winner === 'a' || p.winner === 'b' ? p.winner : 'tie',
    })),
    updated_at: data.updated_at,
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
    const { data } = await api.get(`/embodied/tasks/${taskRef}/workspace`)
    return mapWorkspace(data)
  },

  saveWorkspace: async (
    taskRef: string,
    payload: {
      action_labels: ActionLabelDef[]
      frame_actions: Record<number, FrameAnnotation>
      committed_frames: number[]
      instruction?: string
      success?: 'success' | 'fail' | 'unknown'
      segments?: ActionSegment[]
      grasps?: GraspPose[]
      trajectory?: TrajectoryPoint[]
      preferences?: PreferencePair[]
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
      instruction: payload.instruction,
      success: payload.success,
      segments: (payload.segments || []).map(s => ({
        id: s.id,
        start_frame: s.startFrame,
        end_frame: s.endFrame,
        action_id: s.actionId,
        note: s.note,
      })),
      grasps: payload.grasps,
      trajectory: payload.trajectory,
      preferences: payload.preferences,
    })
    return mapWorkspace(data)
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

  exportLerobotJsonl: (taskRef: string) =>
    api.post(
      `/embodied/tasks/${taskRef}/export`,
      { format: 'lerobot_jsonl' },
      { responseType: 'blob' },
    ),

  exportHdf5: (taskRef: string) =>
    api.post(`/embodied/tasks/${taskRef}/export`, { format: 'hdf5' }, { responseType: 'blob' }),

  prelabel: (taskRef: string, model: 'auto' | 'embodied_policy_demo' | 'embodied_policy_http' = 'auto') =>
    api.post(`/embodied/tasks/${taskRef}/prelabel`, { model }),

  submit: (taskRef: string, workTimeSec: number) =>
    api.post(`/embodied/tasks/${taskRef}/submit`, { work_time: workTimeSec }),
}
