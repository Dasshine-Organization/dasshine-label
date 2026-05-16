import { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

type Props = {
  title: string
  subtitle?: string
  accent?: string
  useBackend?: boolean
  saving?: boolean
  onSave?: () => void
  onSubmit?: () => void
  children: ReactNode
}

export default function ModalityShell({
  title,
  subtitle,
  accent = '#ec4899',
  useBackend,
  saving,
  onSave,
  onSubmit,
  children,
}: Props) {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col h-screen bg-[#0a0a0f] text-white overflow-hidden">
      <header
        className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-[#1e1e2e] shrink-0"
        style={{ borderBottomColor: `${accent}22` }}
      >
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={() => navigate('/tasks')}
            className="text-xs px-2.5 py-1.5 rounded-lg border border-[#1e1e2e] text-white/50 hover:text-white/80"
          >
            ← 任务
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

