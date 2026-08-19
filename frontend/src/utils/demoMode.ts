/** 演示任务 / 演示入口开关（产品默认走真实项目列表） */

type Listener = () => void

let serverAllowsDemo: boolean | null = null
const listeners = new Set<Listener>()

/** 后端 public-config.demo_entries_enabled；false 时强制关闭（生产杀开关） */
export function applyServerDemoEntries(enabled: boolean | undefined | null) {
  if (enabled === undefined || enabled === null) return
  serverAllowsDemo = Boolean(enabled)
  listeners.forEach(fn => fn())
}

export function subscribeDemoEntries(fn: Listener): () => void {
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}

export function isDemoEntriesEnabled(): boolean {
  if (serverAllowsDemo === false) return false
  const flag = import.meta.env.VITE_ENABLE_DEMO_ENTRIES
  if (flag === 'true') return true
  if (flag === 'false') return false
  // 本地开发默认展示「演示」分区，生产构建默认隐藏
  return Boolean(import.meta.env.DEV)
}
