import { useCallback, useEffect, useState } from 'react'
import { message } from 'antd'
import { projectApi } from '../../services/api'

type Props = {
  projectId: number
}

type PoolItem = Record<string, unknown> & { id?: number }

/**
 * 主动学习池面板：同步低置信待领任务，便于优先 claim；
 * 管理员可勾选池内任务触发 relabel（释放领取人、回 PENDING、强制留池）。
 */
export default function ActiveLearningPanel({ projectId }: Props) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [threshold, setThreshold] = useState(0.8)
  const [items, setItems] = useState<PoolItem[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const load = useCallback(async () => {
    try {
      const { data } = await projectApi.getActiveLearningPool(projectId)
      setTotal(data.total ?? 0)
      setThreshold(Number(data.threshold ?? 0.8))
      setItems(data.items ?? [])
      setSelected(new Set())
    } catch {
      setItems([])
    }
  }, [projectId])

  useEffect(() => {
    if (open) void load()
  }, [open, load])

  function toggle(id: number) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

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

  async function relabelSelected() {
    const ids = [...selected]
    if (ids.length === 0) {
      message.warning('请先勾选要重标的任务')
      return
    }
    setLoading(true)
    try {
      const { data } = await projectApi.relabelActiveLearning(projectId, ids)
      message.success(`已标记重标 ${data.promoted ?? ids.length} 条`)
      await load()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '重标失败')
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
            <>
              <ul className="max-h-36 overflow-y-auto space-y-1">
                {items.map(it => {
                  const id = Number(it.id)
                  return (
                    <li key={String(it.id)} className="text-[10px] text-white/45 flex items-center gap-2 px-1">
                      <input
                        type="checkbox"
                        checked={selected.has(id)}
                        onChange={() => toggle(id)}
                        className="accent-[#a78bfa]"
                        aria-label={`选择任务 ${id}`}
                      />
                      <span className="font-mono flex-1">#{String(it.id)}</span>
                      <span>
                        {it.pre_label_confidence != null
                          ? `${(Number(it.pre_label_confidence) * 100).toFixed(0)}%`
                          : '未预标'}
                      </span>
                    </li>
                  )
                })}
              </ul>
              <button
                type="button"
                disabled={loading || selected.size === 0}
                onClick={() => void relabelSelected()}
                className="w-full py-1.5 rounded-lg text-xs border border-amber-500/40 text-amber-300/90
                  disabled:opacity-40 disabled:cursor-not-allowed"
              >
                重标已选 ({selected.size})
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
