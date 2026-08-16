import type { TaskLockState } from '../hooks/useTaskLock'

/** 他人占用任务时的顶栏提示 */
export default function TaskLockBanner({
  lock,
  blocked,
}: {
  lock: TaskLockState
  blocked: boolean
}) {
  if (!blocked) return null
  return (
    <div className="px-4 py-2 text-xs bg-amber-500/15 text-amber-200 border-b border-amber-500/30">
      该任务正由 <span className="font-medium">{lock.holderUsername || '其他用户'}</span>{' '}
      标注中（占用锁未过期）。你可查看，编辑将在对方释放或锁过期后可用。
    </div>
  )
}
