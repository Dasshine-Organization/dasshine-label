import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { message } from 'antd'
import {
  DEFAULT_ACTION_LABELS,
  type ActionLabelDef,
  type FrameAnnotation,
  buildExportPayload,
  frameToTimeSec,
  getEpisodeForTaskId,
  jointStatesForFrame,
  timeSecToFrame,
} from '../mocks/embodiedDemoData'

export default function EmbodiedAnnotation() {
  const { taskId = 'demo' } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const episode = useMemo(() => getEpisodeForTaskId(taskId), [taskId])
  const { streams, totalFrames, clipDurationSec, attribution } = episode

  const [frame, setFrame] = useState(0)
  /** 逐帧顺序播放（离散帧） */
  const [stepPlaying, setStepPlaying] = useState(false)
  /** 连续播放真实时间轴（0～clipDurationSec） */
  const [continuous, setContinuous] = useState(false)
  const [labels, setLabels] = useState<ActionLabelDef[]>(() => [...DEFAULT_ACTION_LABELS])
  const [frameActions, setFrameActions] = useState<Record<number, FrameAnnotation>>({})
  const [committedFrames, setCommittedFrames] = useState<Set<number>>(() => new Set())
  const [newLabelText, setNewLabelText] = useState('')
  const playRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const videoRefs = useRef<(HTMLVideoElement | null)[]>([])
  const frameRef = useRef(0)
  const continuousRef = useRef(false)
  /** 主路 video 就绪后重挂连续播放 effect（解决首帧 ref 尚未挂载） */
  const [leaderTick, setLeaderTick] = useState(0)
  const leaderBumped = useRef(false)
  /** 某路视频在首选失败后是否已切到 fallbackSrc */
  const [videoSrcOverride, setVideoSrcOverride] = useState<Record<string, string>>({})
  /** 两路 URL 均失败 */
  const [failedStreamIds, setFailedStreamIds] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    leaderBumped.current = false
    setVideoSrcOverride({})
    setFailedStreamIds(new Set())
    setLabels([...DEFAULT_ACTION_LABELS])
    setCommittedFrames(new Set())
    setFrame(0)
    setStepPlaying(false)
    setContinuous(false)
    setFrameActions(
      Object.fromEntries(
        Array.from({ length: episode.totalFrames }, (_, i) => [i, { actionId: 'idle' }]),
      ) as Record<number, FrameAnnotation>,
    )
  }, [taskId, episode.totalFrames])

  useEffect(() => {
    frameRef.current = frame
  }, [frame])

  useEffect(() => {
    continuousRef.current = continuous
  }, [continuous])


  const currentAnn = frameActions[frame] ?? { actionId: 'idle' }
  const joints = useMemo(() => jointStatesForFrame(frame, totalFrames), [frame, totalFrames])

  const seekAllToFrame = useCallback(
    (frameIdx: number) => {
      const t = frameToTimeSec(frameIdx, episode)
      videoRefs.current.forEach(v => {
        if (!v) return
        try {
          if (Number.isFinite(t) && Math.abs(v.currentTime - t) > 0.03) {
            v.currentTime = t
          }
        } catch {
          /* seek in progress */
        }
      })
    },
    [episode],
  )

  useEffect(() => {
    videoRefs.current.length = streams.length
  }, [streams.length])

  useEffect(() => {
    if (continuous) return
    seekAllToFrame(frame)
  }, [frame, seekAllToFrame, continuous])

  useEffect(() => {
    if (!stepPlaying || continuous) {
      if (playRef.current) clearInterval(playRef.current)
      playRef.current = null
      return
    }
    const ms = Math.max(60, Math.round((clipDurationSec * 1000) / totalFrames))
    playRef.current = setInterval(() => {
      setFrame(f => (f + 1 >= totalFrames ? 0 : f + 1))
    }, ms)
    return () => {
      if (playRef.current) clearInterval(playRef.current)
    }
  }, [stepPlaying, totalFrames, clipDurationSec, continuous])

  /** 连续播放：多路 video 同步主路时间（依赖中不含 frame，避免每帧重建监听） */
  useEffect(() => {
    if (!continuous) {
      videoRefs.current.forEach(v => v?.pause())
      return
    }
    setStepPlaying(false)
    const master = videoRefs.current[0]
    if (!master) return

    const t0 = frameToTimeSec(frameRef.current, episode)
    videoRefs.current.forEach(v => {
      if (!v) return
      try {
        v.currentTime = t0
      } catch {
        /* */
      }
      v.play().catch(() => {})
    })

    const onTime = () => {
      const m = videoRefs.current[0]
      if (!m) return
      const t = m.currentTime
      if (t >= clipDurationSec - 0.02) {
        videoRefs.current.forEach(v => {
          if (!v) return
          v.pause()
          try {
            v.currentTime = clipDurationSec
          } catch {
            /* */
          }
        })
        setContinuous(false)
        setFrame(totalFrames - 1)
        return
      }
      const f = timeSecToFrame(t, episode)
      setFrame(f)
      videoRefs.current.forEach((v, i) => {
        if (!v || i === 0) return
        if (Math.abs(v.currentTime - t) > 0.1) {
          try {
            v.currentTime = t
          } catch {
            /* */
          }
        }
      })
    }
    master.addEventListener('timeupdate', onTime)
    return () => {
      master.removeEventListener('timeupdate', onTime)
      videoRefs.current.forEach(v => v?.pause())
    }
  }, [continuous, episode, clipDurationSec, totalFrames, leaderTick])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'ArrowLeft') {
        e.preventDefault()
        setFrame(f => Math.max(0, f - 1))
        setStepPlaying(false)
        setContinuous(false)
      }
      if (e.key === 'ArrowRight') {
        e.preventDefault()
        setFrame(f => Math.min(totalFrames - 1, f + 1))
        setStepPlaying(false)
        setContinuous(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [totalFrames])

  const patchCurrent = useCallback((patch: Partial<FrameAnnotation>) => {
    setFrameActions(prev => {
      const cur = prev[frame] ?? { actionId: 'idle' }
      return { ...prev, [frame]: { ...cur, ...patch } }
    })
  }, [frame])

  const addLabel = useCallback(() => {
    const text = newLabelText.trim()
    if (!text) {
      message.warning('请输入标签名称')
      return
    }
    if (labels.some(l => l.label === text)) {
      message.warning('已存在同名标签')
      return
    }
    const id = `act_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
    setLabels(prev => [...prev, { id, label: text }])
    setNewLabelText('')
    message.success('已添加动作标签')
  }, [newLabelText, labels])

  const deleteLabel = useCallback(
    (id: string) => {
      if (id === 'idle') {
        message.warning('「待机」为保留标签，不可删除')
        return
      }
      setLabels(prev => prev.filter(l => l.id !== id))
      setFrameActions(prev => {
        const next = { ...prev }
        for (let i = 0; i < totalFrames; i++) {
          if (next[i]?.actionId === id) {
            next[i] = { ...next[i], actionId: 'idle' }
          }
        }
        return next
      })
      message.success('已删除标签，相关帧已回退为「待机」')
    },
    [totalFrames],
  )

  const updateLabelText = useCallback((id: string, label: string) => {
    const t = label.trim()
    if (!t) return
    setLabels(prev => prev.map(l => (l.id === id ? { ...l, label: t } : l)))
  }, [])

  const commitCurrentFrame = useCallback(() => {
    setCommittedFrames(prev => {
      const n = new Set(prev)
      n.add(frame)
      return n
    })
    message.success(`已保存第 ${frame} 帧标注`)
  }, [frame])

  const uncommitCurrentFrame = useCallback(() => {
    setCommittedFrames(prev => {
      const n = new Set(prev)
      n.delete(frame)
      return n
    })
    message.info(`已取消第 ${frame} 帧的「已保存」标记`)
  }, [frame])

  const exportJson = useCallback(() => {
    const payload = buildExportPayload(
      taskId,
      frameActions,
      episode,
      labels,
      [...committedFrames].sort((a, b) => a - b),
    )
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `embodied_${taskId}_${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(a.href)
    message.success('已导出 JSON')
  }, [frameActions, taskId, episode, labels, committedFrames])

  const exportTorqueCsv = useCallback(() => {
    const rows = ['frame_index,timestamp_ms,joint,torque_nm']
    for (let i = 0; i < totalFrames; i++) {
      const ts = Math.round((i / Math.max(1, totalFrames - 1)) * clipDurationSec * 1000)
      for (const j of jointStatesForFrame(i, totalFrames)) {
        rows.push(`${i},${ts},${j.name},${j.torque_nm}`)
      }
    }
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `embodied_torque_${taskId}_${Date.now()}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
    message.success('已导出扭矩 CSV')
  }, [taskId, totalFrames, clipDurationSec])

  const toggleContinuous = useCallback(() => {
    setContinuous(c => {
      if (!c) setStepPlaying(false)
      return !c
    })
  }, [])

  const toggleStepPlay = useCallback(() => {
    setStepPlaying(p => {
      if (!p) setContinuous(false)
      return !p
    })
  }, [])

  return (
    <div className="flex flex-col gap-6 p-4 md:p-8 pb-14 text-white/90 w-full max-w-[1920px] mx-auto">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1e1e2e] pb-4">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="text-xs px-2.5 py-1.5 rounded-lg border border-[#1e1e2e] text-white/50 hover:text-white/80 hover:border-white/20 transition-all"
          >
            ← 工作台
          </button>
          <div className="min-w-0">
            <div className="text-[10px] text-white/35 uppercase tracking-wider">
              具身标注 · {episode.caseId === 'aloha' ? '多机位真实流' : '视频 mock'}
            </div>
            <h1 className="text-sm md:text-base font-semibold text-white/90 truncate">{episode.projectName}</h1>
            <div className="text-[11px] text-white/35 font-mono mt-0.5">
              task #{taskId} · {streams.length} 路 · 前 {clipDurationSec}s / {totalFrames} 帧 · 已保存{' '}
              {committedFrames.size}/{totalFrames}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={toggleStepPlay}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-all
              ${stepPlaying ? 'bg-[#f97316]/15 text-[#f97316] border-[#f97316]/35' : 'border-[#1e1e2e] text-white/50 hover:border-white/20'}`}
          >
            {stepPlaying ? '暂停逐帧' : '逐帧播放'}
          </button>
          <button
            type="button"
            onClick={toggleContinuous}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-all
              ${continuous ? 'bg-[#10b981]/15 text-[#10b981] border-[#10b981]/35' : 'border-[#1e1e2e] text-white/50 hover:border-white/20'}`}
          >
            {continuous ? '停止连续播放' : '连续播放'}
          </button>
          <button
            type="button"
            onClick={exportJson}
            className="text-xs px-3 py-1.5 rounded-lg bg-[#f97316]/15 text-[#f97316] border border-[#f97316]/30 hover:bg-[#f97316]/25 transition-all"
          >
            导出 JSON
          </button>
          <button
            type="button"
            onClick={exportTorqueCsv}
            className="text-xs px-3 py-1.5 rounded-lg border border-[#1e1e2e] text-white/60 hover:border-[#00d4ff]/40 hover:text-[#00d4ff] transition-all"
          >
            导出扭矩 CSV
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-8 xl:gap-10 items-start w-full">
        <section className="xl:col-span-8 min-w-0 space-y-4">
          <div className="text-[11px] text-white/40 uppercase tracking-widest">
            多路视角（{streams.length} 路 · 宽松布局）
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 lg:gap-8 w-full">
            {streams.map((stream, i) => {
              const effectiveSrc = videoSrcOverride[stream.id] ?? stream.src
              const failed = failedStreamIds.has(stream.id)
              return (
              <div
                key={stream.id}
                className="rounded-2xl overflow-hidden border border-[#1e1e2e] bg-[#12121a] shadow-lg flex flex-col min-w-0"
              >
                <div className="flex items-center justify-between px-3 py-2.5 border-b border-[#1e1e2e] bg-[#0a0a0f] gap-2">
                  <span className="text-xs text-[#f97316]/90 font-medium truncate">{stream.label}</span>
                  <span className="text-[10px] text-white/25 font-mono flex-shrink-0">
                    f{frame} · {frameToTimeSec(frame, episode).toFixed(2)}s
                  </span>
                </div>
                <div className="relative w-full aspect-video overflow-hidden bg-black min-h-[180px]">
                  <video
                    key={`${stream.id}-${effectiveSrc}`}
                    ref={el => {
                      videoRefs.current[i] = el
                    }}
                    src={effectiveSrc}
                    muted
                    playsInline
                    preload="metadata"
                    className={`h-full w-full object-cover transition-opacity duration-200 ${failed ? 'opacity-25' : 'opacity-100'}`}
                    style={{
                      objectPosition: stream.objectPosition ?? '50% 50%',
                      transform: stream.scale && stream.scale !== 1 ? `scale(${stream.scale})` : undefined,
                      transformOrigin: 'center center',
                    }}
                    onLoadedData={() => {
                      setFailedStreamIds(prev => {
                        if (!prev.has(stream.id)) return prev
                        const n = new Set(prev)
                        n.delete(stream.id)
                        return n
                      })
                      if (i === 0 && !leaderBumped.current) {
                        leaderBumped.current = true
                        setLeaderTick(t => t + 1)
                      }
                      if (!continuousRef.current) seekAllToFrame(frameRef.current)
                    }}
                    onError={() => {
                      const usingPrimary = effectiveSrc === stream.src
                      if (stream.fallbackSrc && usingPrimary) {
                        setVideoSrcOverride(prev => ({ ...prev, [stream.id]: stream.fallbackSrc! }))
                        return
                      }
                      setFailedStreamIds(prev => new Set(prev).add(stream.id))
                    }}
                  />
                  {failed && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-4 bg-black/75 text-center">
                      <p className="text-xs text-white/85 font-medium">「{stream.label}」无法加载</p>
                      <p className="text-[10px] text-white/45 leading-relaxed">
                        已尝试主地址与镜像。多为网络超时或浏览器不支持 AV1。
                        请在 <span className="font-mono text-[#00d4ff]/90">src/mocks/embodiedDemoData.ts</span> 中替换该路的{' '}
                        <span className="font-mono">src</span> / <span className="font-mono">fallbackSrc</span>。
                      </p>
                    </div>
                  )}
                  {!failed && (
                    <div className="absolute bottom-2 left-2 right-2 flex justify-between text-[10px] text-white/70 font-mono pointer-events-none drop-shadow-md">
                      <span>{continuous ? '连续播放中' : 'scrub 同步'}</span>
                      <span>{(frame / Math.max(1, totalFrames - 1) * 100).toFixed(0)}%</span>
                    </div>
                  )}
                </div>
              </div>
              )
            })}
          </div>
          <p className="text-[10px] text-white/30 leading-relaxed">
            片源：
            <a href={attribution.detailUrl} className="text-[#00d4ff]/80 hover:underline" target="_blank" rel="noreferrer">
              {attribution.title}
            </a>
            。{attribution.note}
          </p>
        </section>

        <section className="xl:col-span-4 min-w-0 flex flex-col gap-5">
          <div className="rounded-xl border border-[#1e1e2e] bg-[#12121a] p-4 space-y-3">
            <div className="text-[11px] text-white/40 uppercase tracking-widest">动作标签库</div>
            <p className="text-[10px] text-white/25">可添加、修改文案、删除（「待机」不可删）。下拉框与导出均使用此处定义。</p>
            <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
              {labels.map(l => (
                <div key={l.id} className="flex items-center gap-2">
                  <input
                    value={l.label}
                    onChange={e => updateLabelText(l.id, e.target.value)}
                    className="flex-1 min-w-0 bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-2 py-1.5 text-xs text-white
                      focus:outline-none focus:border-[#f97316]/40"
                  />
                  <span className="text-[9px] text-white/20 font-mono truncate max-w-[72px]" title={l.id}>
                    {l.id}
                  </span>
                  {l.id !== 'idle' && (
                    <button
                      type="button"
                      onClick={() => deleteLabel(l.id)}
                      className="text-[10px] px-2 py-1 rounded border border-red-500/30 text-red-400/90 hover:bg-red-500/10 flex-shrink-0"
                    >
                      删
                    </button>
                  )}
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <input
                value={newLabelText}
                onChange={e => setNewLabelText(e.target.value)}
                placeholder="新动作名称…"
                className="flex-1 bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-xs text-white placeholder-white/25 focus:outline-none focus:border-[#f97316]/40"
                onKeyDown={e => e.key === 'Enter' && addLabel()}
              />
              <button
                type="button"
                onClick={addLabel}
                className="text-xs px-3 py-2 rounded-lg border border-[#10b981]/40 text-[#10b981] hover:bg-[#10b981]/10 flex-shrink-0"
              >
                添加
              </button>
            </div>
          </div>

          <div className="rounded-xl border border-[#1e1e2e] bg-[#12121a] p-4 space-y-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] text-white/40 uppercase tracking-widest">逐帧标注</span>
              <span className="text-[10px] text-white/25">← → 切帧</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={commitCurrentFrame}
                className="text-xs px-3 py-1.5 rounded-lg bg-[#10b981]/15 text-[#10b981] border border-[#10b981]/35 hover:bg-[#10b981]/25"
              >
                保存本帧标注
              </button>
              <button
                type="button"
                disabled={!committedFrames.has(frame)}
                onClick={uncommitCurrentFrame}
                className="text-xs px-3 py-1.5 rounded-lg border border-[#1e1e2e] text-white/45 hover:border-white/25 disabled:opacity-30"
              >
                取消已保存标记
              </button>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={frame <= 0}
                onClick={() => {
                  setStepPlaying(false)
                  setContinuous(false)
                  setFrame(f => f - 1)
                }}
                className="px-2 py-1 rounded-lg border border-[#1e1e2e] text-white/50 disabled:opacity-30 hover:border-white/25"
              >
                上一帧
              </button>
              <input
                type="range"
                min={0}
                max={totalFrames - 1}
                value={frame}
                onChange={e => {
                  setStepPlaying(false)
                  setContinuous(false)
                  setFrame(Number(e.target.value))
                }}
                className="flex-1 accent-[#f97316]"
              />
              <button
                type="button"
                disabled={frame >= totalFrames - 1}
                onClick={() => {
                  setStepPlaying(false)
                  setContinuous(false)
                  setFrame(f => f + 1)
                }}
                className="px-2 py-1 rounded-lg border border-[#1e1e2e] text-white/50 disabled:opacity-30 hover:border-white/25"
              >
                下一帧
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Array.from({ length: totalFrames }).map((_, i) => {
                const saved = committedFrames.has(i)
                const current = i === frame
                return (
                  <button
                    key={i}
                    type="button"
                    title={saved ? '已保存标注' : '未保存'}
                    onClick={() => {
                      setStepPlaying(false)
                      setContinuous(false)
                      setFrame(i)
                    }}
                    className={`relative w-8 h-8 rounded-md text-[10px] font-mono border transition-all
                      ${current ? 'ring-2 ring-[#f97316] ring-offset-1 ring-offset-[#12121a] border-[#f97316]/60 text-[#f97316] z-10' : 'border-[#1e1e2e] text-white/40'}
                      ${saved ? 'bg-[#10b981]/25 border-[#10b981]/55 text-[#a7f3d0] shadow-[0_0_10px_rgba(16,185,129,0.35)]' : ''}
                      ${!saved && !current ? 'hover:border-white/25' : ''}`}
                  >
                    {i}
                    {saved && (
                      <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-[#10b981] border border-[#12121a]" />
                    )}
                  </button>
                )
              })}
            </div>
            <p className="text-[10px] text-white/25">
              绿色高亮 + 角标 = 已点击「保存本帧标注」的帧；当前帧为橙色描边。
            </p>
            <label className="block text-[11px] text-white/40 mb-1">当前帧动作</label>
            <select
              value={labels.some(l => l.id === currentAnn.actionId) ? currentAnn.actionId : 'idle'}
              onChange={e => patchCurrent({ actionId: e.target.value })}
              className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#f97316]/40"
            >
              {labels.map(a => (
                <option key={a.id} value={a.id}>{a.label}</option>
              ))}
            </select>
            <label className="block text-[11px] text-white/40 mb-1">备注</label>
            <textarea
              value={currentAnn.note ?? ''}
              onChange={e => patchCurrent({ note: e.target.value })}
              rows={2}
              placeholder="可选：接触力、异常等"
              className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 resize-none focus:outline-none focus:border-[#f97316]/40"
            />
          </div>

          <div className="rounded-xl border border-[#1e1e2e] bg-[#12121a] overflow-hidden flex-1 min-h-[200px]">
            <div className="px-3 py-2 border-b border-[#1e1e2e] flex items-center justify-between bg-[#0a0a0f]">
              <span className="text-[11px] text-white/40 uppercase tracking-widest">关节状态（mock）</span>
              <span className="text-[10px] text-white/25">rad / N·m</span>
            </div>
            <div className="overflow-x-auto max-h-[280px] overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-[#12121a]">
                  <tr className="text-left text-white/35 border-b border-[#1e1e2e]">
                    <th className="px-3 py-2 font-medium">关节</th>
                    <th className="px-3 py-2 font-mono">θ (rad)</th>
                    <th className="px-3 py-2 font-mono">τ (N·m)</th>
                  </tr>
                </thead>
                <tbody>
                  {joints.map(j => (
                    <tr key={j.name} className="border-b border-[#1e1e2e]/60 hover:bg-white/[0.02]">
                      <td className="px-3 py-2 text-white/70 font-mono">{j.name}</td>
                      <td className="px-3 py-2 font-mono text-[#00d4ff]/90">{j.position_rad}</td>
                      <td className="px-3 py-2 font-mono text-[#a78bfa]/90">{j.torque_nm}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
