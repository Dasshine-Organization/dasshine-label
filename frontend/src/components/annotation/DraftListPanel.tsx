import { useState } from 'react'
import useAnnotationStore, { AnnotationDraft } from '../../store/annotationStore'

// ─── DraftListPanel ───────────────────────────────────────────────────────────
// 右侧面板中的草稿历史列表

interface Props {
  taskId: string
  onLoad?: (draft: AnnotationDraft) => void
}

export default function DraftListPanel({ taskId, onLoad }: Props) {
  const { drafts, loadDraft, deleteDraft, clearAllDrafts, getDraftList } = useAnnotationStore()
  const [confirmClear, setConfirmClear] = useState(false)

  // Get drafts for this task only
  const taskDrafts = getDraftList().filter(d => d.taskId === taskId)

  function formatTime(iso: string) {
    const d = new Date(iso)
    const diff = Date.now() - d.getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return '刚刚'
    if (mins < 60) return `${mins} 分钟前`
    if (mins < 1440) return `${Math.floor(mins / 60)} 小时前`
    return d.toLocaleDateString('zh-CN')
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
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-white/30 uppercase tracking-widest">草稿历史</span>
        {taskDrafts.length > 0 && (
          confirmClear ? (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-white/30">确认清空？</span>
              <button
                onClick={() => { clearAllDrafts(); setConfirmClear(false) }}
                className="text-[10px] text-red-400 hover:text-red-300"
              >是</button>
              <button
                onClick={() => setConfirmClear(false)}
                className="text-[10px] text-white/30 hover:text-white/50"
              >否</button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmClear(true)}
              className="text-[10px] text-white/20 hover:text-red-400 transition-colors"
            >
              清空
            </button>
          )
        )}
      </div>

      {taskDrafts.map((draft) => (
        <div
          key={`${draft.taskId}:${draft.imageIndex}`}
          className="bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg p-2.5 group hover:border-white/15 transition-all"
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-white/40 font-mono">帧 #{draft.imageIndex + 1}</span>
              {draft.isSubmitted && (
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#10b981]/10 text-[#10b981] border border-[#10b981]/20">
                  已提交
                </span>
              )}
            </div>
            <span className="text-[10px] text-white/20">{formatTime(draft.savedAt)}</span>
          </div>

          {/* Annotation counts */}
          <div className="flex gap-1.5 mb-2.5">
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

          {/* Actions */}
          <div className="flex gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => handleLoad(draft)}
              className="flex-1 py-1 rounded text-[11px] bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/20
                hover:bg-[#00d4ff]/20 active:scale-95 transition-all"
            >
              恢复
            </button>
            <button
              onClick={() => deleteDraft(draft.taskId, draft.imageIndex)}
              className="px-2.5 py-1 rounded text-[11px] text-white/30 border border-white/10
                hover:text-red-400 hover:border-red-500/20 active:scale-95 transition-all"
            >
              删除
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
