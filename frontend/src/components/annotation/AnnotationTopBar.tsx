import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Progress, message } from 'antd';
import useAnnotationStore from '../../store/annotationStore';
import AutoSaveIndicator from './AutoSaveIndicator';

function useTimer() {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(id)
  }, [])
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return `${h > 0 ? h + ':' : ''}${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

interface TopBarProps {
  taskName?: string;
  totalImages?: number;
  currentImage?: number;
  /** 已有标注框的帧数（用于进度条） */
  labeledFrames?: number;
  onPrev?: () => void;
  onNext?: () => void;
  onExport?: () => void;
  saveHint?: string;
  onSubmit?: () => void;
  onManualSave?: () => void;
  /** 项目内任务队列（从项目任务列表进入时） */
  projectTaskIndex?: number;
  projectTaskTotal?: number;
  onPrevTask?: () => void;
  onNextTask?: () => void;
  taskStatusLabel?: string;
  /** 明确返回路径（有 projectId 时应回项目任务列表）；缺省为浏览器后退 */
  backHref?: string;
}

export default function AnnotationTopBar({
  taskName = '任务标注',
  totalImages = 1,
  currentImage = 1,
  labeledFrames = 0,
  onPrev,
  onNext,
  onExport,
  saveHint,
  onSubmit,
  onManualSave,
  projectTaskIndex,
  projectTaskTotal,
  onPrevTask,
  onNextTask,
  taskStatusLabel,
  backHref,
}: TopBarProps) {
  const navigate = useNavigate()
  const { mode, setMode, annotations2d, boxes3d, saveDraft } = useAnnotationStore()
  const timer = useTimer()
  const [submitting, setSubmitting] = useState(false)

  const total = Math.max(1, totalImages)
  const current = Math.min(Math.max(1, currentImage), total)
  const labeled = Math.min(Math.max(0, labeledFrames), total)
  const count2d = annotations2d.length
  const count3d = boxes3d.length
  const completionProgress = Math.round((labeled / total) * 100)
  const canPrevFrame = current > 1
  const canNextFrame = current < total
  const showFrameNav = total > 1
  const showProjectNav =
    projectTaskTotal != null && projectTaskTotal > 1 && onPrevTask && onNextTask
  const projectIdx = (projectTaskIndex ?? 0) + 1

  function handleSubmit() {
    // Save draft before submitting
    saveDraft()
    setSubmitting(true)
    setTimeout(() => {
      setSubmitting(false)
      if (onSubmit) onSubmit()
      else message.success({ content: '标注已提交', className: 'annotation-message' })
    }, 800)
  }

  return (
    <div className="h-12 flex items-center px-4 gap-3 bg-[#12121a] border-b border-[#1e1e2e] flex-shrink-0">
      {/* Back */}
      <button
        type="button"
        onClick={() => (backHref ? navigate(backHref) : navigate(-1))}
        className="flex items-center gap-1.5 text-white/40 hover:text-white/80 transition-colors text-xs"
      >
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
          <path d="M10 12L6 8l4-4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        返回
      </button>

      <div className="w-px h-5 bg-[#1e1e2e]" />

      {/* Task name */}
      <span className="text-white/70 text-sm font-medium truncate max-w-48">{taskName}</span>
      {taskStatusLabel && (
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/5 text-white/40 border border-white/10">
          {taskStatusLabel}
        </span>
      )}

      <div className="w-px h-5 bg-[#1e1e2e]" />

      {/* 2D / 3D mode switch */}
      <div className="flex items-center bg-[#0a0a0f] rounded-lg p-0.5 border border-[#1e1e2e]">
        {(['2d', '3d'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-all
              ${mode === m
                ? 'bg-[#00d4ff]/15 text-[#00d4ff] ring-1 ring-[#00d4ff]/30'
                : 'text-white/30 hover:text-white/60'}`}
          >
            {m.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Annotation counts（当前模式） */}
      <div className="flex items-center gap-1.5 text-xs">
        {mode === '2d' ? (
          <span className="px-2 py-0.5 rounded bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/20">
            当前帧 {count2d} 个框
          </span>
        ) : (
          <span className="px-2 py-0.5 rounded bg-[#7c3aed]/10 text-[#a78bfa] border border-[#7c3aed]/20">
            当前帧 {count3d} 个 3D 框
          </span>
        )}
        <span className="px-2 py-0.5 rounded bg-white/5 text-white/45 border border-white/10">
          已标注 {labeled}/{total} 帧
        </span>
      </div>

      {/* ── Auto-save indicator ── */}
      <AutoSaveIndicator onManualSave={onManualSave} />

      {/* Spacer */}
      <div className="flex-1" />

      {saveHint && (
        <>
          <span className="text-[10px] text-emerald-400/80 max-w-40 truncate" title={saveHint}>
            {saveHint}
          </span>
          <div className="w-px h-5 bg-[#1e1e2e]" />
        </>
      )}

      {showProjectNav && (
        <>
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              disabled={projectIdx <= 1}
              onClick={onPrevTask}
              className="w-7 h-7 rounded flex items-center justify-center text-white/40 hover:text-white/80 hover:bg-white/5 transition-all disabled:opacity-25 disabled:pointer-events-none"
              title="上一条任务"
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
                <path d="M10 12L6 8l4-4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <span className="text-xs text-white/40 font-mono whitespace-nowrap">
              任务 {projectIdx}/{projectTaskTotal}
            </span>
            <button
              type="button"
              disabled={projectIdx >= (projectTaskTotal ?? 1)}
              onClick={onNextTask}
              className="w-7 h-7 rounded flex items-center justify-center text-white/40 hover:text-white/80 hover:bg-white/5 transition-all disabled:opacity-25 disabled:pointer-events-none"
              title="下一条任务"
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
                <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
          <div className="w-px h-5 bg-[#1e1e2e]" />
        </>
      )}

      {/* 帧导航与标注完成进度 */}
      <div className="flex items-center gap-2 min-w-[180px]">
        {showFrameNav && (
          <button
            type="button"
            onClick={onPrev}
            disabled={!canPrevFrame}
            className="w-7 h-7 rounded flex items-center justify-center text-white/40 hover:text-white/80 hover:bg-white/5 transition-all disabled:opacity-25 disabled:pointer-events-none"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
              <path d="M10 12L6 8l4-4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        )}
        <div className="flex items-center gap-2 min-w-32 flex-1">
          <span className="text-xs text-white/40 font-mono whitespace-nowrap">
            {showFrameNav ? `${current}/${total}` : `共 ${total} 张`}
          </span>
          <Progress
            percent={completionProgress}
            showInfo={false}
            size="small"
            strokeColor="#00d4ff"
            trailColor="#1e1e2e"
            className="flex-1 !m-0"
          />
          <span className="text-xs text-white/40 font-mono">{completionProgress}%</span>
        </div>
        {showFrameNav && (
          <button
            type="button"
            onClick={onNext}
            disabled={!canNextFrame}
            className="w-7 h-7 rounded flex items-center justify-center text-white/40 hover:text-white/80 hover:bg-white/5 transition-all disabled:opacity-25 disabled:pointer-events-none"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
              <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        )}
      </div>

      <div className="w-px h-5 bg-[#1e1e2e]" />

      {/* Timer */}
      <div className="flex items-center gap-1.5 text-xs text-white/30 font-mono">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
          <circle cx="8" cy="9" r="6"/>
          <path d="M8 6v3l2 1.5" strokeLinecap="round"/>
          <path d="M6 2h4M8 2v1" strokeLinecap="round"/>
        </svg>
        {timer}
      </div>

      <div className="w-px h-5 bg-[#1e1e2e]" />

      {/* Export */}
      <button
        onClick={onExport}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border border-white/10 text-white/40 hover:text-white/70 hover:border-white/20 transition-all"
      >
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
          <path d="M8 2v8M5 7l3 3 3-3" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M2 12v1a1 1 0 001 1h10a1 1 0 001-1v-1" strokeLinecap="round"/>
        </svg>
        导出
      </button>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={submitting}
        className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium transition-all
          ${submitting
            ? 'bg-[#00d4ff]/10 text-[#00d4ff]/40 cursor-not-allowed'
            : 'bg-[#00d4ff]/15 text-[#00d4ff] border border-[#00d4ff]/30 hover:bg-[#00d4ff]/25 active:scale-95'}`}
      >
        {submitting
          ? <span className="w-3 h-3 border border-[#00d4ff]/40 border-t-[#00d4ff] rounded-full animate-spin" />
          : <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
              <path d="M2 8l4 4 8-8" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>}
        提交
      </button>
    </div>
  )
}
