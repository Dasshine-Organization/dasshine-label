import { expect, test } from '@playwright/test'
import { installApiMocks, MODALITIES, seedAuth } from './helpers'

/**
 * P20：每模态一条冒烟 — 标注工作台 → 审核通过 → 项目导出。
 * （导入用已有任务/演示资产代替真实 ZIP，避免依赖后端与大文件。）
 */
for (const modality of MODALITIES) {
  test.describe(`P20 smoke · ${modality.id}`, () => {
    test(`annotate → review → export`, async ({ page }) => {
      await seedAuth(page)
      await installApiMocks(page, modality)

      // 1) 标注工作台可打开；能点则提交（离线/演示按钮可能 disabled）
      await page.goto(modality.annotatePath)
      const submit = page.getByRole('button', { name: modality.submitName }).first()
      await expect(submit).toBeVisible({ timeout: 20_000 })
      if (await submit.isEnabled()) {
        await submit.click()
      }

      // 2) 审核（自动选中队列首条）
      await page.goto('/review')
      await expect(page.getByRole('heading', { name: '审核工作台' })).toBeVisible()
      await expect(page.getByText(/E2E/).first()).toBeVisible({ timeout: 15_000 })
      const approve = page.getByRole('button', { name: '通过' })
      await expect(approve).toBeVisible({ timeout: 15_000 })
      await approve.click()
      await expect(page.getByText(/已通过/).first()).toBeVisible({ timeout: 10_000 })

      // 3) 导出
      await page.goto('/projects/1/tasks')
      const exportBtn = page.getByRole('button', { name: /导出数据/ })
      await expect(exportBtn).toBeVisible({ timeout: 15_000 })
      await exportBtn.click()
      await page.locator('button', { hasText: new RegExp(modality.exportFormat, 'i') }).first().click()
      await expect(page.getByText(/已导出/).first()).toBeVisible({ timeout: 10_000 })
    })
  })
}
