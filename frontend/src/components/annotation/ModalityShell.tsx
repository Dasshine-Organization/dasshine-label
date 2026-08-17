import { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import CollabPresenceBar from '../CollabPresenceBar'
import TaskLockBanner from '../TaskLockBanner'
import type { TaskLockState } from '../../hooks/useTaskLock'
import type { CollabPeer } from '../../hooks/useYjsCollab'

type Props = {
  title: string
  subtitle?: string
  accent?: string
  useBackend?: boolean
  saving?: boolean
  dirty?: boolean
  lastSavedAt?: string | null
  onSave?: () => void
  onSubmit?: () => void
  /** 返回列表路径，默认 /tasks；有 projectId 时应传项目任务列表 */
  backHref?: string
  backLabel?: string
  headerExtra?: ReactNode
  children: ReactNode
  lock?: TaskLockState
  lockBlocked?: boolean
  peers?: CollabPeer[]
  connected?: boolean
}

export default function ModalityShell({
  title,
  subtitle,
  accent = '#ec4899',
  useBackend,
  saving,
  dirty,
  lastSavedAt,
  onSave,
  onSubmit,
  backHref = '/tasks',
  backLabel = '← 返回',
  headerExtra,
  children,
  lock,
  lockBlocked,
  peers,
  connected,
}: Props) {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col h-screen bg-[#0a0a0f] text-white overflow-hidden">
      {lock && <TaskLockBanner lock={lock} blocked={Boolean(lockBlocked)} />}
      {peers && <CollabPresenceBar peers={peers} connected={Boolean(connected)} />}
      <header
        className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-[#1e1e2e] shrink-0"
        style={{ borderBottomColor: `${accent}22` }}
      >
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={() => navigate(backHref)}
            className="text-xs px-2.5 py-1.5 rounded-lg border border-[#1e1e2e] text-white/50 hover:text-white/80"
          >
            {backLabel}
          </button>
          <div className="min-w-0">
            <h1 className="text-sm font-semibold truncate" style={{ color: accent }}>
              {title}
            </h1>
            {subtitle && <p className="text-[11px] text-white/35 truncate">{subtitle}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {useBackend !== undefined && (
            <span className="text-[10px] text-white/30 px-2 py-1 rounded border border-white/10">
              {useBackend ? '已连接后端' : '离线演示'}
            </span>
          )}
          {dirty && !saving && (
            <span className="text-[10px] text-[#f59e0b]/90 px-2 py-0.5 rounded border border-[#f59e0b]/25">
              未保存
            </span>
          )}
          {lastSavedAt && (
            <span className="text-[10px] text-[#10b981]/80 font-mono" title={lastSavedAt}>
              已保存{' '}
              {new Date(lastSavedAt).toLocaleTimeString('zh-CN', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
              })}
            </span>
          )}
          {headerExtra}
          {onSave && (
            <button
              type="button"
              onClick={onSave}
              disabled={saving}
              className="text-xs px-3 py-1.5 rounded-lg border border-white/15 text-white/60 hover:border-white/30"
            >
              {saving ? '保存中…' : '保存草稿'}
            </button>
          )}
          {onSubmit && (
            <button
              type="button"
              onClick={onSubmit}
              className="text-xs px-3 py-1.5 rounded-lg text-white font-medium"
              style={{ background: `${accent}33`, border: `1px solid ${accent}55` }}
            >
              提交标注
            </button>
          )}
        </div>
      </header>
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  )
}
