import { defineConfig, devices } from '@playwright/test'

const PORT = Number(process.env.E2E_PORT || 4173)

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: process.env.E2E_BASE_URL || `http://127.0.0.1:${PORT}`,
    trace: 'on-first-retry',
    ...devices['Desktop Chrome'],
  },
  webServer: {
    command: `npx vite --host 127.0.0.1 --port ${PORT} --strictPort`,
    url: `http://127.0.0.1:${PORT}`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      ...process.env,
      VITE_ENABLE_DEMO_ENTRIES: 'true',
      VITE_E2E_STUB_AUTOMERGE: 'true',
      VITE_API_URL: 'http://127.0.0.1:8000/api/v1',
    },
  },
})
