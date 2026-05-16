/** 任务 1002：迷你城市路口点云（KITTI 坐标系结构，见 public/samples） */
export const TASK_POINT_CLOUD_SAMPLES: Record<string, string> = {
  '1002': '/samples/urban_intersection_mini.pcd',
  '1006': '/samples/urban_intersection_mini.pcd',
}

export function getTaskPointCloudUrl(taskId: string | number): string | undefined {
  return TASK_POINT_CLOUD_SAMPLES[String(taskId)]
}

import { isEmbodiedTaskId } from '../mocks/embodiedDemoData'

export type AnnotationWorkspaceMode = '2d' | '3d' | 'embodied'

/** 演示任务元数据（后续可改为 API 返回） */
export const DEMO_TASK_ROUTES: Record<string, { mode: AnnotationWorkspaceMode; label: string }> = {
  '1001': { mode: '2d', label: '自动驾驶场景标注' },
  '1002': { mode: '3d', label: '自动驾驶点云标注' },
  '1003': { mode: '2d', label: '行人检测' },
  '1004': { mode: '2d', label: '交通标志识别' },
  '1005': { mode: '2d', label: '自动驾驶场景标注' },
  '1006': { mode: '3d', label: '自动驾驶点云标注' },
  '2001': { mode: 'embodied', label: '具身 · InSight 多视角' },
  '2002': { mode: 'embodied', label: '具身 · ALOHA 四相机' },
  demo: { mode: 'embodied', label: '具身 · InSight 演示' },
}

export function resolveTaskMode(task: {
  type?: string
  category?: string
  project?: string
  taskId?: string | number
}): AnnotationWorkspaceMode {
  const id = task.taskId != null ? String(task.taskId) : ''
  const demo = DEMO_TASK_ROUTES[id]
  if (demo) return demo.mode
  if (isEmbodiedTaskId(id)) return 'embodied'

  if (task.category === 'embodied') return 'embodied'
  if (task.category === 'pointcloud_3d') return '3d'
  if (task.type && /具身|机器人|lerobot|aloha|insight/i.test(task.type)) return 'embodied'
  if (task.project && /具身|机器人|lerobot|aloha|insight/i.test(task.project)) return 'embodied'
  if (task.type && /3\s*d|点云|lidar/i.test(task.type)) return '3d'
  if (task.project && /点云|3d|lidar/i.test(task.project)) return '3d'
  return '2d'
}

export function getAnnotatePath(taskId: string | number, mode?: AnnotationWorkspaceMode): string {
  const id = String(taskId)
  const resolved = mode ?? resolveTaskMode({ taskId: id })
  if (resolved === 'embodied') return `/annotate-embodied/${id}`
  if (resolved === '3d') return `/annotate-3d/${id}`
  return `/annotate-image/${id}`
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
  return '/tasks'
}
