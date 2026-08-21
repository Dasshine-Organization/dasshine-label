/**
 * Capture key UI screenshots for docs/user-guide.
 * Requires frontend on :5173 and backend on :8000.
 */
import { chromium } from 'playwright'
import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT = path.resolve(__dirname, '../docs/user-guide/images')
const BASE = process.env.UG_BASE || 'http://127.0.0.1:5173'

fs.mkdirSync(OUT, { recursive: true })

async function shot(page, name) {
  const file = path.join(OUT, `${name}.png`)
  await page.waitForTimeout(600)
  await page.screenshot({ path: file, fullPage: false })
  console.log('saved', file)
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  // 1. Login
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle' })
  await shot(page, '01-login')

  await page.locator('input').nth(0).fill('admin')
  await page.locator('input[type="password"]').fill('admin123')
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForURL(/\/($|\?)/, { timeout: 20000 }).catch(() => {})
  await page.waitForTimeout(1200)
  await shot(page, '02-dashboard')

  // 2. Projects
  await page.goto(`${BASE}/projects`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  await shot(page, '03-projects')

  // Try open first project if any
  const projectCard = page.locator('a[href*="/projects/"], button, [class*="card"]').filter({ hasText: /.+/ }).first()
  const projectLink = page.locator('a[href*="/projects/"][href*="/tasks"]').first()
  if (await projectLink.count()) {
    await projectLink.click()
    await page.waitForTimeout(1200)
    await shot(page, '04-project-tasks')
  } else {
    // click into a project from list
    const anyProject = page.locator('[href^="/projects/"]').first()
    if (await anyProject.count()) {
      await anyProject.click()
      await page.waitForTimeout(1200)
      await shot(page, '04-project-tasks')
    } else {
      await shot(page, '04-project-tasks')
    }
  }

  // 3. Tasks
  await page.goto(`${BASE}/tasks`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  await shot(page, '05-tasks')

  // 4. Review
  await page.goto(`${BASE}/review`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  await shot(page, '06-review')

  // 5. Leaderboard
  await page.goto(`${BASE}/leaderboard`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  await shot(page, '07-leaderboard')

  // 6. Users (admin)
  await page.goto(`${BASE}/users`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  await shot(page, '08-users')

  // 7. Profile
  await page.goto(`${BASE}/profile`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  await shot(page, '09-profile')

  // 8. Register page
  await page.goto(`${BASE}/register`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(600)
  await shot(page, '10-register')

  // 9. Try open an annotation workspace if a task link exists from tasks page
  await page.goto(`${BASE}/tasks`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  const annotate = page.locator('a[href*="/annotate"]').first()
  if (await annotate.count()) {
    await annotate.click()
    await page.waitForTimeout(1500)
    await shot(page, '11-annotate-workspace')
  } else {
    // navigate to projects tasks and try claim/open
    await page.goto(`${BASE}/projects`, { waitUntil: 'networkidle' })
    const p = page.locator('a[href^="/projects/"]').first()
    if (await p.count()) {
      await p.click()
      await page.waitForTimeout(1000)
      const taskOpen = page.locator('a[href*="/annotate"], button').filter({ hasText: /打开|标注|进入|开始/ }).first()
      if (await taskOpen.count()) {
        await taskOpen.click()
        await page.waitForTimeout(1500)
      }
      await shot(page, '11-annotate-workspace')
    } else {
      await shot(page, '11-annotate-workspace')
    }
  }

  await browser.close()
  console.log('done')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
