import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'

// 创建 axios 实例
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
})

// 请求拦截器 - 添加 token
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const auth = localStorage.getItem('dasshine_auth')
    const token = auth ? JSON.parse(auth)?.state?.token : null
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器 - 处理错误
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Token 过期或无效
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// 认证相关 API
export const authApi = {
  // 注册
  register: (data: {
    username: string
    email: string
    password: string
    full_name?: string
  }) => api.post('/auth/register', data),

  // 登录
  login: (username: string, password: string) => {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)
    return api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
  },

  // 获取当前用户
  getMe: () => api.get('/auth/me'),

  // 刷新 token
  refresh: () => api.post('/auth/refresh'),
}

// 项目相关 API
export const projectApi = {
  // 获取项目列表
  getList: (params?: { skip?: number; limit?: number }) =>
    api.get('/projects', { params }),

  // 获取项目详情
  getById: (id: number) => api.get(`/projects/${id}`),

  // 创建项目
  create: (data: {
    name: string
    description?: string
    type: string
    annotation_schema: Record<string, any>
  }) => api.post('/projects', data),

  // 更新项目
  update: (id: number, data: Partial<{
    name: string
    description: string
    status: string
    annotation_schema: Record<string, any>
  }>) => api.put(`/projects/${id}`, data),

  // 删除项目
  delete: (id: number) => api.delete(`/projects/${id}`),

  // 添加项目成员
  addMember: (projectId: number, userId: number, role: string) =>
    api.post(`/projects/${projectId}/members`, { user_id: userId, role }),
}

// 任务相关 API
export const taskApi = {
  // 获取任务列表
  getList: (params?: {
    project_id?: number
    status?: string
    page?: number
    page_size?: number
  }) => api.get('/tasks', { params }),

  // 获取可领取的任务
  getAvailable: (params?: { project_id?: number; limit?: number }) =>
    api.get('/tasks/available', { params }),

  // 领取任务
  claim: (taskId: number) => api.post(`/tasks/${taskId}/claim`),

  // 开始任务
  start: (taskId: number) => api.post(`/tasks/${taskId}/start`),

  // 提交任务
  submit: (taskId: number, data: { result: Record<string, any>; work_time: number }) =>
    api.post(`/tasks/${taskId}/submit`, data),

  // 放弃任务
  release: (taskId: number, reason?: string) =>
    api.post(`/tasks/release/${taskId}`, { reason }),

  // 获取任务统计
  getStats: (projectId: number) => api.get(`/tasks/stats/${projectId}`),
}

// 标注相关 API
export const annotationApi = {
  // 创建标注
  create: (data: {
    task_id: number
    result: Record<string, any>
    work_time: number
  }) => api.post('/annotations', data),

  // 获取标注详情
  getById: (id: number) => api.get(`/annotations/${id}`),

  // 更新标注
  update: (id: number, data: {
    result: Record<string, any>
    work_time?: number
  }) => api.put(`/annotations/${id}`, data),

  // 获取任务的标注列表
  getByTask: (taskId: number) => api.get(`/tasks/${taskId}/annotations`),

  // 获取用户的标注历史
  getByUser: (userId: number, params?: { skip?: number; limit?: number }) =>
    api.get(`/users/${userId}/annotations`, { params }),
}

// 3D标注相关 API
export const annotations3DApi = {
  // 创建3D边界框
  createCuboid: (taskId: number, dataId: string, cuboid: any, frameId?: number, trackId?: string) =>
    api.post('/annotations/3d/cuboid', cuboid, { params: { task_id: taskId, data_id: dataId, frame_id: frameId, track_id: trackId } }),

  // 创建3D关键点
  createPoint: (taskId: number, dataId: string, point: any, frameId?: number) =>
    api.post('/annotations/3d/point', point, { params: { task_id: taskId, data_id: dataId, frame_id: frameId } }),

  // 获取任务的3D标注
  getByTask: (taskId: number, params?: { data_id?: string; frame_id?: number; annotation_type?: string }) =>
    api.get(`/annotations/3d/task/${taskId}`, { params }),

  // 更新3D标注
  update: (annotationId: string, updates: any) =>
    api.put(`/annotations/3d/${annotationId}`, updates),

  // 删除3D标注
  delete: (annotationId: string) =>
    api.delete(`/annotations/3d/${annotationId}`),

  // 批量创建
  batchCreate: (data: { task_id: number; data_id: string; annotations: any[] }) =>
    api.post('/annotations/3d/batch', data),

  // 获取统计
  getStats: (taskId: number) =>
    api.get(`/annotations/3d/task/${taskId}/stats`),

  // 导出
  export: (taskId: number, format: 'kitti' | 'json' | 'csv', includeMetadata?: boolean) =>
    api.post(`/annotations/3d/task/${taskId}/export`, { format, include_metadata: includeMetadata }),
}

// 导出相关 API
export const exportApi = {
  // 导出项目数据
  exportProject: (projectId: number, format: 'json' | 'csv' | 'coco' = 'json', status?: string) =>
    api.get(`/export/${projectId}`, {
      params: { format, status },
      responseType: 'blob',
    }),

  // 获取导出统计
  getStats: (projectId: number) => api.get(`/export/${projectId}/stats`),
}

// 自动标注相关 API
export const autoLabelApi = {
  // 获取支持的模型列表
  getModels: () => api.get('/auto-label/models'),

  // 创建自动标注任务
  createTask: (projectId: number, config: {
    model: string
    task_type: string
    confidence_threshold?: number
  }) => api.post('/auto-label/tasks', { project_id: projectId, config }),

  // 为单个数据项执行自动标注
  processItem: (taskId: number, model?: string) =>
    api.post(`/auto-label/process/${taskId}`, { model }),

  // 批量处理
  processBatch: (projectId: number, model?: string) =>
    api.post('/auto-label/batch', { project_id: projectId, model }),

  // 查看自动标注结果
  getResult: (taskId: number) => api.get(`/auto-label/result/${taskId}`),
}

// 质量控制相关 API
export const qualityApi = {
  // 执行交叉验证
  crossValidate: (projectId: number, config?: {
    min_agreement_rate?: number
    sample_rate?: number
  }) => api.post('/quality/cross-validate', { project_id: projectId, config }),

  // 获取验证结果
  getValidationResult: (projectId: number) =>
    api.get(`/quality/validation/${projectId}`),

  // 获取用户质量评分
  getUserScore: (userId: number) => api.get(`/quality/score/${userId}`),

  // 获取一致性统计
  getAgreementStats: (projectId: number) =>
    api.get(`/quality/agreement/${projectId}`),
}

// 具身标注 API（详见 services/embodied.ts）
export { embodiedApi } from './embodied'

// 2D 预标注 API（详见 services/prelabel.ts）
export { prelabelApi } from './prelabel'

// 用户相关 API
export const userApi = {
  // 获取用户列表（管理员）
  getList: (params?: { skip?: number; limit?: number; role?: string }) =>
    api.get('/users', { params }),

  // 获取用户详情
  getById: (id: number) => api.get(`/users/${id}`),

  // 创建用户（管理员）
  create: (data: {
    username: string
    email: string
    password: string
    full_name?: string
    role?: string
  }) => api.post('/users', data),

  // 更新用户
  update: (id: number, data: Partial<{
    full_name: string
    email: string
    status: string
    level: string
    skills: string[]
  }>) => api.put(`/users/${id}`, data),

  // 删除用户
  delete: (id: number) => api.delete(`/users/${id}`),

  // 获取用户统计
  getStats: (id: number) => api.get(`/users/${id}/stats`),
}

export default api
