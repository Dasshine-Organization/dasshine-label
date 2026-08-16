import api from './api'

export type TextSpan = { id: string; start: number; end: number; label: string; text: string }
export type AudioSegment = {
  id: string
  start_ms: number
  end_ms: number
  speaker: string
  text: string
}
export type VideoClip = {
  id: string
  start_sec: number
  end_sec: number
  label: string
  note?: string
}

export type OcrSpan = {
  id: string
  text: string
  label?: string
  bbox: number[] // xywh
}

export type ModalityPayload = {
  schema?: string
  modality: string
  ann_type: string
  spans?: Array<TextSpan | OcrSpan>
  classification_labels?: string[]
  sentiment?: string | null
  qa_pairs?: { question: string; answer: string }[]
  summary?: string
  translation?: string
  segments?: AudioSegment[]
  transcript?: string
  speakers?: string[]
  clips?: VideoClip[]
  caption?: string
  frame_notes?: Record<string, string>
  vqa?: { question: string; answer: string }
}

export type ModalityWorkspace = {
  task_id: number
  project_id: number
  project_name: string
  category?: string
  ann_type: string
  modality: 'text' | 'audio' | 'video' | 'multimodal' | 'ocr'
  content: {
    text?: string
    title?: string
    audio_url?: string
    video_url?: string
    image_url?: string
  }
  payload: ModalityPayload
  label_classes: { id: string; name: string; color: string }[]
  draft_updated_at?: string | null
}

export const DEMO_TEXT_CONTENT =
  '特斯拉公司今日在上海超级工厂宣布扩大产能。首席执行官马斯克表示，新款 Model Y 将在第四季度交付。'

export const DEMO_AUDIO_URL =
  'https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3'

export const DEMO_VIDEO_URL =
  'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4'

function parseTaskId(taskId: string): number | null {
  const n = Number.parseInt(taskId, 10)
  return Number.isFinite(n) ? n : null
}

export function offlineTextWorkspace(taskId: string, annType = 'ner'): ModalityWorkspace {
  return {
    task_id: Number.parseInt(taskId, 10) || 3001,
    project_id: 0,
    project_name: '语料标注（离线）',
    category: 'nlp',
    ann_type: annType,
    modality: 'text',
    content: { text: DEMO_TEXT_CONTENT, title: '演示文稿' },
    payload: {
      schema: 'dasshine.modality.v1',
      modality: 'text',
      ann_type: annType,
      spans: [],
      qa_pairs: [{ question: '', answer: '' }],
    },
    label_classes: [
      { id: 'PER', name: '人名', color: '#ec4899' },
      { id: 'ORG', name: '机构', color: '#00d4ff' },
      { id: 'LOC', name: '地点', color: '#10b981' },
    ],
  }
}

export function offlineAudioWorkspace(taskId: string): ModalityWorkspace {
  return {
    task_id: Number.parseInt(taskId, 10) || 3002,
    project_id: 0,
    project_name: '语音转写（离线）',
    category: 'audio',
    ann_type: 'asr',
    modality: 'audio',
    content: { audio_url: DEMO_AUDIO_URL, title: 'ASR 示例' },
    payload: {
      schema: 'dasshine.modality.v1',
      modality: 'audio',
      ann_type: 'asr',
      segments: [],
      transcript: '',
      speakers: ['说话人 A', '说话人 B'],
    },
    label_classes: [],
  }
}

export function offlineMultimodalWorkspace(taskId: string): ModalityWorkspace {
  return {
    task_id: Number.parseInt(taskId, 10) || 3001,
    project_id: 0,
    project_name: '多模态（离线）',
    category: 'multimodal',
    ann_type: 'image_caption',
    modality: 'multimodal',
    content: {
      image_url: 'https://images.unsplash.com/photo-1545558014-8692077e9b5c?w=960&q=80',
      title: 'Caption 演示',
    },
    payload: {
      schema: 'dasshine.modality.v1',
      modality: 'multimodal',
      ann_type: 'image_caption',
      caption: '',
      vqa: { question: '', answer: '' },
    },
    label_classes: [],
  }
}

export function offlineVideoWorkspace(taskId: string): ModalityWorkspace {
  return {
    task_id: Number.parseInt(taskId, 10) || 3003,
    project_id: 0,
    project_name: '视频标注（离线）',
    category: 'video',
    ann_type: 'video_action',
    modality: 'video',
    content: { video_url: DEMO_VIDEO_URL, title: '动作片段' },
    payload: {
      schema: 'dasshine.modality.v1',
      modality: 'video',
      ann_type: 'video_action',
      clips: [],
      caption: '',
    },
    label_classes: [],
  }
}

export const modalityApi = {
  getWorkspace: async (taskId: string): Promise<ModalityWorkspace> => {
    const id = parseTaskId(taskId)
    if (id == null) throw new Error('invalid task id')
    const { data } = await api.get<ModalityWorkspace>(`/tasks/${id}/modality/workspace`)
    return data
  },

  saveWorkspace: async (taskId: string, payload: ModalityPayload) => {
    const id = parseTaskId(taskId)
    if (id == null) throw new Error('invalid task id')
    return api.put(`/tasks/${id}/modality/workspace`, { payload })
  },

  submit: async (taskId: string, payload: ModalityPayload, workTimeSec = 0) => {
    const id = parseTaskId(taskId)
    if (id == null) throw new Error('invalid task id')
    return api.post(`/tasks/${id}/modality/submit`, { payload, work_time: workTimeSec })
  },
}
