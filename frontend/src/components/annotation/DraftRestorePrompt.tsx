import { useEffect, useState } from 'react'
import useAnnotationStore, { AnnotationDraft } from '../../store/annotationStore'

// ─── DraftRestorePrompt ───────────────────────────────────────────────────────
// 进入标注页时，如果检测到草稿，弹出恢复提示

interface Props {
  taskId: string
  imageIndex: number
  onRestored?: () => void
  onDiscarded?: () => void
}

export default function DraftRestorePrompt({ taskId, imageIndex, onRestored, onDiscarded }: Props) {
  const { drafts, loadDraft, deleteDraft } = useAnnotationStore()
  const [draft, setDraft] = useState<AnnotationDraft | null>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const key = `${taskId}:${imageIndex}`
    const found = drafts[key]
    if (found && !found.isSubmitted) {
      setDraft(found)
      setVisible(true)
    }
  }, [taskId, imageIndex])

  if (!visible || !draft) return null

  function formatRelative(iso: string) {
    const diff = Date.now() - new Date(iso).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return '刚刚'
    if (mins < 60) return `${mins} 分钟前`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours} 小时前`
    return new Date(iso).toLocaleDateString('zh-CN')
  }

  function handleRestore() {
    loadDraft(taskId, imageIndex)
    setVisible(false)
    onRestored?.()
  }

  function handleDiscard() {
    deleteDraft(taskId, imageIndex)
    setVisible(false)
    onDiscarded?.()
  }

  const count2d = draft.annotations2d.length
  const count3d = draft.boxes3d.length

  return (
    <div className="absolute top-16 left-1/2 -translate-x-1/2 z-50 w-80 animate-in slide-in-from-top-2">
      <div className="bg-[#12121a] border border-[#f59e0b]/30 rounded-xl p-4 shadow-2xl"
        style={{ boxShadow: '0 0 30px rgba(245,158,11,0.08)' }}>

        {/* Header */}
        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-8 h-8 rounded-lg bg-[#f59e0b]/10 border border-[#f59e0b]/20 flex items-center justify-center flex-shrink-0">
            <svg viewBox="0 0 16 16" fill="none" stroke="#f59e0b" strokeWidth="1.5" className="w-4 h-4">
              <path d="M8 3v5l3 3" strokeLinecap="round" strokeLinejoin="round"/>
              <circle cx="8" cy="8" r="6"/>
            </svg>
          </div>
          <div>
            <div className="text-sm font-medium text-white/80">发现未完成的草稿</div>
            <div className="text-[11px] text-white/30">保存于 {formatRelative(draft.savedAt)}</div>
          </div>
        </div>

        {/* Stats */}
        <div className="flex gap-2 mb-4">
          {count2d > 0 && (
            <div className="flex-1 bg-[#0a0a0f] rounded-lg px-3 py-2 border border-[#1e1e2e]">
              <div className="text-[10px] text-white/30 mb-0.5">2D 标注</div>
              <div className="text-base font-mono text-[#00d4ff]">{count2d}</div>
            </div>
          )}
          {count3d > 0 && (
            <div className="flex-1 bg-[#0a0a0f] rounded-lg px-3 py-2 border border-[#1e1e2e]">
              <div className="text-[10px] text-white/30 mb-0.5">3D 框</div>
              <div className="text-base font-mono text-[#a78bfa]">{count3d}</div>
            </div>
          )}
          {count2d === 0 && count3d === 0 && (
            <div className="text-xs text-white/30">草稿为空</div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={handleRestore}
            className="flex-1 py-2 rounded-lg text-xs font-medium transition-all active:scale-95
              bg-[#f59e0b]/15 text-[#f59e0b] border border-[#f59e0b]/30
              hover:bg-[#f59e0b]/25 hover:border-[#f59e0b]/50"
          >
            恢复草稿
          </button>
          <button
            onClick={handleDiscard}
            className="flex-1 py-2 rounded-lg text-xs font-medium transition-all active:scale-95
              bg-transparent text-white/40 border border-white/10
              hover:text-white/60 hover:border-white/20"
          >
            丢弃，重新标注
          </button>
        </div>
      </div>
    </div>
  )
}
