import { ReactNode, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import CollabPresenceBar from '../CollabPresenceBar'
import TaskLockBanner from '../TaskLockBanner'
import { GuidelinesSidePanel } from './GuidelinesPanel'
import type { TaskLockState } from '../../hooks/useTaskLock'
import type { CollabPeer } from '../../hooks/useYjsCollab'

type RejectTarget = { object_id: string; label?: string; note?: string }

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
  onAutoLabel?: () => void
  autoLabeling?: boolean
  onNext?: () => void
  onSkip?: () => void
  navBusy?: boolean
  guidelinesMd?: string
  rejectFeedback?: string | null
  rejectTargets?: RejectTarget[]
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
  onAutoLabel,
  autoLabeling,
  onNext,
  onSkip,
  navBusy,
  guidelinesMd,
  rejectFeedback,
  rejectTargets,
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
  const [showGuide, setShowGuide] = useState(false)
  const [showKeys, setShowKeys] = useState(false)

  return (
    <div className="flex flex-col h-screen bg-[#0a0a0f] text-white overflow-hidden">
      {lock && <TaskLockBanner lock={lock} blocked={Boolean(lockBlocked)} />}
      {peers && <CollabPresenceBar peers={peers} connected={Boolean(connected)} />}
      {(rejectFeedback || (rejectTargets && rejectTargets.length > 0)) && (
        <div className="px-4 py-2 bg-[#ef4444]/10 border-b border-[#ef4444]/25 text-[11px] text-[#fca5a5]">
          <span className="font-medium">审核驳回：</span>
          {rejectFeedback || '请按定位修改'}
          {rejectTargets && rejectTargets.length > 0 && (
            <span className="ml-2 text-[#ef4444]/80">
              定位 {rejectTargets.map(t => t.object_id).join(', ')}
            </span>
          )}
        </div>
      )}
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
          <button
            type="button"
            onClick={() => setShowKeys(true)}
            className="text-[10px] px-2 py-1 rounded border border-white/10 text-white/40 hover:text-white/70"
            title="快捷键"
          >
            ?
          </button>
          {guidelinesMd !== undefined && (
            <button
              type="button"
              onClick={() => setShowGuide(v => !v)}
              className="text-xs px-2.5 py-1.5 rounded-lg border border-white/15 text-white/50 hover:text-white/80"
            >
              规范
            </button>
          )}
          {onSkip && (
            <button
              type="button"
              onClick={onSkip}
              disabled={navBusy || lockBlocked || useBackend === false}
              className="text-xs px-3 py-1.5 rounded-lg border border-white/15 text-white/50 disabled:opacity-40"
            >
              跳过
            </button>
          )}
          {onNext && (
            <button
              type="button"
              onClick={onNext}
              disabled={navBusy || useBackend === false}
              className="text-xs px-3 py-1.5 rounded-lg border border-[#10b981]/35 text-[#10b981] disabled:opacity-40"
            >
              {navBusy ? '…' : '下一题'}
            </button>
          )}
          {onAutoLabel && (
            <button
              type="button"
              onClick={onAutoLabel}
              disabled={autoLabeling || lockBlocked || useBackend === false}
              className="text-xs px-3 py-1.5 rounded-lg border border-[#00d4ff]/30 text-[#00d4ff] hover:bg-[#00d4ff]/10 disabled:opacity-40"
            >
              {autoLabeling ? 'AI 预标注中…' : 'AI 预标注'}
            </button>
          )}
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
      <div className="flex-1 overflow-hidden flex">
        <main className="flex-1 overflow-hidden">{children}</main>
        {showGuide && (
          <aside className="w-72 border-l border-[#1e1e2e] bg-[#12121a] overflow-y-auto shrink-0">
            <div className="text-[10px] text-white/35 uppercase tracking-wider px-3 py-2 border-b border-[#1e1e2e]">
              标注规范
            </div>
            <GuidelinesSidePanel markdown={guidelinesMd} />
          </aside>
        )}
      </div>
      {showKeys && (
        <div
          className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
          onClick={() => setShowKeys(false)}
        >
          <div
            className="bg-[#12121a] border border-[#1e1e2e] rounded-xl p-5 max-w-sm w-full text-sm"
            onClick={e => e.stopPropagation()}
          >
            <div className="font-medium mb-3">快捷操作</div>
            <ul className="space-y-1.5 text-white/55 text-xs">
              <li>保存草稿 — 顶栏按钮（自动防抖保存）</li>
              <li>提交标注 — 顶栏「提交标注」</li>
              <li>下一题 / 跳过 — 顶栏按钮</li>
              <li>规范 — 顶栏打开侧栏必读文档</li>
              <li>文本 NER — 选中文字后打标签</li>
            </ul>
            <button
              type="button"
              className="mt-4 text-xs text-[#00d4ff]"
              onClick={() => setShowKeys(false)}
            >
              关闭
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
