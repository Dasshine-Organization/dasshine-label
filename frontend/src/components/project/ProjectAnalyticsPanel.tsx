import { useEffect, useState } from 'react'
import { projectApi } from '../../services/api'

type Props = {
  projectId: number
}

type Analytics = {
  summary?: {
    approved?: number
    approved_in_window?: number
    estimated_spend?: number
    throughput_per_day?: number
    pending?: number
  }
  price_per_task?: number
  tat_hours?: {
    annotate_p50?: number | null
    review_p50?: number | null
    e2e_p50?: number | null
  }
  daily_throughput?: Array<{ date: string; approved: number }>
}

/** 项目运营看板：近 30 天吞吐、累计成本（单价×历史通过数）、TAT p50。无数据时整块不渲染。 */
export default function ProjectAnalyticsPanel({ projectId }: Props) {
  const [data, setData] = useState<Analytics | null>(null)

  useEffect(() => {
    let cancelled = false
    projectApi
      .getAnalytics(projectId, 30)
      .then(res => {
        if (!cancelled) setData(res.data)
      })
      .catch(() => {
        if (!cancelled) setData(null)
      })
    return () => {
      cancelled = true
    }
  }, [projectId])

  if (!data?.summary) return null

  const s = data.summary
  const maxBar = Math.max(1, ...(data.daily_throughput?.map(d => d.approved) ?? [1]))

  return (
    <section className="mb-6 space-y-3">
      <h2 className="text-sm font-medium text-white/60">运营看板 · 近 30 天</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: '窗口内通过', value: s.approved_in_window ?? 0, color: '#10b981' },
          { label: '日均吞吐', value: s.throughput_per_day ?? 0, color: '#00d4ff' },
          {
            label: '累计成本',
            value: `¥${(s.estimated_spend ?? 0).toFixed(0)}`,
            color: '#f59e0b',
          },
          {
            label: '单价/任务',
            value: `¥${(data.price_per_task ?? 0).toFixed(2)}`,
            color: '#a78bfa',
          },
        ].map(c => (
          <div key={c.label} className="bg-[#12121a] border border-[#1e1e2e] rounded-xl p-3">
            <div className="text-[10px] text-white/30">{c.label}</div>
            <div className="text-lg font-mono font-semibold mt-0.5" style={{ color: c.color }}>
              {c.value}
            </div>
          </div>
        ))}
      </div>
      {(data.tat_hours?.e2e_p50 != null || data.tat_hours?.annotate_p50 != null) && (
        <div className="text-[11px] text-white/40 flex flex-wrap gap-4">
          {data.tat_hours?.annotate_p50 != null && (
            <span>标注 TAT p50: {data.tat_hours.annotate_p50.toFixed(1)}h</span>
          )}
          {data.tat_hours?.review_p50 != null && (
            <span>审核 TAT p50: {data.tat_hours.review_p50.toFixed(1)}h</span>
          )}
          {data.tat_hours?.e2e_p50 != null && (
            <span>端到端 p50: {data.tat_hours.e2e_p50.toFixed(1)}h</span>
          )}
        </div>
      )}
      {(data.daily_throughput?.length ?? 0) > 0 && (
        <div className="flex items-end gap-0.5 h-10">
          {data.daily_throughput!.slice(-14).map(d => (
            <div
              key={d.date}
              title={`${d.date}: ${d.approved}`}
              className="flex-1 bg-[#10b981]/30 rounded-t-sm min-w-[4px]"
              style={{ height: `${Math.max(8, (d.approved / maxBar) * 100)}%` }}
            />
          ))}
        </div>
      )}
    </section>
  )
}
