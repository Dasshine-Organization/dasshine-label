import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { message } from 'antd'
import {
  DEFAULT_ACTION_LABELS,
  type ActionLabelDef,
  type EmbodiedDemoEpisode,
  type FrameAnnotation,
  buildExportPayload,
  frameToTimeSec,
  getEpisodeForTaskId,
  jointStatesForFrame,
  forceWrenchForFrame,
  tactileForFrame,
  timeSecToFrame,
} from '../mocks/embodiedDemoData'
import {
  embodiedApi,
  type ActionSegment,
  type GraspPose,
  type PreferencePair,
  type TrajectoryPoint,
} from '../services/embodied'
import ProjectExportMenu from '../components/dataset/ProjectExportMenu'
import EmbodiedPose3DViewer from '../components/embodied/EmbodiedPose3DViewer'
import CollabPresenceBar from '../components/CollabPresenceBar'
import useAuthStore from '../store/authStore'
import { useYjsCollab } from '../hooks/useYjsCollab'
import { notifyDraftSaved } from '../utils/draftSaveNotify'
import { getAnnotateBackHref, isDemoTaskId } from '../utils/annotationRoutes'

function downloadBlob(blob: Blob, filename: string) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}

type EmbodiedLocalDraft = {
  action_labels: ActionLabelDef[]
  frame_actions: Record<number, FrameAnnotation>
  committed_frames: number[]
  instruction?: string
  success?: 'success' | 'fail' | 'unknown'
  segments?: ActionSegment[]
  savedAt: string
}

function embodiedDraftKey(taskId: string) {
  return `dasshine_embodied_draft_${taskId}`
}

function readEmbodiedLocalDraft(taskId: string): EmbodiedLocalDraft | null {
  try {
    const raw = localStorage.getItem(embodiedDraftKey(taskId))
    if (!raw) return null
    const data = JSON.parse(raw) as EmbodiedLocalDraft
    if (data && data.frame_actions) return data
  } catch {
    /* ignore */
  }
  return null
}

function writeEmbodiedLocalDraft(
  taskId: string,
  labels: ActionLabelDef[],
  frameActions: Record<number, FrameAnnotation>,
  committedFrames: Set<number>,
  instruction = '',
  success: 'success' | 'fail' | 'unknown' = 'unknown',
  segments: ActionSegment[] = [],
): string {
  const savedAt = new Date().toISOString()
  try {
    localStorage.setItem(
      embodiedDraftKey(taskId),
      JSON.stringify({
        action_labels: labels,
        frame_actions: frameActions,
        committed_frames: [...committedFrames].sort((a, b) => a - b),
        instruction,
        success,
        segments,
        savedAt,
      } satisfies EmbodiedLocalDraft),
    )
  } catch {
    /* quota */
  }
  return savedAt
}

export default function EmbodiedAnnotation() {
  const { taskId = 'demo' } = useParams<{ taskId: string }>()
  const [searchParams] = useSearchParams()
  const projectIdParam = searchParams.get('projectId')
  const navigate = useNavigate()
  const { token } = useAuthStore()
  const demoOnly = isDemoTaskId(taskId)
  const mockEpisode = useMemo(() => getEpisodeForTaskId(taskId), [taskId])
  const [episode, setEpisode] = useState<EmbodiedDemoEpisode>(mockEpisode)
  const [useBackend, setUseBackend] = useState(false)
  const [hydrated, setHydrated] = useState(false)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dirtyRef = useRef(false)
  const { streams, totalFrames, clipDurationSec, attribution } = episode

  const backHref = getAnnotateBackHref({
    projectId: projectIdParam,
    category: 'embodied',
  })

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
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null)
  const [savingDraft, setSavingDraft] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [instruction, setInstruction] = useState('')
  const [success, setSuccess] = useState<'success' | 'fail' | 'unknown'>('unknown')
  const [segments, setSegments] = useState<ActionSegment[]>([])
  const [grasps, setGrasps] = useState<GraspPose[]>([])
  const [trajectory, setTrajectory] = useState<TrajectoryPoint[]>([])
  const [preferences, setPreferences] = useState<PreferencePair[]>([])
  const [prelabeling, setPrelabeling] = useState(false)
  const [selectedGraspId, setSelectedGraspId] = useState<string | null>(null)
  const [policyActive, setPolicyActive] = useState<string | null>(null)
  const [segStart, setSegStart] = useState<number | null>(null)

  useEffect(() => {
    setEpisode(mockEpisode)
    setUseBackend(false)
    setHydrated(false)
  }, [taskId, mockEpisode])

  useEffect(() => {
    if (!token || demoOnly) {
      const local = readEmbodiedLocalDraft(taskId)
      if (local) {
        setLabels(local.action_labels?.length ? local.action_labels : [...DEFAULT_ACTION_LABELS])
        setCommittedFrames(new Set(local.committed_frames ?? []))
        setFrameActions(local.frame_actions)
        setInstruction(local.instruction || '')
        setSuccess(local.success || 'unknown')
        setSegments(local.segments || [])
        setLastSavedAt(local.savedAt)
      } else {
        setLabels([...DEFAULT_ACTION_LABELS])
        setCommittedFrames(new Set())
        setInstruction(mockEpisode.instruction || '')
        setSuccess(mockEpisode.success || 'unknown')
        setSegments([])
        setFrameActions(
          Object.fromEntries(
            Array.from({ length: mockEpisode.totalFrames }, (_, i) => [i, { actionId: 'idle' }]),
          ) as Record<number, FrameAnnotation>,
        )
      }
      setUseBackend(false)
      setHydrated(true)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const [ep, ws] = await Promise.all([
          embodiedApi.getEpisode(taskId),
          embodiedApi.getWorkspace(taskId),
        ])
        if (cancelled) return
        setEpisode(ep)
        setUseBackend(true)
        const local = readEmbodiedLocalDraft(taskId)
        const serverHasWork =
          (ws.committed_frames?.length ?? 0) > 0 ||
          Object.values(ws.frame_actions ?? {}).some(a => a?.actionId && a.actionId !== 'idle')
        if (!serverHasWork && local) {
          setLabels(local.action_labels?.length ? local.action_labels : [...DEFAULT_ACTION_LABELS])
          setCommittedFrames(new Set(local.committed_frames ?? []))
          const actions: Record<number, FrameAnnotation> = {}
          for (let i = 0; i < ep.totalFrames; i++) {
            actions[i] = local.frame_actions[i] ?? { actionId: 'idle' }
          }
          setFrameActions(actions)
          setInstruction(local.instruction || ep.instruction || '')
          setSuccess(local.success || ep.success || 'unknown')
          setSegments(local.segments || [])
          setGrasps([])
          setTrajectory([])
          setLastSavedAt(local.savedAt)
        } else {
          setLabels(ws.action_labels.length ? ws.action_labels : [...DEFAULT_ACTION_LABELS])
          setCommittedFrames(new Set(ws.committed_frames))
          const actions: Record<number, FrameAnnotation> = {}
          for (let i = 0; i < ep.totalFrames; i++) {
            actions[i] = ws.frame_actions[i] ?? { actionId: 'idle' }
          }
          setFrameActions(actions)
          setInstruction(ws.instruction || ep.instruction || '')
          setSuccess(ws.success || ep.success || 'unknown')
          setSegments(ws.segments || [])
          setGrasps(ws.grasps || [])
          setTrajectory(ws.trajectory || [])
          setPreferences(ws.preferences || [])
        }
        setHydrated(true)
      } catch {
        if (!cancelled) {
          setEpisode(mockEpisode)
          setUseBackend(false)
          const local = readEmbodiedLocalDraft(taskId)
          if (local) {
            setLabels(local.action_labels?.length ? local.action_labels : [...DEFAULT_ACTION_LABELS])
            setCommittedFrames(new Set(local.committed_frames ?? []))
            setFrameActions(local.frame_actions)
            setLastSavedAt(local.savedAt)
          }
          setHydrated(true)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [taskId, token, mockEpisode, demoOnly])

  const collabEnabled = useBackend && !demoOnly
  const { peers, connected, pushDraft } = useYjsCollab(
    taskId,
    collabEnabled,
    useCallback((draft: Record<string, unknown>) => {
      if (Array.isArray(draft.action_labels)) {
        setLabels(draft.action_labels as ActionLabelDef[])
      }
      if (draft.frame_actions && typeof draft.frame_actions === 'object') {
        setFrameActions(draft.frame_actions as Record<number, FrameAnnotation>)
      }
      if (Array.isArray(draft.committed_frames)) {
        setCommittedFrames(new Set(draft.committed_frames as number[]))
      }
      if (typeof draft.instruction === 'string') setInstruction(draft.instruction)
      if (draft.success === 'success' || draft.success === 'fail' || draft.success === 'unknown') {
        setSuccess(draft.success)
      }
      if (Array.isArray(draft.segments)) setSegments(draft.segments as ActionSegment[])
      if (Array.isArray(draft.grasps)) setGrasps(draft.grasps as GraspPose[])
      if (Array.isArray(draft.trajectory)) setTrajectory(draft.trajectory as TrajectoryPoint[])
      if (Array.isArray(draft.preferences)) setPreferences(draft.preferences as PreferencePair[])
    }, []),
  )

  useEffect(() => {
    if (!collabEnabled || !connected || !hydrated) return
    pushDraft({
      action_labels: labels,
      frame_actions: frameActions,
      committed_frames: [...committedFrames].sort((a, b) => a - b),
      instruction,
      success,
      segments,
      grasps,
      trajectory,
      preferences,
    })
  }, [
    collabEnabled,
    connected,
    hydrated,
    labels,
    frameActions,
    committedFrames,
    instruction,
    success,
    segments,
    grasps,
    trajectory,
    preferences,
    pushDraft,
  ])

  const persistWorkspace = useCallback(async (showToast = false) => {
    setSavingDraft(true)
    try {
      const at = writeEmbodiedLocalDraft(
        taskId,
        labels,
        frameActions,
        committedFrames,
        instruction,
        success,
        segments,
      )
      setLastSavedAt(at)
      if (useBackend) {
        await embodiedApi.saveWorkspace(taskId, {
          action_labels: labels,
          frame_actions: frameActions,
          committed_frames: [...committedFrames].sort((a, b) => a - b),
          instruction,
          success,
          segments,
          grasps,
          trajectory,
          preferences,
        })
      }
      dirtyRef.current = false
      if (showToast) notifyDraftSaved()
    } catch {
      if (showToast) message.error('保存到服务器失败')
    } finally {
      setSavingDraft(false)
    }
  }, [useBackend, taskId, labels, frameActions, committedFrames, instruction, success, segments, grasps, trajectory, preferences])

  useEffect(() => {
    if (!hydrated) return
    dirtyRef.current = true
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      void persistWorkspace(false)
    }, 2500)
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [labels, frameActions, committedFrames, instruction, success, segments, grasps, trajectory, preferences, hydrated, persistWorkspace])

  useEffect(() => {
    if (!hydrated || useBackend) return
    // 离线：仅在无本地草稿时初始化空帧，避免覆盖已保存内容
    const local = readEmbodiedLocalDraft(taskId)
    if (local) return
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
  }, [taskId, episode.totalFrames, hydrated, useBackend])

  useEffect(() => {
    frameRef.current = frame
  }, [frame])

  useEffect(() => {
    continuousRef.current = continuous
  }, [continuous])


  const currentAnn = frameActions[frame] ?? { actionId: 'idle' }
  const joints = useMemo(() => jointStatesForFrame(frame, totalFrames), [frame, totalFrames])
  const force = useMemo(() => forceWrenchForFrame(frame, totalFrames), [frame, totalFrames])
  const tactile = useMemo(() => tactileForFrame(frame, totalFrames), [frame, totalFrames])
  const trajAtFrame = trajectory.find(t => t.frame === frame)

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

  const commitCurrentFrame = useCallback(async () => {
    setCommittedFrames(prev => {
      const n = new Set(prev)
      n.add(frame)
      return n
    })
    if (useBackend) {
      try {
        await embodiedApi.patchFrame(taskId, frame, { commit: true })
      } catch {
        message.warning('本帧已标记，但同步服务器失败')
      }
    }
    message.success(`已保存第 ${frame} 帧标注`)
  }, [frame, useBackend, taskId])

  const uncommitCurrentFrame = useCallback(async () => {
    setCommittedFrames(prev => {
      const n = new Set(prev)
      n.delete(frame)
      return n
    })
    if (useBackend) {
      try {
        await embodiedApi.patchFrame(taskId, frame, { commit: false })
      } catch {
        message.warning('已取消标记，但同步服务器失败')
      }
    }
    message.info(`已取消第 ${frame} 帧的「已保存」标记`)
  }, [frame, useBackend, taskId])

  const exportJson = useCallback(async () => {
    if (useBackend) {
      try {
        const res = await embodiedApi.exportJson(taskId)
        downloadBlob(res.data, `embodied_${taskId}_${Date.now()}.json`)
        message.success('已从服务器导出 JSON')
        return
      } catch {
        message.warning('服务器导出失败，使用本地数据')
      }
    }
    const payload = buildExportPayload(
      taskId,
      frameActions,
      episode,
      labels,
      [...committedFrames].sort((a, b) => a - b),
    )
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
    downloadBlob(blob, `embodied_${taskId}_${Date.now()}.json`)
    message.success('已导出本地 JSON')
  }, [useBackend, taskId, frameActions, episode, labels, committedFrames])

  const runPrelabel = useCallback(async () => {
    if (!useBackend) {
      message.info('演示模式无策略预标注')
      return
    }
    setPrelabeling(true)
    try {
      await embodiedApi.prelabel(taskId)
      const ws = await embodiedApi.getWorkspace(taskId)
      setInstruction(ws.instruction || '')
      setSuccess(ws.success)
      setSegments(ws.segments || [])
      setGrasps(ws.grasps || [])
      setTrajectory(ws.trajectory || [])
      setPreferences(ws.preferences || [])
      message.success('已应用策略预标注')
    } catch {
      message.error('预标注失败')
    } finally {
      setPrelabeling(false)
    }
  }, [useBackend, taskId])

  useEffect(() => {
    if (!useBackend) return
    void embodiedApi
      .listPolicyWeights()
      .then(res => setPolicyActive(res.data?.active_id ?? null))
      .catch(() => undefined)
  }, [useBackend])

  const uploadPolicyWeight = useCallback(
    async (file: File | null) => {
      if (!file || !useBackend) return
      try {
        const { data } = await embodiedApi.uploadPolicyWeight(file)
        setPolicyActive(data?.active_id ?? data?.item?.id ?? null)
        message.success('策略权重已上传并可用')
      } catch {
        message.error('权重上传失败')
      }
    },
    [useBackend],
  )

  const exportTorqueCsv = useCallback(async () => {
    if (useBackend) {
      try {
        const res = await embodiedApi.exportTorqueCsv(taskId)
        downloadBlob(res.data, `embodied_torque_${taskId}_${Date.now()}.csv`)
        message.success('已从服务器导出扭矩 CSV')
        return
      } catch {
        message.warning('服务器导出失败，使用本地数据')
      }
    }
    const rows = ['frame_index,timestamp_ms,joint,torque_nm']
    for (let i = 0; i < totalFrames; i++) {
      const ts = Math.round((i / Math.max(1, totalFrames - 1)) * clipDurationSec * 1000)
      for (const j of jointStatesForFrame(i, totalFrames)) {
        rows.push(`${i},${ts},${j.name},${j.torque_nm}`)
      }
    }
    const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8' })
    downloadBlob(blob, `embodied_torque_${taskId}_${Date.now()}.csv`)
    message.success('已导出扭矩 CSV')
  }, [taskId, totalFrames, clipDurationSec, useBackend])

  const handleSubmit = useCallback(async () => {
    if (!useBackend) {
      message.info('演示任务仅本地保存，请用正式任务提交审核')
      return
    }
    setSubmitting(true)
    try {
      await persistWorkspace(false)
      await embodiedApi.submit(taskId, 30)
      message.success('已提交审核')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '提交失败')
    } finally {
      setSubmitting(false)
    }
  }, [useBackend, persistWorkspace, taskId])

  const markSegmentStart = useCallback(() => {
    setSegStart(frame)
    message.info(`区间起点：帧 ${frame}`)
  }, [frame])

  const markSegmentEnd = useCallback(() => {
    if (segStart == null) {
      message.warning('请先标记区间起点')
      return
    }
    const start = Math.min(segStart, frame)
    const end = Math.max(segStart, frame)
    const actionId = frameActions[frame]?.actionId || 'idle'
    setSegments(prev => [
      ...prev,
      {
        id: `seg_${Date.now().toString(36)}`,
        startFrame: start,
        endFrame: end,
        actionId,
        note: '',
      },
    ])
    setSegStart(null)
    message.success(`已添加区间 ${start}–${end}`)
  }, [segStart, frame, frameActions])

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
      <CollabPresenceBar peers={peers} connected={connected} />
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#1e1e2e] pb-4">
        <div className="flex items-center gap-3 min-w-0">
          <button
            type="button"
            onClick={() => navigate(backHref)}
            className="text-xs px-2.5 py-1.5 rounded-lg border border-[#1e1e2e] text-white/50 hover:text-white/80 hover:border-white/20 transition-all"
          >
            ← 返回
          </button>
          <div className="min-w-0">
            <div className="text-[10px] text-white/35 uppercase tracking-wider">
              具身标注 · {episode.caseId === 'aloha' ? '多机位真实流' : '视频 mock'}
              {useBackend ? ' · 已同步服务器' : ''}
            </div>
            <h1 className="text-sm md:text-base font-semibold text-white/90 truncate">{episode.projectName}</h1>
            <div className="text-[11px] text-white/35 font-mono mt-0.5">
              task #{taskId} · {streams.length} 路 · 前 {clipDurationSec}s / {totalFrames} 帧 · 已保存{' '}
              {committedFrames.size}/{totalFrames}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {lastSavedAt && (
            <span className="text-[10px] text-[#10b981]/80 font-mono" title={lastSavedAt}>
              已保存 {new Date(lastSavedAt).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          )}
          <button
            type="button"
            onClick={() => void persistWorkspace(true)}
            disabled={savingDraft}
            className="text-xs px-3 py-1.5 rounded-lg border border-white/15 text-white/60 hover:border-white/30 disabled:opacity-40"
          >
            {savingDraft ? '保存中…' : '保存草稿'}
          </button>
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
          <ProjectExportMenu
            projectId={projectIdParam}
            projectName={episode.projectName}
            compact
          />
          <button
            type="button"
            onClick={() => void runPrelabel()}
            disabled={prelabeling || !useBackend}
            className="text-xs px-3 py-1.5 rounded-lg border border-[#10b981]/40 text-[#10b981] hover:bg-[#10b981]/10 disabled:opacity-40"
          >
            {prelabeling ? '预标注中…' : '策略预标注'}
          </button>
          <label className="text-xs px-3 py-1.5 rounded-lg border border-[#1e1e2e] text-white/50 hover:border-white/25 cursor-pointer disabled:opacity-40">
            上传权重
            <input
              type="file"
              className="hidden"
              disabled={!useBackend}
              onChange={e => {
                const f = e.target.files?.[0] ?? null
                void uploadPolicyWeight(f)
                e.target.value = ''
              }}
            />
          </label>
          {policyActive && (
            <span className="text-[10px] text-white/30 font-mono truncate max-w-[7rem]" title={policyActive}>
              w:{policyActive.slice(0, 8)}
            </span>
          )}
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={submitting || !useBackend}
            className="text-xs px-3 py-1.5 rounded-lg border border-[#a78bfa]/40 text-[#a78bfa] hover:bg-[#a78bfa]/10 disabled:opacity-40"
          >
            {submitting ? '提交中…' : '提交审核'}
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
            <div className="text-[11px] text-white/40 uppercase tracking-widest">任务指令 / 结局</div>
            <label className="block text-[11px] text-white/40 mb-1">语言指令（VLA）</label>
            <textarea
              value={instruction}
              onChange={e => setInstruction(e.target.value)}
              rows={2}
              placeholder="例如：把咖啡杯放到托盘上"
              className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white placeholder-white/20 resize-none focus:outline-none focus:border-[#f97316]/40"
            />
            <label className="block text-[11px] text-white/40 mb-1">执行结果</label>
            <select
              value={success}
              onChange={e => setSuccess(e.target.value as 'success' | 'fail' | 'unknown')}
              className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#f97316]/40"
            >
              <option value="unknown">未知</option>
              <option value="success">成功</option>
              <option value="fail">失败</option>
            </select>
            <div className="text-[11px] text-white/40 uppercase tracking-widest pt-1">动作区间</div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={markSegmentStart}
                className="text-xs px-3 py-1.5 rounded-lg border border-[#00d4ff]/35 text-[#00d4ff] hover:bg-[#00d4ff]/10"
              >
                标记起点{segStart != null ? ` (${segStart})` : ''}
              </button>
              <button
                type="button"
                onClick={markSegmentEnd}
                className="text-xs px-3 py-1.5 rounded-lg border border-[#10b981]/35 text-[#10b981] hover:bg-[#10b981]/10"
              >
                标记终点并添加
              </button>
            </div>
            {segments.length > 0 && (
              <div className="space-y-1.5 max-h-28 overflow-y-auto">
                {segments.map(s => (
                  <div key={s.id} className="flex items-center gap-2 text-[11px] text-white/55">
                    <span className="font-mono text-white/35">
                      {s.startFrame}–{s.endFrame}
                    </span>
                    <span>{labels.find(l => l.id === s.actionId)?.label || s.actionId}</span>
                    <button
                      type="button"
                      className="ml-auto text-red-400/80 hover:text-red-300"
                      onClick={() => setSegments(prev => prev.filter(x => x.id !== s.id))}
                    >
                      删
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="text-[11px] text-white/40 uppercase tracking-widest pt-2">抓取 / 轨迹</div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() =>
                  setGrasps(prev => [
                    ...prev,
                    {
                      id: `g_${Date.now().toString(36)}`,
                      frame,
                      position: { x: 0, y: 0, z: 0 },
                      orientation: { roll: 0, pitch: 0, yaw: 0 },
                      width: 0.08,
                      label: 'grasp',
                    },
                  ])
                }
                className="text-xs px-3 py-1.5 rounded-lg border border-[#f97316]/35 text-[#f97316] hover:bg-[#f97316]/10"
              >
                本帧加抓取点
              </button>
              <button
                type="button"
                onClick={() =>
                  setTrajectory(prev => [
                    ...prev.filter(p => p.frame !== frame),
                    {
                      frame,
                      ee: { x: 0, y: 0, z: 0, roll: 0, pitch: 0, yaw: 0 },
                      gripper: 0,
                    },
                  ])
                }
                className="text-xs px-3 py-1.5 rounded-lg border border-[#a78bfa]/35 text-[#a78bfa] hover:bg-[#a78bfa]/10"
              >
                本帧加 EE 轨迹点
              </button>
            </div>
            <p className="text-[10px] text-white/25">
              抓取 {grasps.length} · 轨迹点 {trajectory.length}（数值 + 3D 拖拽同步）
            </p>
            <EmbodiedPose3DViewer
              grasps={grasps}
              trajectory={trajectory}
              frame={frame}
              selectedGraspId={selectedGraspId}
              onSelectGrasp={setSelectedGraspId}
              onMoveGrasp={(id, position, orientation) =>
                setGrasps(prev =>
                  prev.map(g =>
                    g.id === id
                      ? {
                          ...g,
                          position,
                          orientation: orientation || g.orientation,
                        }
                      : g,
                  ),
                )
              }
              onMoveTrajectory={(f, ee) =>
                setTrajectory(prev => prev.map(p => (p.frame === f ? { ...p, ee } : p)))
              }
            />
            {grasps.filter(g => g.frame === frame).map(g => (
              <div key={g.id} className="grid grid-cols-3 gap-1 text-[10px]">
                {(['x', 'y', 'z'] as const).map(k => (
                  <label key={k} className="text-white/35">
                    pos.{k}
                    <input
                      type="number"
                      step="0.01"
                      value={g.position[k]}
                      onChange={e =>
                        setGrasps(prev =>
                          prev.map(x =>
                            x.id === g.id
                              ? { ...x, position: { ...x.position, [k]: Number(e.target.value) } }
                              : x,
                          ),
                        )
                      }
                      className="w-full mt-0.5 bg-[#0a0a0f] border border-[#1e1e2e] rounded px-1 py-1 text-white font-mono"
                    />
                  </label>
                ))}
                {(['roll', 'pitch', 'yaw'] as const).map(k => (
                  <label key={k} className="text-white/35">
                    {k}
                    <input
                      type="number"
                      step="0.01"
                      value={g.orientation[k]}
                      onChange={e =>
                        setGrasps(prev =>
                          prev.map(x =>
                            x.id === g.id
                              ? { ...x, orientation: { ...x.orientation, [k]: Number(e.target.value) } }
                              : x,
                          ),
                        )
                      }
                      className="w-full mt-0.5 bg-[#0a0a0f] border border-[#1e1e2e] rounded px-1 py-1 text-white font-mono"
                    />
                  </label>
                ))}
                <button
                  type="button"
                  className="col-span-3 text-left text-red-400/80"
                  onClick={() => setGrasps(prev => prev.filter(x => x.id !== g.id))}
                >
                  删除本抓取
                </button>
              </div>
            ))}
            {trajAtFrame && (
              <div className="grid grid-cols-3 gap-1 text-[10px] pt-1 border-t border-[#1e1e2e]/80">
                {(['x', 'y', 'z', 'roll', 'pitch', 'yaw'] as const).map(k => (
                  <label key={k} className="text-white/35">
                    ee.{k}
                    <input
                      type="number"
                      step="0.01"
                      value={trajAtFrame.ee[k]}
                      onChange={e =>
                        setTrajectory(prev =>
                          prev.map(p =>
                            p.frame === frame
                              ? { ...p, ee: { ...p.ee, [k]: Number(e.target.value) } }
                              : p,
                          ),
                        )
                      }
                      className="w-full mt-0.5 bg-[#0a0a0f] border border-[#1e1e2e] rounded px-1 py-1 text-white font-mono"
                    />
                  </label>
                ))}
                <label className="text-white/35 col-span-3">
                  gripper
                  <input
                    type="number"
                    step="0.01"
                    value={trajAtFrame.gripper}
                    onChange={e =>
                      setTrajectory(prev =>
                        prev.map(p =>
                          p.frame === frame ? { ...p, gripper: Number(e.target.value) } : p,
                        ),
                      )
                    }
                    className="w-full mt-0.5 bg-[#0a0a0f] border border-[#1e1e2e] rounded px-1 py-1 text-white font-mono"
                  />
                </label>
              </div>
            )}
            <div className="text-[11px] text-white/40 uppercase tracking-widest pt-2">偏好对（RLHF）</div>
            <button
              type="button"
              onClick={() =>
                setPreferences(prev => [
                  ...prev,
                  {
                    id: `pref_${Date.now().toString(36)}`,
                    prompt: instruction || '比较两种执行方式',
                    chosen: '动作更稳、抓取成功',
                    rejected: '抖动导致失败',
                    winner: 'a',
                  },
                ])
              }
              className="text-xs px-3 py-1.5 rounded-lg border border-[#fbbf24]/35 text-[#fbbf24] hover:bg-[#fbbf24]/10"
            >
              添加偏好对
            </button>
            {preferences.length > 0 && (
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {preferences.map(p => (
                  <div key={p.id} className="space-y-1 text-[10px] border border-[#1e1e2e] rounded-lg p-2">
                    <input
                      value={p.prompt}
                      onChange={e =>
                        setPreferences(prev =>
                          prev.map(x => (x.id === p.id ? { ...x, prompt: e.target.value } : x)),
                        )
                      }
                      placeholder="比较提示"
                      className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1 text-white"
                    />
                    <textarea
                      value={p.chosen}
                      onChange={e =>
                        setPreferences(prev =>
                          prev.map(x => (x.id === p.id ? { ...x, chosen: e.target.value } : x)),
                        )
                      }
                      rows={1}
                      placeholder="chosen / A"
                      className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1 text-white resize-none"
                    />
                    <textarea
                      value={p.rejected}
                      onChange={e =>
                        setPreferences(prev =>
                          prev.map(x => (x.id === p.id ? { ...x, rejected: e.target.value } : x)),
                        )
                      }
                      rows={1}
                      placeholder="rejected / B"
                      className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1 text-white resize-none"
                    />
                    <div className="flex items-center gap-2">
                      <select
                        value={p.winner}
                        onChange={e =>
                          setPreferences(prev =>
                            prev.map(x =>
                              x.id === p.id
                                ? { ...x, winner: e.target.value as PreferencePair['winner'] }
                                : x,
                            ),
                          )
                        }
                        className="bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1 text-white"
                      >
                        <option value="a">胜 A</option>
                        <option value="b">胜 B</option>
                        <option value="tie">平局</option>
                      </select>
                      <button
                        type="button"
                        className="ml-auto text-red-400/80"
                        onClick={() => setPreferences(prev => prev.filter(x => x.id !== p.id))}
                      >
                        删
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

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
              <span className="text-[11px] text-white/40 uppercase tracking-widest">
                关节 / 力觉 / 触觉（mock）
              </span>
              <span className="text-[10px] text-white/25">rad · N·m · N</span>
            </div>
            <div className="overflow-x-auto max-h-[200px] overflow-y-auto">
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
            <div className="px-3 py-2 border-t border-[#1e1e2e] grid grid-cols-3 gap-2 text-[10px] font-mono text-white/55">
              {(['fx', 'fy', 'fz', 'tx', 'ty', 'tz'] as const).map(k => (
                <div key={k}>
                  <span className="text-white/30">{k} </span>
                  {force[k]}
                </div>
              ))}
            </div>
            <div className="px-3 py-2 border-t border-[#1e1e2e] flex flex-wrap gap-2 text-[10px]">
              {tactile.pads.map(p => (
                <span key={p.name} className="font-mono text-white/50">
                  {p.name}:{p.pressure}
                </span>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
