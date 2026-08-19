import { useEffect, useState } from 'react'
import { message } from 'antd'
import { qualityApi } from '../services/api'

type Row = {
  rank: number
  user_id: number
  username: string
  accuracy: number
  completed_tasks: number
  level: string
  overall_score: number
}

export default function Leaderboard() {
  const [rows, setRows] = useState<Row[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    qualityApi
      .getLeaderboard(30)
      .then(res => setRows(res.data.data ?? []))
      .catch(() => message.error('加载排行榜失败'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-xl font-semibold mb-1">质量排行榜</h1>
      <p className="text-xs text-white/30 mb-6">按准确率与综合质量分排序（完成任务 ≥ 1）</p>
      {loading ? (
        <div className="text-white/30 text-sm">加载中…</div>
      ) : rows.length === 0 ? (
        <div className="text-white/30 text-sm">暂无数据</div>
      ) : (
        <div className="rounded-xl border border-[#1e1e2e] overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#12121a] text-[10px] text-white/35 uppercase tracking-wider">
              <tr>
                <th className="text-left px-4 py-2">名次</th>
                <th className="text-left px-4 py-2">用户</th>
                <th className="text-right px-4 py-2">准确率</th>
                <th className="text-right px-4 py-2">完成数</th>
                <th className="text-right px-4 py-2">综合分</th>
                <th className="text-left px-4 py-2">等级</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.user_id} className="border-t border-[#1e1e2e]/80">
                  <td className="px-4 py-2.5 font-mono text-[#00d4ff]/90">{r.rank}</td>
                  <td className="px-4 py-2.5">{r.username}</td>
                  <td className="px-4 py-2.5 text-right font-mono">{(r.accuracy * 100).toFixed(1)}%</td>
                  <td className="px-4 py-2.5 text-right font-mono">{r.completed_tasks}</td>
                  <td className="px-4 py-2.5 text-right font-mono">{(r.overall_score * 100).toFixed(1)}</td>
                  <td className="px-4 py-2.5 text-white/50">{r.level}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
