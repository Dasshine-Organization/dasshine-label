/** 任务 1002：迷你城市路口点云（KITTI 坐标系结构，见 public/samples） */
export const TASK_POINT_CLOUD_SAMPLES: Record<string, string> = {
  '1002': '/samples/urban_intersection_mini.pcd',
  '1006': '/samples/urban_intersection_mini.pcd',
}

export function getTaskPointCloudUrl(taskId: string | number): string | undefined {
  return TASK_POINT_CLOUD_SAMPLES[String(taskId)]
}

import { isEmbodiedTaskId } from '../mocks/embodiedDemoData'

export type AnnotationWorkspaceMode =
  | '2d'
  | '3d'
  | 'embodied'
  | 'text'
  | 'audio'
  | 'video'
  | 'multimodal'

/** 演示任务元数据（后续可改为 API 返回） */
export const DEMO_TASK_ROUTES: Record<
  string,
  { mode: AnnotationWorkspaceMode; label: string; category?: string }
> = {
  '1001': { mode: '2d', label: '自动驾驶场景标注', category: 'image_2d' },
  '1002': { mode: '3d', label: '自动驾驶点云标注', category: 'pointcloud_3d' },
  '1003': { mode: '2d', label: '行人检测', category: 'image_2d' },
  '1004': { mode: '2d', label: '交通标志识别', category: 'image_2d' },
  '1005': { mode: '2d', label: '自动驾驶场景标注', category: 'image_2d' },
  '1006': { mode: '3d', label: '自动驾驶点云标注', category: 'pointcloud_3d' },
  '2001': { mode: 'embodied', label: '具身 · InSight 多视角', category: 'embodied' },
  '2002': { mode: 'embodied', label: '具身 · ALOHA 四相机', category: 'embodied' },
  demo: { mode: 'embodied', label: '具身 · InSight 演示', category: 'embodied' },
  '3001': { mode: 'text', label: '语料 · NER 演示', category: 'nlp' },
  '3002': { mode: 'audio', label: '语音 · ASR 演示', category: 'audio' },
  '3003': { mode: 'video', label: '视频 · 动作片段', category: 'video' },
}

const TEXT_CATEGORIES = new Set(['nlp', 'ocr'])
const AUDIO_CATEGORIES = new Set(['audio'])
const VIDEO_CATEGORIES = new Set(['video'])
const MULTIMODAL_CATEGORIES = new Set(['multimodal'])

export function resolveTaskMode(task: {
  type?: string
  category?: string
  ann_type?: string
  project?: string
  taskId?: string | number
}): AnnotationWorkspaceMode {
  const id = task.taskId != null ? String(task.taskId) : ''
  const demo = DEMO_TASK_ROUTES[id]
  if (demo) return demo.mode
  if (isEmbodiedTaskId(id)) return 'embodied'

  const cat = task.category?.toLowerCase()
  const ann = task.ann_type?.toLowerCase()

  if (cat === 'embodied' || task.category === 'embodied') return 'embodied'
  if (cat === 'pointcloud_3d') return '3d'
  if (TEXT_CATEGORIES.has(cat ?? '') || ann === 'ner' || ann === 'sentiment') return 'text'
  if (AUDIO_CATEGORIES.has(cat ?? '') || ann === 'asr' || ann === 'speaker_diarize') return 'audio'
  if (VIDEO_CATEGORIES.has(cat ?? '') || ann?.startsWith('video_')) return 'video'
  if (MULTIMODAL_CATEGORIES.has(cat ?? '') || ann === 'vqa' || ann === 'image_caption') return 'multimodal'

  if (task.type && /具身|机器人|lerobot|aloha|insight/i.test(task.type)) return 'embodied'
  if (task.project && /具身|机器人|lerobot|aloha|insight/i.test(task.project)) return 'embodied'
  if (task.type && /3\s*d|点云|lidar/i.test(task.type)) return '3d'
  if (task.project && /点云|3d|lidar/i.test(task.project)) return '3d'
  if (task.type && /语料|文本|ner|nlp|翻译|摘要/i.test(task.type)) return 'text'
  if (task.type && /语音|音频|asr|转写/i.test(task.type)) return 'audio'
  if (task.type && /视频|video/i.test(task.type)) return 'video'

  return '2d'
}

export function getAnnotatePath(taskId: string | number, mode?: AnnotationWorkspaceMode): string {
  const id = String(taskId)
  const resolved = mode ?? resolveTaskMode({ taskId: id })
  switch (resolved) {
    case 'embodied':
      return `/annotate-embodied/${id}`
    case '3d':
      return `/annotate-3d/${id}`
    case 'text':
      return `/annotate-text/${id}`
    case 'audio':
      return `/annotate-audio/${id}`
    case 'video':
      return `/annotate-video/${id}`
    case 'multimodal':
      return `/annotate-multimodal/${id}`
    default:
      return `/annotate-image/${id}`
  }
}

export function resolveAnnotatePathForTask(taskId: string | number): string {
  return getAnnotatePath(taskId)
}

export function resolveProjectAnnotatePath(project: {
  category?: string | null
  id?: number
}): string {
  if (project.category === 'embodied') {
    return getAnnotatePath('demo', 'embodied')
  }
  if (project.category === 'pointcloud_3d') {
    return getAnnotatePath(1002, '3d')
  }
  if (project.category === 'nlp' || project.category === 'ocr') {
    return getAnnotatePath(3001, 'text')
  }
  if (project.category === 'audio') {
    return getAnnotatePath(3002, 'audio')
  }
  if (project.category === 'video') {
    return getAnnotatePath(3003, 'video')
  }
  if (project.category === 'multimodal') {
    return getAnnotatePath(3001, 'multimodal')
  }
  return '/tasks'
}
