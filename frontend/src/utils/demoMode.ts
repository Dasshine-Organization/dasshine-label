/**
 * 演示入口开关。
 *
 * 优先级：VITE_ENABLE_DEMO_ENTRIES=true/false 强制 → DEV 默认开 →
 * 生产构建看后端 public-config.demo_entries_enabled。
 * 生产 Docker 编译期为 false，即使后端误开 DEBUG 也不会因 Vite 再露出演示区。
 */

type Listener = () => void

let serverAllowsDemo: boolean | null = null
const listeners = new Set<Listener>()

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
  const flag = import.meta.env.VITE_ENABLE_DEMO_ENTRIES
  if (flag === 'true') return true
  if (flag === 'false') return false
  if (import.meta.env.DEV) return true
  return serverAllowsDemo === true
}
