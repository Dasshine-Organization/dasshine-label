/** 演示任务 / 演示入口开关（产品默认走真实项目列表） */
export function isDemoEntriesEnabled(): boolean {
  const flag = import.meta.env.VITE_ENABLE_DEMO_ENTRIES
  if (flag === 'true') return true
  if (flag === 'false') return false
  // 本地开发默认展示「演示」分区，生产构建默认隐藏
  return Boolean(import.meta.env.DEV)
}
