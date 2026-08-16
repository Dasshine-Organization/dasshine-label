/**
 * 具身标注示例 — 前端 mock
 * - Mars 案例：Wikimedia / NASA InSight（单源多裁剪模拟多视角）
 * - ALOHA 案例：Hugging Face LeRobot `aloha_static_coffee` episode 0（四路 **独立** 相机 MP4，同一演示片段）
 */

export type CameraStream = {
  id: string
  label: string
  src: string
  /** 首选失败时自动切换（如境内镜像） */
  fallbackSrc?: string
  objectPosition?: string
  scale?: number
}

export type EmbodiedDemoAttribution = {
  title: string
  detailUrl: string
  note: string
}

export interface EmbodiedDemoEpisode {
  caseId: string
  projectName: string
  clipDurationSec: number
  fps: number
  totalFrames: number
  streams: CameraStream[]
  attribution: EmbodiedDemoAttribution
  instruction?: string
  success?: 'success' | 'fail' | 'unknown'
  hasProprioception?: boolean
}

/** 动作标签定义（可增删改；帧上存 id） */
export type ActionLabelDef = { id: string; label: string }

export const DEFAULT_ACTION_LABELS: ActionLabelDef[] = [
  { id: 'idle', label: '待机' },
  { id: 'reach', label: '伸手接近' },
  { id: 'align', label: '对准目标' },
  { id: 'grasp', label: '闭合抓取' },
  { id: 'lift', label: '抬升' },
  { id: 'transport', label: '移运' },
  { id: 'place', label: '放置释放' },
  { id: 'retract', label: '回原点' },
]

export type FrameAnnotation = { actionId: string; note?: string }

const MARS_ARM_DEMO_WEBM =
  'https://upload.wikimedia.org/wikipedia/commons/b/bb/PIA24664-MarsInSightLander-CleaningSolarPanel-20210522.webm'

/** 主站；部分网络下 resolve 较慢，可为每路配置 fallbackSrc */
const ALOHA_CHUNK0 =
  'https://huggingface.co/datasets/lerobot/aloha_static_coffee/resolve/main/videos/chunk-000'
const ALOHA_CHUNK0_MIRROR =
  'https://hf-mirror.com/datasets/lerobot/aloha_static_coffee/resolve/main/videos/chunk-000'

export function getEmbodiedDemoEpisode(): EmbodiedDemoEpisode {
  const clipDurationSec = 2
  const fps = 12
  const totalFrames = Math.round(clipDurationSec * fps)

  return {
    caseId: 'mars',
    projectName: '具身示例 · InSight 机械臂（单源多裁剪）',
    clipDurationSec,
    fps,
    totalFrames,
    streams: [
      { id: 'cam_main', label: '主视角', src: MARS_ARM_DEMO_WEBM, objectPosition: '50% 52%' },
      { id: 'cam_arm', label: '机械臂区域', src: MARS_ARM_DEMO_WEBM, objectPosition: '58% 62%', scale: 1.45 },
      { id: 'cam_panel', label: '太阳能板', src: MARS_ARM_DEMO_WEBM, objectPosition: '42% 38%', scale: 1.25 },
      { id: 'cam_left', label: '左侧取景', src: MARS_ARM_DEMO_WEBM, objectPosition: '28% 55%', scale: 1.2 },
      { id: 'cam_top', label: '偏俯视', src: MARS_ARM_DEMO_WEBM, objectPosition: '50% 35%', scale: 1.15 },
      { id: 'cam_coarse', label: '远景', src: MARS_ARM_DEMO_WEBM, objectPosition: '50% 50%', scale: 1.0 },
      { id: 'cam_far_left', label: '极左带', src: MARS_ARM_DEMO_WEBM, objectPosition: '18% 48%', scale: 1.12 },
      { id: 'cam_far_right', label: '极右带', src: MARS_ARM_DEMO_WEBM, objectPosition: '82% 52%', scale: 1.12 },
    ],
    attribution: {
      title: 'PIA24664 — InSight lander cleaning solar panel with sand (2021-05-22)',
      detailUrl:
        'https://commons.wikimedia.org/wiki/File:PIA24664-MarsInSightLander-CleaningSolarPanel-20210522.webm',
      note: 'NASA / JPL-Caltech · 公有领域 · 本页仅截取前 2s 作标注演示',
    },
  }
}

export function getAlohaMultiCamEpisode(): EmbodiedDemoEpisode {
  const clipDurationSec = 2
  const fps = 12
  const totalFrames = Math.round(clipDurationSec * fps)

  return {
    caseId: 'aloha',
    projectName: '多视角案例 · ALOHA 制咖啡（LeRobot 四路真实相机）',
    clipDurationSec,
    fps,
    totalFrames,
    streams: [
      {
        id: 'cam_high',
        label: '高位全局',
        src: `${ALOHA_CHUNK0}/observation.images.cam_high/episode_000000.mp4`,
        fallbackSrc: `${ALOHA_CHUNK0_MIRROR}/observation.images.cam_high/episode_000000.mp4`,
      },
      {
        id: 'cam_low',
        label: '低位全局',
        src: `${ALOHA_CHUNK0}/observation.images.cam_low/episode_000000.mp4`,
        fallbackSrc: `${ALOHA_CHUNK0_MIRROR}/observation.images.cam_low/episode_000000.mp4`,
      },
      {
        id: 'cam_left_wrist',
        label: '左腕第一视角',
        src: `${ALOHA_CHUNK0}/observation.images.cam_left_wrist/episode_000000.mp4`,
        fallbackSrc: `${ALOHA_CHUNK0_MIRROR}/observation.images.cam_left_wrist/episode_000000.mp4`,
      },
      {
        id: 'cam_right_wrist',
        label: '右腕第一视角',
        src: `${ALOHA_CHUNK0}/observation.images.cam_right_wrist/episode_000000.mp4`,
        fallbackSrc: `${ALOHA_CHUNK0_MIRROR}/observation.images.cam_right_wrist/episode_000000.mp4`,
      },
    ],
    attribution: {
      title: 'lerobot/aloha_static_coffee — episode 000000',
      detailUrl: 'https://huggingface.co/datasets/lerobot/aloha_static_coffee',
      note:
        '四路为不同 MP4（同一 episode）。主站 huggingface.co；失败时将自动尝试 hf-mirror.com。编码多为 AV1，建议 Chrome；仍无法播放请在 embodiedDemoData.ts 替换为 H.264 地址。',
    },
  }
}

export function getEpisodeForTaskId(taskId: string): EmbodiedDemoEpisode {
  if (taskId === '2002' || taskId === 'embodied-aloha') return getAlohaMultiCamEpisode()
  return getEmbodiedDemoEpisode()
}

export const JOINT_NAMES = [
  'base_yaw',
  'shoulder_pitch',
  'elbow_pitch',
  'wrist_pitch',
  'wrist_roll',
  'gripper',
] as const

const EMBODIED_IDS = new Set(['2001', '2002', 'demo', 'embodied-demo', 'embodied-aloha'])

export function isEmbodiedTaskId(taskId: string): boolean {
  if (!taskId) return false
  if (EMBODIED_IDS.has(taskId)) return true
  if (taskId.startsWith('embodied-')) return true
  return false
}

function round(x: number, d: number): number {
  const p = 10 ** d
  return Math.round(x * p) / p
}

export function frameToTimeSec(frame: number, episode: EmbodiedDemoEpisode): number {
  const { totalFrames, clipDurationSec } = episode
  if (totalFrames <= 1) return 0
  const clamped = Math.max(0, Math.min(totalFrames - 1, frame))
  return (clamped / (totalFrames - 1)) * clipDurationSec
}

/** 由连续播放的 currentTime 反推帧索引 */
export function timeSecToFrame(timeSec: number, episode: EmbodiedDemoEpisode): number {
  const { totalFrames, clipDurationSec } = episode
  if (totalFrames <= 1) return 0
  const t = Math.max(0, Math.min(clipDurationSec, timeSec))
  const raw = Math.round((t / clipDurationSec) * (totalFrames - 1))
  return Math.max(0, Math.min(totalFrames - 1, raw))
}

export function jointStatesForFrame(
  frame: number,
  totalFrames: number,
): { name: string; position_rad: number; torque_nm: number }[] {
  const tf = Math.max(1, totalFrames)
  const f = ((frame % tf) + tf) % tf
  const t = f * 0.12
  return JOINT_NAMES.map((name, j) => {
    const position_rad = Math.sin(t + j * 0.55) * 1.1 + (j - 2.5) * 0.08
    const torque_nm = Math.cos(t * 1.3 + j * 0.7) * 3.2 + Math.sin(f * 0.21 + j) * 0.4
    return { name, position_rad: round(position_rad, 4), torque_nm: round(torque_nm, 3) }
  })
}

export function forceWrenchForFrame(frame: number, totalFrames: number) {
  const tf = Math.max(1, totalFrames)
  const f = ((frame % tf) + tf) % tf
  const t = f * 0.12
  return {
    fx: round(Math.sin(t) * 2.4, 4),
    fy: round(Math.cos(t * 1.1) * 1.6, 4),
    fz: round(-4.5 + Math.sin(t * 0.7) * 1.2, 4),
    tx: round(Math.cos(t * 0.9) * 0.35, 4),
    ty: round(Math.sin(t * 1.2) * 0.28, 4),
    tz: round(Math.cos(t * 0.5) * 0.15, 4),
  }
}

const TACTILE_PADS = ['pad_thumb', 'pad_index', 'pad_middle', 'pad_palm'] as const

export function tactileForFrame(frame: number, totalFrames: number) {
  const tf = Math.max(1, totalFrames)
  const f = ((frame % tf) + tf) % tf
  const t = f * 0.15
  return {
    pads: TACTILE_PADS.map((name, i) => ({
      name,
      pressure: round(Math.max(0, Math.sin(t + i * 0.8) * 0.55 + 0.35), 4),
    })),
  }
}

function labelText(labels: ActionLabelDef[], id: string): string {
  return labels.find(l => l.id === id)?.label ?? id
}

export function buildExportPayload(
  taskId: string,
  frameActions: Record<number, FrameAnnotation>,
  episode: EmbodiedDemoEpisode,
  labels: ActionLabelDef[],
  committedFrames: number[],
) {
  const { totalFrames, fps, clipDurationSec } = episode
  const committed = new Set(committedFrames)
  const frames = Array.from({ length: totalFrames }, (_, i) => {
    const ann = frameActions[i] ?? { actionId: 'idle' }
    return {
      index: i,
      timestamp_ms: Math.round((i / Math.max(1, totalFrames - 1)) * clipDurationSec * 1000),
      action: { id: ann.actionId, label: labelText(labels, ann.actionId) },
      note: ann.note ?? '',
      annotation_saved: committed.has(i),
      joints: jointStatesForFrame(i, totalFrames).map(j => ({
        name: j.name,
        position_rad: j.position_rad,
        position_deg: round((j.position_rad * 180) / Math.PI, 2),
        torque_nm: j.torque_nm,
      })),
    }
  })
  return {
    schema: 'dasshine.embodied_sequence.v3',
    task_id: taskId,
    case_id: episode.caseId,
    project: episode.projectName,
    clip_duration_sec: clipDurationSec,
    fps,
    exported_at: new Date().toISOString(),
    action_labels: labels,
    committed_frames: [...committed].sort((a, b) => a - b),
    streams: episode.streams.map(s => ({ id: s.id, label: s.label, src: s.src })),
    attribution: episode.attribution,
    frames,
  }
}
