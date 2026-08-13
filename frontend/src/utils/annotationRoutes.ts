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
export const DEMO_TASK_IDS = new Set([
  '1001', '1002', '1003', '1004', '1005', '1006',
  '2001', '2002', 'demo',
  '3001', '3002', '3003',
])

export function isDemoTaskId(taskId: string | number): boolean {
  return DEMO_TASK_IDS.has(String(taskId))
}

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
  // 有真实项目 ID 时进入该项目任务列表（不再跳演示任务）
  if (project.id != null) {
    return `/projects/${project.id}/tasks`
  }

  // 无真实项目 ID 时：优先回类别项目列表，避免误进演示 task
  if (project.category) {
    return getCategoryProjectsPath(project.category)
  }
  return '/projects'
}

/** 标注工作台返回列表时使用的入口（按类别收窄项目/任务） */
export function getCategoryProjectsPath(category?: string | null): string {
  if (!category) return '/projects'
  return `/projects?category=${encodeURIComponent(category)}`
}

export function getCategoryTasksPath(category?: string | null): string {
  if (!category) return '/tasks'
  return `/tasks?category=${encodeURIComponent(category)}`
}

/** 标注页返回：有 projectId 回项目任务列表，否则回类别项目列表 */
export function getAnnotateBackHref(opts: {
  projectId?: string | number | null
  category?: string | null
}): string {
  const pid = opts.projectId != null && String(opts.projectId).trim() !== ''
    ? Number(opts.projectId)
    : NaN
  if (Number.isFinite(pid) && pid > 0) {
    return `/projects/${pid}/tasks`
  }
  return getCategoryProjectsPath(opts.category)
}
