import { useState } from 'react'
import { message } from 'antd'
import api from '../../services/api'
import { ProjectSummary, DispatchStrategy } from '../../types/project'

interface Props {
  project: ProjectSummary
  onClose: () => void
  onDispatched: () => void
}

export default function DispatchModal({ project, onClose, onDispatched }: Props) {
  const [strategy, setStrategy] = useState<DispatchStrategy>('smart')
  const [batchSize, setBatchSize] = useState(100)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const pendingTasks =
    (project.total_tasks ?? project.total_items ?? 0)
    - (project.completed_tasks ?? 0)
    - (project.approved_tasks ?? project.approved_items ?? 0)

  const STRATEGIES = [
    { id: 'smart',       label: '智能分派', desc: '综合评分自动选最优标注员', color: '#00d4ff' },
    { id: 'round_robin', label: '轮询',     desc: '顺序循环均匀分配',         color: '#10b981' },
    { id: 'random',      label: '随机',     desc: '随机抽取符合条件的标注员', color: '#f59e0b' },
    { id: 'manual',      label: '手动',     desc: '指定成员列表',             color: '#a78bfa' },
  ]

  async function handleDispatch() {
    setLoading(true)
    try {
      const { data } = await api.post(`/projects/${project.id}/dispatch`, {
        project_id: project.id,
        batch_size: batchSize,
        strategy,
      })
      setResult(data)
      onDispatched()
      if (data.assigned_count > 0) {
        message.success({ content: `成功分派 ${data.assigned_count} 个任务`, duration: 3 })
      }
    } catch (e: any) {
      message.error({ content: e?.response?.data?.detail ?? '分派失败', duration: 3 })
    } finally {
      setLoading(false)
    }
  }

  const color = project.cover_color

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-md bg-[#12121a] border border-[#1e1e2e] rounded-2xl overflow-hidden"
        style={{ boxShadow: `0 0 40px ${color}12` }}>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#1e1e2e]">
          <div>
            <div className="text-sm font-medium text-white/80">任务分派</div>
            <div className="text-[11px] text-white/30 mt-0.5 truncate max-w-64">{project.name}</div>
          </div>
          <button onClick={onClose} className="text-white/30 hover:text-white/70 transition-colors">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
              <path d="M3 3l10 10M13 3L3 13" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Stats */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: '待分派', value: Math.max(0, pendingTasks), color: '#f59e0b' },
              { label: '总任务', value: project.total_tasks,       color: '#9ba0ad' },
              { label: '已完成', value: project.approved_tasks,    color: '#10b981' },
            ].map(s => (
              <div key={s.label} className="bg-[#0a0a0f] border border-[#1e1e2e] rounded-xl p-3 text-center">
                <div className="text-[10px] text-white/30 mb-1">{s.label}</div>
                <div className="text-lg font-mono font-semibold" style={{ color: s.color }}>{s.value}</div>
              </div>
            ))}
          </div>

          {/* Strategy */}
          <div>
            <div className="text-xs text-white/40 mb-2.5 uppercase tracking-widest">分派策略</div>
            <div className="grid grid-cols-2 gap-2">
              {STRATEGIES.map(s => (
                <button
                  key={s.id}
                  onClick={() => setStrategy(s.id as DispatchStrategy)}
                  className={`p-3 rounded-xl border text-left transition-all
                    ${strategy === s.id
                      ? 'ring-1'
                      : 'border-[#1e1e2e] hover:border-white/20'}`}
                  style={strategy === s.id ? {
                    background: `${s.color}12`,
                    borderColor: s.color,
                    boxShadow: `0 0 0 1px ${s.color}25`,
                  } : undefined}
                >
                  <div className={`text-xs font-medium mb-0.5 ${strategy === s.id ? '' : 'text-white/50'}`}
                    style={strategy === s.id ? { color: s.color } : undefined}>
                    {s.label}
                  </div>
                  <div className="text-[10px] text-white/25">{s.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Batch size */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs text-white/40 uppercase tracking-widest">本批次数量</div>
              <span className="text-sm font-mono text-white/60">{batchSize}</span>
            </div>
            <input
              type="range" min="10" max={Math.max(10, pendingTasks)} step="10"
              value={batchSize}
              onChange={e => setBatchSize(parseInt(e.target.value))}
              className="w-full"
            />
            <div className="flex justify-between text-[10px] text-white/20 mt-1">
              <span>10</span>
              <span>{Math.max(10, pendingTasks)}</span>
            </div>
          </div>

          {/* Result */}
          {result && (
            <div className={`rounded-xl p-3 border text-xs space-y-1
              ${result.assigned_count > 0
                ? 'bg-[#10b981]/10 border-[#10b981]/20 text-[#10b981]'
                : 'bg-[#ef4444]/10 border-[#ef4444]/20 text-[#ef4444]'}`}>
              <div className="font-medium">{result.message}</div>
              <div className="text-current/60">
                成功: {result.assigned_count} · 失败: {result.failed_count} · 批次: {result.batch_id?.slice(0, 8)}…
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex gap-3 px-5 pb-5">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl text-sm border border-white/10 text-white/40 hover:text-white/60 hover:border-white/20 transition-all"
          >
            取消
          </button>
          <button
            onClick={handleDispatch}
            disabled={loading || pendingTasks === 0}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-all active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed"
            style={{ background: `${color}20`, color, border: `1px solid ${color}40` }}
          >
            {loading
              ? <span className="flex items-center justify-center gap-2">
                  <span className="w-3.5 h-3.5 border border-current/30 border-t-current rounded-full animate-spin" />
                  分派中…
                </span>
              : '开始分派'}
          </button>
        </div>
      </div>
    </div>
  )
}
