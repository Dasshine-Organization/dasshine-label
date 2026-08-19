import { useCallback, useEffect, useState } from 'react'
import { message } from 'antd'
import { projectApi } from '../../services/api'

type Props = {
  projectId: number
}

/** 主动学习池：低置信样本同步与重标 */
export default function ActiveLearningPanel({ projectId }: Props) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [threshold, setThreshold] = useState(0.8)
  const [items, setItems] = useState<Array<Record<string, unknown>>>([])

  const load = useCallback(async () => {
    try {
      const { data } = await projectApi.getActiveLearningPool(projectId)
      setTotal(data.total ?? 0)
      setThreshold(Number(data.threshold ?? 0.8))
      setItems(data.items ?? [])
    } catch {
      setItems([])
    }
  }, [projectId])

  useEffect(() => {
    if (open) void load()
  }, [open, load])

  async function syncPool() {
    setLoading(true)
    try {
      const { data } = await projectApi.syncActiveLearning(projectId)
      message.success(`已同步：新增 ${data.added ?? 0}，移除 ${data.removed ?? 0}`)
      await load()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '同步失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="px-3 py-1.5 rounded-lg text-xs border border-[#a78bfa]/35 text-[#a78bfa]
          hover:bg-[#a78bfa]/10 transition-all"
      >
        主动学习{total > 0 ? ` (${total})` : ''}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 z-40 w-[320px] bg-[#12121a] border border-[#1e1e2e] rounded-xl shadow-xl p-3 space-y-2">
          <div className="flex items-center justify-between text-xs text-white/50">
            <span>置信度 &lt; {threshold.toFixed(2)} 入池</span>
            <button type="button" onClick={() => setOpen(false)} className="text-white/30 hover:text-white/60">
              关闭
            </button>
          </div>
          <button
            type="button"
            disabled={loading}
            onClick={() => void syncPool()}
            className="w-full py-1.5 rounded-lg text-xs border border-[#a78bfa]/30 text-[#a78bfa]"
          >
            从预标注结果同步入池
          </button>
          {items.length === 0 ? (
            <div className="text-[11px] text-white/30 py-3 text-center">池内暂无任务</div>
          ) : (
            <ul className="max-h-36 overflow-y-auto space-y-1">
              {items.map(it => (
                <li key={String(it.id)} className="text-[10px] text-white/45 flex justify-between gap-2 px-1">
                  <span className="font-mono">#{String(it.id)}</span>
                  <span>
                    {it.pre_label_confidence != null
                      ? `${(Number(it.pre_label_confidence) * 100).toFixed(0)}%`
                      : '未预标'}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
