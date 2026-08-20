import type { Page, Route } from '@playwright/test'

/**
 * 每模态一条冒烟：打开工作台 → 审核通过 → 项目导出。
 * 全程 mock /api/v1，不连真实后端；演示 taskId 对应离线工作台。
 */
export type ModalitySmoke = {
  id: string
  category: string
  annotatePath: string
  submitName: RegExp
  reviewLabel: string
  exportFormat: string
}

export const MODALITIES: ModalitySmoke[] = [
  { id: 'image_2d', category: 'image_2d', annotatePath: '/annotate-image/1001', submitName: /提交/, reviewLabel: '图像 2D 样例', exportFormat: 'coco' },
  { id: 'pointcloud_3d', category: 'pointcloud_3d', annotatePath: '/annotate-3d/1002', submitName: /提交/, reviewLabel: '点云样例', exportFormat: 'kitti' },
  { id: 'nlp', category: 'nlp', annotatePath: '/annotate-text/3001', submitName: /提交标注/, reviewLabel: '语料样例', exportFormat: 'jsonl' },
  { id: 'audio', category: 'audio', annotatePath: '/annotate-audio/3002', submitName: /提交标注/, reviewLabel: '语音样例', exportFormat: 'jsonl' },
  { id: 'video', category: 'video', annotatePath: '/annotate-video/3003', submitName: /提交标注/, reviewLabel: '视频样例', exportFormat: 'jsonl' },
  { id: 'ocr', category: 'ocr', annotatePath: '/annotate-ocr/ocr-demo', submitName: /提交审核/, reviewLabel: 'OCR 样例', exportFormat: 'jsonl' },
  { id: 'multimodal', category: 'multimodal', annotatePath: '/annotate-multimodal/mm-demo', submitName: /提交标注/, reviewLabel: '多模态样例', exportFormat: 'jsonl' },
  { id: 'embodied', category: 'embodied', annotatePath: '/annotate-embodied/demo', submitName: /提交审核/, reviewLabel: '具身样例', exportFormat: 'json' },
]

function json(route: Route, body: unknown, extra?: { headers?: Record<string, string> }) {
  return route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(body),
    headers: extra?.headers,
  })
}

export async function seedAuth(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem(
      'dasshine_auth',
      JSON.stringify({
        state: {
          user: {
            id: 1,
            username: 'e2e',
            email: 'e2e@example.com',
            level: 'expert',
            role: 'admin',
            is_admin: true,
            skill_tags: [],
            accuracy_rate: 0.9,
            total_completed: 0,
            total_earnings: 0,
            active_tasks: 0,
          },
          token: 'e2e-token',
          isAuthenticated: true,
        },
        version: 0,
      }),
    )
  })
}

export async function installApiMocks(page: Page, modality: ModalitySmoke) {
  await page.route('**/api/v1/**', async route => {
    const url = route.request().url()
    const method = route.request().method()
    const taskId = 9000 + MODALITIES.findIndex(m => m.id === modality.id)

    if (url.includes('/auth/public-config')) {
      return json(route, {
        register_enabled: true,
        oidc_enabled: false,
        frontend_url: 'http://127.0.0.1:4173',
        demo_entries_enabled: true,
        metrics_enabled: true,
      })
    }
    if (url.includes('/quality/queue')) {
      return json(route, {
        total: 1,
        items: [{
          id: taskId,
          project_id: 1,
          project_name: `E2E ${modality.category}`,
          category: modality.category,
          status: 'submitted',
          filename: modality.reviewLabel,
          assignee_name: 'e2e',
        }],
      })
    }
    if (url.includes('/quality/tasks/') && method === 'GET') {
      return json(route, {
        id: taskId,
        project_id: 1,
        project_name: `E2E ${modality.category}`,
        category: modality.category,
        status: 'submitted',
        filename: modality.reviewLabel,
        annotations2d: [],
        modality_preview: { modality: modality.category },
      })
    }
    if (url.includes('/quality/review') && method === 'POST') {
      return json(route, { success: true, message: '已通过', task_id: taskId, task_status: 'approved' })
    }
    if (url.includes('/projects/1') && !url.includes('/tasks') && method === 'GET') {
      return json(route, {
        id: 1,
        name: `E2E ${modality.category}`,
        category: modality.category,
        status: 'active',
        total_items: 1,
        approved_items: 1,
      })
    }
    if (url.includes('/projects/1/tasks')) {
      return json(route, {
        total: 1,
        items: [{ id: 1, project_id: 1, filename: 'sample', status: 'approved', priority: 5, category: modality.category }],
      })
    }
    if (url.includes('/export/1/stats')) {
      return json(route, {
        project_id: 1,
        category: modality.category,
        default_format: modality.exportFormat,
        approved_tasks: 1,
        formats: [{ id: modality.exportFormat, label: modality.exportFormat, ext: 'bin', description: 'e2e', primary: true }],
      })
    }
    if (url.includes('/export/1/snapshots')) {
      return json(route, { items: [] })
    }
    if (url.match(/\/export\/1(\?|$)/) && method === 'GET') {
      return json(route, { ok: true, category: modality.category }, {
        headers: { 'Content-Disposition': 'attachment; filename="e2e.json"' },
      })
    }
    if (url.includes('/analytics') || url.includes('/active-learning') || url.includes('/dispatch-logs')) {
      return json(route, { summary: {}, items: [], logs: [], total: 0 })
    }
    return json(route, { ok: true, items: [], total: 0 })
  })
}
