import { useState } from 'react'
import useAnnotationStore, { AnnotationDraft } from '../../store/annotationStore'

interface Props {
  taskId: string
  currentImageIndex?: number
  onLoad?: (draft: AnnotationDraft) => void
}

export default function DraftListPanel({ taskId, currentImageIndex, onLoad }: Props) {
  const { drafts, loadDraft, deleteDraft, clearAllDrafts, getDraftList, autoSaveMeta } =
    useAnnotationStore()
  const [confirmClear, setConfirmClear] = useState(false)

  const taskDrafts = getDraftList().filter(d => d.taskId === taskId)

  function formatTime(iso: string) {
    const d = new Date(iso)
    const diff = Date.now() - d.getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return '刚刚'
    if (mins < 60) return `${mins} 分钟前`
    if (mins < 1440) return `${Math.floor(mins / 60)} 小时前`
    return d.toLocaleString('zh-CN', {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  function handleLoad(draft: AnnotationDraft) {
    loadDraft(draft.taskId, draft.imageIndex)
    onLoad?.(draft)
  }

  if (taskDrafts.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center mx-auto mb-3">
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5 text-white/20">
            <path d="M4 4h12v12H4V4zM8 4v4h4V4M7 13h6" strokeLinecap="round"/>
          </svg>
        </div>
        <div className="text-xs text-white/20">暂无保存的草稿</div>
        <div className="text-[10px] text-white/10 mt-1">Ctrl+S 手动保存，或等待自动保存</div>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] text-white/30 uppercase tracking-widest">
          草稿历史 ({taskDrafts.length})
        </span>
        {autoSaveMeta.lastSavedAt && (
          <span className="text-[10px] text-[#10b981]/70 truncate max-w-[120px]" title={autoSaveMeta.lastSavedAt}>
            最近 {formatTime(autoSaveMeta.lastSavedAt)}
          </span>
        )}
      </div>

      {confirmClear ? (
        <div className="flex items-center gap-1.5 text-[10px] px-2 py-1 rounded bg-red-500/5 border border-red-500/20">
          <span className="text-white/40">确认清空本任务草稿？</span>
          <button
            type="button"
            onClick={() => { clearAllDrafts(taskId); setConfirmClear(false) }}
            className="text-red-400 hover:text-red-300"
          >是</button>
          <button
            type="button"
            onClick={() => setConfirmClear(false)}
            className="text-white/30 hover:text-white/50"
          >否</button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirmClear(true)}
          className="text-[10px] text-white/20 hover:text-red-400 transition-colors"
        >
          清空本任务草稿
        </button>
      )}

      {taskDrafts.map((draft) => {
        const isCurrent =
          currentImageIndex !== undefined && draft.imageIndex === currentImageIndex
        return (
          <div
            key={`${draft.taskId}:${draft.imageIndex}`}
            className={`bg-[#0a0a0f] border rounded-lg p-2.5 group transition-all
              ${isCurrent
                ? 'border-[#00d4ff]/40 ring-1 ring-[#00d4ff]/15'
                : 'border-[#1e1e2e] hover:border-white/15'}`}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-[10px] text-white/40 font-mono">帧 #{draft.imageIndex + 1}</span>
                {isCurrent && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/20">
                    当前帧
                  </span>
                )}
                {draft.isSubmitted && (
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/20">
                    已提交
                  </span>
                )}
              </div>
              <span className="text-[10px] text-white/25 shrink-0">{formatTime(draft.savedAt)}</span>
            </div>

            <div className="flex gap-1.5 mb-2.5 flex-wrap">
              {draft.annotations2d.length > 0 && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#00d4ff]/10 text-[#00d4ff]/70 border border-[#00d4ff]/15">
                  2D×{draft.annotations2d.length}
                </span>
              )}
              {draft.boxes3d.length > 0 && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#a78bfa]/10 text-[#a78bfa]/70 border border-[#a78bfa]/15">
                  3D×{draft.boxes3d.length}
                </span>
              )}
              {draft.annotations2d.length === 0 && draft.boxes3d.length === 0 && (
                <span className="text-[10px] text-white/20">空草稿</span>
              )}
            </div>

            <div className="flex gap-1.5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
              <button
                type="button"
                onClick={() => handleLoad(draft)}
                className="flex-1 py-1 rounded text-[11px] bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/20
                  hover:bg-[#00d4ff]/20 active:scale-95 transition-all"
              >
                恢复
              </button>
              <button
                type="button"
                onClick={() => deleteDraft(draft.taskId, draft.imageIndex)}
                className="px-2.5 py-1 rounded text-[11px] text-white/30 border border-white/10
                  hover:text-red-400 hover:border-red-500/20 active:scale-95 transition-all"
              >
                删除
              </button>
            </div>
          </div>
        )
      })}
    </div>
  )
}
