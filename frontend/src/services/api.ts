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
      const url = error.config?.url ?? ''
      const isAuthAttempt =
        url.includes('/auth/login') || url.includes('/auth/register')
      if (!isAuthAttempt) {
        localStorage.removeItem('dasshine_auth')
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login'
        }
      }
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

  // 修改当前用户密码
  changePassword: (data: { current_password: string; new_password: string }) =>
    api.post('/auth/change-password', data),
}

// 组织（多租户）
export const orgApi = {
  list: () =>
    api.get<{ active_org_id: number | null; items: Array<{ id: number; name: string; slug: string }> }>(
      '/orgs',
    ),
  create: (data: { name: string; slug?: string }) => api.post('/orgs', data),
  activate: (orgId: number) => api.post(`/orgs/${orgId}/activate`),
  getMembers: (orgId: number) => api.get(`/orgs/${orgId}/members`),
  addMember: (orgId: number, data: { user_id: number; role?: string }) =>
    api.post(`/orgs/${orgId}/members`, data),
  getQuota: (orgId: number) => api.get(`/orgs/${orgId}/quota`),
  updateQuota: (
    orgId: number,
    data: { max_projects?: number; max_tasks?: number; max_members?: number; credits?: number },
  ) => api.put(`/orgs/${orgId}/quota`, data),
  getBilling: (orgId: number) => api.get(`/orgs/${orgId}/billing`),
  topupBilling: (orgId: number, data: { amount: number; note?: string }) =>
    api.post(`/orgs/${orgId}/billing/topup`, data),
  checkout: (orgId: number, packId: string) =>
    api.post<{ session_id: string; url: string }>(`/orgs/${orgId}/billing/checkout`, {
      pack_id: packId,
    }),
}

export const billingApi = {
  listPacks: () =>
    api.get<{ configured: boolean; items: Array<Record<string, unknown>> }>('/billing/packs'),
  checkout: (orgId: number, packId: string) =>
    api.post<{ session_id: string; url: string }>(`/orgs/${orgId}/billing/checkout`, {
      pack_id: packId,
    }),
}

// 项目相关 API
export const projectApi = {
  // 获取项目列表
  getList: (params?: {
    skip?: number
    limit?: number
    status?: string
    category?: string
    org_id?: number
  }) => api.get('/projects', { params }),

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
  }>) => api.patch(`/projects/${id}`, data),

  archive: (id: number) => api.post(`/projects/${id}/archive`),

  restore: (id: number) => api.post(`/projects/${id}/restore`),

  delete: (id: number) => api.delete(`/projects/${id}`),

  // 添加项目成员
  addMember: (projectId: number, userId: number, role: string) =>
    api.post(`/projects/${projectId}/members`, { user_id: userId, role }),

  removeMember: (projectId: number, userId: number) =>
    api.delete(`/projects/${projectId}/members/${userId}`),

  getMembers: (projectId: number) =>
    api.get<Array<{
      user_id: number
      username: string
      level: string
      role: string
      accuracy_score: number
      completed_tasks: number
    }>>(`/projects/${projectId}/members`),

  getDispatchLogs: (projectId: number, limit = 10) =>
    api.get<{ project_id: number; total: number; logs: Array<Record<string, unknown>> }>(
      `/projects/${projectId}/dispatch-logs`,
      { params: { limit } },
    ),

  getStats: (projectId: number) => api.get(`/projects/${projectId}/stats`),

  getGoldenTasks: (projectId: number) =>
    api.get<{
      project_id: number
      total: number
      items: Array<{
        id: number
        status: string
        is_golden: boolean
        has_golden_answer: boolean
        golden_answer?: Record<string, unknown>
        data_url?: string
        filename?: string
      }>
    }>(`/projects/${projectId}/golden-tasks`),

  getQualityConfig: (projectId: number) =>
    api.get<{ project_id: number; quality_config: Record<string, unknown> }>(
      `/projects/${projectId}/quality-config`,
    ),

  updateQualityConfig: (projectId: number, config: Record<string, unknown>) =>
    api.put(`/projects/${projectId}/quality-config`, config),
}

// 任务相关 API
export const taskApi = {
  getById: (taskId: number) => api.get(`/tasks/${taskId}`),

  getProjectTasks: (projectId: number, params?: { page?: number; page_size?: number; status?: string }) =>
    api.get(`/projects/${projectId}/tasks`, { params }),

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

  /** 标注占用锁 */
  getLock: (taskId: number) => api.get(`/tasks/${taskId}/lock`),
  acquireLock: (taskId: number) => api.post(`/tasks/${taskId}/lock`),
  releaseLock: (taskId: number) => api.delete(`/tasks/${taskId}/lock`),

  /** 2D 图像标注草稿（服务端） */
  getAnnotationDraft: (taskId: number) =>
    api.get<{
      payload: Record<string, unknown>
      task_status?: string
      updated_at?: string | null
    }>(`/tasks/${taskId}/annotation-draft`),

  saveAnnotationDraft: (taskId: number, payload: Record<string, unknown>) =>
    api.put<{ task_status?: string }>(`/tasks/${taskId}/annotation-draft`, { payload }),

  submitImageAnnotation: (
    taskId: number,
    data: { payload: Record<string, unknown>; work_time: number },
  ) =>
    api.post<{ task_status?: string; message?: string }>(
      `/tasks/${taskId}/image/submit`,
      data,
    ),

  submitPointCloudAnnotation: (
    taskId: number,
    data: { payload: Record<string, unknown>; work_time: number },
  ) =>
    api.post<{ task_status?: string; message?: string }>(
      `/tasks/${taskId}/pointcloud/submit`,
      data,
    ),
}

// 标注相关 API 已废弃（410）。请使用 taskApi annotation-draft / submit。

// 导出相关 API
export const exportApi = {
  exportProject: (projectId: number, format: string = 'coco', status?: string) =>
    api.get(`/export/${projectId}`, {
      params: { format, status },
      responseType: 'blob',
    }),

  startJob: (projectId: number, format: string, status?: string) =>
    api.post<{ job_id: string; status: string; format: string }>(`/export/${projectId}/jobs`, null, {
      params: { format, status },
    }),

  getJob: (jobId: string) =>
    api.get<{
      job_id: string
      state: string
      status: string
      ready: boolean
      download_url?: string
      error?: string
      bytes?: number
    }>(`/export/jobs/${jobId}`),

  getStats: (projectId: number) =>
    api.get<{
      project_id: number
      category?: string
      default_format?: string
      export_formats?: string[]
      formats?: Array<{
        id: string
        label: string
        ext: string
        description: string
        primary?: boolean
      }>
      approved_tasks?: number
      ready_for_export?: number
    }>(`/export/${projectId}/stats`),
}

// LLM/OCR 自动标注未接入（API 501）。2D 请用 taskApi prelabel。

// 质量控制相关 API
export const qualityApi = {
  getQueue: (params?: { project_id?: number; limit?: number }) =>
    api.get<{ total: number; items: Array<Record<string, unknown>> }>('/quality/queue', {
      params,
    }),

  getTaskDetail: (taskId: number) => api.get(`/quality/tasks/${taskId}`),

  review: (data: {
    task_id: number
    decision: 'approved' | 'rejected'
    score?: number
    feedback?: string
    canonical_annotation_id?: string
  }) =>
    api.post<{ success: boolean; message: string; task_id: number; task_status: string }>(
      '/quality/review',
      data,
    ),

  // 执行交叉验证
  crossValidate: (taskId: number) =>
    api.post('/quality/cross-validation', { task_id: taskId }),

  insertGolden: (projectId: number, ratio = 0.1) =>
    api.post<{ success: boolean; inserted: number; ratio: number }>('/quality/insert-golden', {
      project_id: projectId,
      ratio,
    }),

  updateGoldenAnswer: (taskId: number, data: Record<string, unknown>, source = 'expert') =>
    api.put(`/quality/tasks/${taskId}/golden-answer`, { data, source, confidence: 1 }),

  getReport: (projectId: number) => api.get(`/quality/report/${projectId}`),

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

// 文本 / 语音 / 视频标注 API
export { modalityApi } from './modalityAnnotation'

// 用户相关 API
export interface UserRecord {
  id: number
  username: string
  email: string
  full_name?: string | null
  role: string
  status: string
  level: string
  accuracy_score: number
  completed_tasks: number
  is_admin: boolean
}

export const userApi = {
  getList: (params?: { skip?: number; limit?: number; role?: string; status?: string }) =>
    api.get<UserRecord[]>('/users', { params }),

  getById: (id: number) => api.get<UserRecord>(`/users/${id}`),

  create: (data: {
    username: string
    email: string
    password: string
    full_name?: string
    role?: string
  }) => api.post<UserRecord>('/users', data),

  update: (id: number, data: Partial<{
    full_name: string
    email: string
    role: string
    status: string
    level: string
    skills: string[]
  }>) => api.put<UserRecord>(`/users/${id}`, data),

  delete: (id: number) => api.delete(`/users/${id}`),

  resetPassword: (id: number, new_password: string) =>
    api.post(`/users/${id}/reset-password`, { new_password }),

  getStats: (id: number) => api.get(`/users/${id}/stats`),
}

export const rolesApi = {
  list: () => api.get<{
    roles: { value: string; label: string; permissions: string[] }[]
    current_role: string
    current_permissions: string[]
    is_admin: boolean
  }>('/roles'),
}

export default api
