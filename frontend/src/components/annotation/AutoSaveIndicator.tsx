import { useEffect, useState } from 'react'
import useAnnotationStore from '../../store/annotationStore'
import { notifyDraftSaved } from '../../utils/draftSaveNotify'

// ─── AutoSaveIndicator ────────────────────────────────────────────────────────
// 顶部状态栏里的自动保存状态显示；「保存草稿」始终可见

interface Props {
  /** 2D/3D 等自定义保存逻辑 */
  onManualSave?: () => void
}

export default function AutoSaveIndicator({ onManualSave }: Props) {
  const { autoSaveMeta, saveDraft } = useAnnotationStore()
  const { isDirty, lastSavedAt, saveCount } = autoSaveMeta
  const [justSaved, setJustSaved] = useState(false)

  useEffect(() => {
    if (saveCount === 0) return
    setJustSaved(true)
    const t = setTimeout(() => setJustSaved(false), 2000)
    return () => clearTimeout(t)
  }, [saveCount])

  function formatTime(iso: string | null) {
    if (!iso) return ''
    const d = new Date(iso)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  function handleSave() {
    if (onManualSave) onManualSave()
    else {
      saveDraft()
      notifyDraftSaved()
    }
  }

  return (
    <div className="flex items-center gap-1.5">
      {isDirty ? (
        <span className="w-1.5 h-1.5 rounded-full bg-[#f59e0b] animate-pulse" title="有未保存的修改" />
      ) : (
        <span className="w-1.5 h-1.5 rounded-full bg-[#10b981]" title="已保存" />
      )}

      <span className="text-[11px] text-white/30 font-mono">
        {isDirty
          ? '未保存'
          : justSaved
            ? <span className="text-[#10b981]/80">已保存</span>
            : lastSavedAt
              ? `${formatTime(lastSavedAt)}`
              : '–'}
      </span>

      <button
        type="button"
        onClick={handleSave}
        className={`ml-1 flex items-center gap-1 px-2 py-0.5 rounded text-[11px] border transition-all active:scale-95
          ${isDirty
            ? 'bg-[#f59e0b]/10 border-[#f59e0b]/30 text-[#f59e0b] hover:bg-[#f59e0b]/20'
            : 'bg-white/5 border-white/10 text-white/45 hover:text-white/70 hover:border-white/20'}`}
        title="Ctrl+S 保存草稿"
      >
        <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3 h-3">
          <path d="M2 2h8l2 2v8a1 1 0 01-1 1H3a1 1 0 01-1-1V2z" strokeLinejoin="round"/>
          <path d="M5 2v4h4V2M4 10h6" strokeLinecap="round"/>
        </svg>
        保存草稿
      </button>
    </div>
  )
}
