import type { Page } from '@playwright/test'

export type ModalitySmoke = {
  id: string
  category: string
  annotatePath: string
  submitName: RegExp
  reviewLabel: string
  exportFormat: string
}

/** 每模态一条：导入(有任务) → 标注 → 审核 → 导出 */
export const MODALITIES: ModalitySmoke[] = [
  {
    id: 'image_2d',
    category: 'image_2d',
    annotatePath: '/annotate-image/1001',
    submitName: /提交/,
    reviewLabel: '图像 2D 样例',
    exportFormat: 'coco',
  },
  {
    id: 'pointcloud_3d',
    category: 'pointcloud_3d',
    annotatePath: '/annotate-3d/1002',
    submitName: /提交/,
    reviewLabel: '点云样例',
    exportFormat: 'kitti',
  },
  {
    id: 'nlp',
    category: 'nlp',
    annotatePath: '/annotate-text/3001',
    submitName: /提交标注/,
    reviewLabel: '语料样例',
    exportFormat: 'jsonl',
  },
  {
    id: 'audio',
    category: 'audio',
    annotatePath: '/annotate-audio/3002',
    submitName: /提交标注/,
    reviewLabel: '语音样例',
    exportFormat: 'jsonl',
  },
  {
    id: 'video',
    category: 'video',
    annotatePath: '/annotate-video/3003',
    submitName: /提交标注/,
    reviewLabel: '视频样例',
    exportFormat: 'jsonl',
  },
  {
    id: 'ocr',
    category: 'ocr',
    annotatePath: '/annotate-ocr/ocr-demo',
    submitName: /提交审核/,
    reviewLabel: 'OCR 样例',
    exportFormat: 'jsonl',
  },
  {
    id: 'multimodal',
    category: 'multimodal',
    annotatePath: '/annotate-multimodal/mm-demo',
    submitName: /提交标注/,
    reviewLabel: '多模态样例',
    exportFormat: 'jsonl',
  },
  {
    id: 'embodied',
    category: 'embodied',
    annotatePath: '/annotate-embodied/demo',
    submitName: /提交审核/,
    reviewLabel: '具身样例',
    exportFormat: 'json',
  },
]

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
    const req = route.request()
    const url = req.url()
    const method = req.method()

    if (url.includes('/auth/public-config')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          register_enabled: true,
          oidc_enabled: false,
          frontend_url: 'http://127.0.0.1:4173',
          demo_entries_enabled: true,
          metrics_enabled: true,
        }),
      })
    }

    if (url.includes('/quality/queue')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 1,
          items: [
            {
              id: 9000 + MODALITIES.findIndex(m => m.id === modality.id),
              project_id: 1,
              project_name: `E2E ${modality.category}`,
              category: modality.category,
              status: 'submitted',
              filename: modality.reviewLabel,
              assignee_name: 'e2e',
            },
          ],
        }),
      })
    }

    if (url.includes('/quality/tasks/') && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 9001,
          project_id: 1,
          project_name: `E2E ${modality.category}`,
          category: modality.category,
          status: 'submitted',
          filename: modality.reviewLabel,
          annotations2d: [],
          modality_preview: { modality: modality.category },
        }),
      })
    }

    if (url.includes('/quality/review') && method === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: '已通过',
          task_id: 9001,
          task_status: 'approved',
        }),
      })
    }

    if (url.includes('/projects/1') && !url.includes('/tasks') && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          name: `E2E ${modality.category}`,
          category: modality.category,
          status: 'active',
          total_items: 1,
          approved_items: 1,
        }),
      })
    }

    if (url.includes('/projects/1/tasks')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total: 1,
          items: [
            {
              id: 1,
              project_id: 1,
              filename: 'sample',
              status: 'approved',
              priority: 5,
              category: modality.category,
            },
          ],
        }),
      })
    }

    if (url.includes('/export/1/stats')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          project_id: 1,
          category: modality.category,
          default_format: modality.exportFormat,
          approved_tasks: 1,
          formats: [
            {
              id: modality.exportFormat,
              label: modality.exportFormat,
              ext: 'bin',
              description: 'e2e',
              primary: true,
            },
          ],
        }),
      })
    }

    if (url.includes('/export/1/snapshots')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [] }),
      })
    }

    if (url.match(/\/export\/1(\?|$)/) && method === 'GET') {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: { 'Content-Disposition': 'attachment; filename="e2e.json"' },
        body: JSON.stringify({ ok: true, category: modality.category }),
      })
    }

    if (url.includes('/analytics') || url.includes('/active-learning') || url.includes('/dispatch-logs')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ summary: {}, items: [], logs: [], total: 0 }),
      })
    }

    // 其余 API：避免 401 踢回登录
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, items: [], total: 0 }),
    })
  })
}
