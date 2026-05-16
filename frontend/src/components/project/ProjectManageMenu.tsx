import { useState, useRef, useEffect } from 'react'
import { Modal, message } from 'antd'
import { projectApi } from '../../services/api'
import type { ProjectSummary } from '../../types/project'

type Props = {
  project: ProjectSummary
  onChanged: () => void
}

export default function ProjectManageMenu({ project, onChanged }: Props) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const isArchived = project.status === 'archived'
  const total = project.total_items ?? project.total_tasks ?? 0

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  async function run(action: () => Promise<void>) {
    setBusy(true)
    try {
      await action()
      onChanged()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '操作失败')
    } finally {
      setBusy(false)
      setOpen(false)
    }
  }

  function confirmArchive() {
    Modal.confirm({
      title: '归档项目',
      content: (
        <div className="text-white/60 text-sm space-y-2">
          <p>归档后项目将变为只读，不再分派新任务，数据仍保留。</p>
          <p>可随时从「已归档」筛选中恢复。</p>
        </div>
      ),
      okText: '归档',
      cancelText: '取消',
      okButtonProps: { disabled: busy },
      onOk: () =>
        run(async () => {
          await projectApi.archive(project.id)
          message.success('项目已归档')
        }),
    })
  }

  function confirmRestore() {
    Modal.confirm({
      title: '恢复项目',
      content: '将项目从归档状态恢复为归档前的状态，可继续导入与分派任务。',
      okText: '恢复',
      cancelText: '取消',
      onOk: () =>
        run(async () => {
          await projectApi.restore(project.id)
          message.success('项目已恢复')
        }),
    })
  }

  function confirmDelete() {
    Modal.confirm({
      title: '永久删除项目',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      content: (
        <div className="text-white/60 text-sm space-y-2">
          <p>
            确定删除「<span className="text-white/80">{project.name}</span>」？此操作不可撤销。
          </p>
          {total > 0 && (
            <p className="text-amber-400/90">
              将同时删除 {total.toLocaleString()} 条任务及关联标注数据。
            </p>
          )}
        </div>
      ),
      onOk: () =>
        run(async () => {
          const { data } = await projectApi.delete(project.id)
          const n = data?.deleted_tasks ?? 0
          message.success(n > 0 ? `已删除项目及 ${n} 条任务` : '项目已删除')
        }),
    })
  }

  return (
    <div ref={ref} className="relative" onClick={e => e.stopPropagation()}>
      <button
        type="button"
        disabled={busy}
        onClick={() => setOpen(v => !v)}
        className="p-1.5 rounded-lg text-white/30 hover:text-white/70 hover:bg-white/5 transition-all
          disabled:opacity-40"
        aria-label="项目操作"
      >
        <svg viewBox="0 0 16 16" fill="currentColor" className="w-4 h-4">
          <circle cx="8" cy="3" r="1.25" />
          <circle cx="8" cy="8" r="1.25" />
          <circle cx="8" cy="13" r="1.25" />
        </svg>
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-1 z-20 min-w-[140px] py-1 rounded-xl border border-[#1e1e2e]
            bg-[#12121a] shadow-xl shadow-black/40"
        >
          {isArchived ? (
            <button
              type="button"
              disabled={busy}
              onClick={confirmRestore}
              className="w-full px-3 py-2 text-left text-xs text-white/70 hover:bg-white/5 hover:text-white"
            >
              恢复项目
            </button>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={confirmArchive}
              className="w-full px-3 py-2 text-left text-xs text-white/70 hover:bg-white/5 hover:text-white"
            >
              归档项目
            </button>
          )}
          <div className="my-1 border-t border-[#1e1e2e]" />
          <button
            type="button"
            disabled={busy}
            onClick={confirmDelete}
            className="w-full px-3 py-2 text-left text-xs text-red-400/80 hover:bg-red-500/10 hover:text-red-400"
          >
            永久删除
          </button>
        </div>
      )}
    </div>
  )
}
