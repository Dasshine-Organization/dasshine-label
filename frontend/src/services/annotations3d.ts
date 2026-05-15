import axios from 'axios'
import type { 
  Cuboid3D, 
  Point3D, 
  Annotation3DStats 
} from '../types/annotation3d'

export interface Cuboid3DCreate {
  position: { x: number; y: number; z: number }
  size: { width: number; height: number; depth: number }
  rotation?: { roll: number; pitch: number; yaw: number }
  label: string
  color?: string
  confidence?: number
}

export interface Point3DCreate {
  position: { x: number; y: number; z: number }
  label: string
  color?: string
  visibility?: 'visible' | 'occluded' | 'hidden'
}

export interface Annotation3DResponse {
  id: string
  task_id: number
  data_id: string
  annotation_type: string
  data: any
  frame_id?: number
  track_id?: string
  created_by: number
  created_at: string
  updated_at: string
}

export const annotations3DApi = {
  // 创建3D边界框
  createCuboid: async (
    taskId: number,
    dataId: string,
    cuboid: Cuboid3DCreate,
    frameId?: number,
    trackId?: string
  ): Promise<Annotation3DResponse> => {
    const response = await axios.post('/annotations/3d/cuboid', cuboid, {
      params: { task_id: taskId, data_id: dataId, frame_id: frameId, track_id: trackId }
    })
    return response.data
  },

  // 创建3D关键点
  createPoint: async (
    taskId: number,
    dataId: string,
    point: Point3DCreate,
    frameId?: number
  ): Promise<Annotation3DResponse> => {
    const response = await axios.post('/annotations/3d/point', point, {
      params: { task_id: taskId, data_id: dataId, frame_id: frameId }
    })
    return response.data
  },

  // 获取任务的所有3D标注
  getTaskAnnotations: async (
    taskId: number,
    params?: { data_id?: string; frame_id?: number; annotation_type?: string }
  ): Promise<Annotation3DResponse[]> => {
    const response = await axios.get(`/annotations/3d/task/${taskId}`, { params })
    return response.data
  },

  // 更新3D标注
  updateAnnotation: async (
    annotationId: string,
    updates: Partial<Cuboid3D | Point3D>
  ): Promise<Annotation3DResponse> => {
    const response = await axios.put(`/annotations/3d/${annotationId}`, updates)
    return response.data
  },

  // 删除3D标注
  deleteAnnotation: async (annotationId: string): Promise<void> => {
    await axios.delete(`/annotations/3d/${annotationId}`)
  },

  // 批量创建3D标注
  batchCreate: async (data: {
    task_id: number
    data_id: string
    annotations: { annotation_type: string; data: any; frame_id?: number; track_id?: string }[]
  }): Promise<Annotation3DResponse[]> => {
    const response = await axios.post('/annotations/3d/batch', data)
    return response.data
  },

  // 获取3D标注统计
  getStats: async (taskId: number): Promise<Annotation3DStats> => {
    const response = await axios.get(`/annotations/3d/task/${taskId}/stats`)
    return response.data
  },

  // 导出3D标注
  exportAnnotations: async (
    taskId: number,
    format: 'kitti' | 'json' | 'csv',
    includeMetadata: boolean = true
  ): Promise<{ format: string; content: string; filename: string }> => {
    const response = await axios.post(`/annotations/3d/task/${taskId}/export`, {
      format,
      include_metadata: includeMetadata
    })
    return response.data
  },
}
