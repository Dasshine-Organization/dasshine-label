/** 产品信息架构：类别 Hub（侧栏 / Dashboard / Projects 共用） */
export type CategoryHub = {
  id: string
  label: string
  color: string
  projectsHref: string
  tasksHref: string
}

export const CATEGORY_HUBS: CategoryHub[] = [
  { id: 'image_2d', label: '图像 2D', color: '#00d4ff', projectsHref: '/projects?category=image_2d', tasksHref: '/tasks?category=image_2d' },
  { id: 'pointcloud_3d', label: '3D 点云', color: '#a78bfa', projectsHref: '/projects?category=pointcloud_3d', tasksHref: '/tasks?category=pointcloud_3d' },
  { id: 'nlp', label: '语料', color: '#ec4899', projectsHref: '/projects?category=nlp', tasksHref: '/tasks?category=nlp' },
  { id: 'audio', label: '语音', color: '#10b981', projectsHref: '/projects?category=audio', tasksHref: '/tasks?category=audio' },
  { id: 'video', label: '视频', color: '#f59e0b', projectsHref: '/projects?category=video', tasksHref: '/tasks?category=video' },
  { id: 'embodied', label: '具身', color: '#f97316', projectsHref: '/projects?category=embodied', tasksHref: '/tasks?category=embodied' },
  { id: 'ocr', label: 'OCR', color: '#06b6d4', projectsHref: '/projects?category=ocr', tasksHref: '/tasks?category=ocr' },
  { id: 'multimodal', label: '多模态', color: '#8b5cf6', projectsHref: '/projects?category=multimodal', tasksHref: '/tasks?category=multimodal' },
]

export const CATEGORY_HUB_BY_ID = Object.fromEntries(
  CATEGORY_HUBS.map(h => [h.id, h]),
) as Record<string, CategoryHub>
