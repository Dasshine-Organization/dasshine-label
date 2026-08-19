import { useCallback, useEffect, useState } from 'react'
import { message } from 'antd'
import { projectApi, qualityApi } from '../../services/api'

type GoldenItem = {
  id: number
  status: string
  has_golden_answer: boolean
  golden_answer?: Record<string, unknown>
  filename?: string
}

interface Props {
  projectId: number
}

export default function ProjectQualityPanel({ projectId }: Props) {
  const [open, setOpen] = useState(false)
  const [ratio, setRatio] = useState(0.1)
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<GoldenItem[]>([])
  const [report, setReport] = useState<{
    golden_tasks?: number
    quality_score?: number
    approval_rate?: number
  } | null>(null)
  const [editId, setEditId] = useState<number | null>(null)
  const [answerJson, setAnswerJson] = useState('{\n  \n}')
  const [rotationOn, setRotationOn] = useState(false)
  const [guidelinesMd, setGuidelinesMd] = useState('')
  const [mustRead, setMustRead] = useState(true)
  const [autoApprove, setAutoApprove] = useState(false)
  const [minAgreement, setMinAgreement] = useState(0.8)
  const [goldenFailThreshold, setGoldenFailThreshold] = useState(5)
  const [savingGuide, setSavingGuide] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [g, r, qc, guide] = await Promise.all([
        projectApi.getGoldenTasks(projectId),
        qualityApi.getReport(projectId).catch(() => ({ data: null })),
        projectApi.getQualityConfig(projectId).catch(() => ({ data: null })),
        projectApi.getGuidelines(projectId).catch(() => ({ data: null })),
      ])
      setItems(g.data?.items ?? [])
      setReport(r.data as typeof report)
      const cfg = (qc.data?.quality_config || {}) as Record<string, unknown>
      setRotationOn(Boolean(cfg.golden_rotation))
      if (typeof cfg.golden_ratio === 'number') setRatio(Number(cfg.golden_ratio))
      setAutoApprove(Boolean(cfg.auto_approve_on_agreement))
      if (typeof cfg.min_agreement === 'number') setMinAgreement(Number(cfg.min_agreement))
      if (typeof cfg.golden_fail_threshold === 'number') {
        setGoldenFailThreshold(Number(cfg.golden_fail_threshold))
      }
      if (guide.data) {
        setGuidelinesMd(guide.data.guidelines_md || '')
        setMustRead(Boolean(guide.data.must_read ?? true))
      } else if (typeof cfg.guidelines_md === 'string') {
        setGuidelinesMd(cfg.guidelines_md)
        setMustRead(Boolean(cfg.guidelines_must_read ?? true))
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '加载质控失败')
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    if (open) load()
  }, [open, load])

  async function handleInsert() {
    try {
      const { data } = await qualityApi.insertGolden(projectId, ratio)
      message.success(`已标记 ${data.inserted} 道黄金题`)
      load()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '插入失败（需管理员）')
    }
  }

  async function toggleRotation(next: boolean) {
    try {
      await projectApi.updateQualityConfig(projectId, {
        golden_rotation: next,
        golden_ratio: ratio,
        golden_claim_ratio: ratio,
      })
      setRotationOn(next)
      message.success(next ? '已开启黄金题定时轮换' : '已关闭定时轮换')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '更新失败')
    }
  }

  async function saveDailyQc() {
    try {
      await projectApi.updateQualityConfig(projectId, {
        auto_approve_on_agreement: autoApprove,
        min_agreement: minAgreement,
        golden_fail_threshold: goldenFailThreshold,
      })
      message.success('日常质控已保存')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '保存失败')
    }
  }

  async function saveGuidelines() {
    setSavingGuide(true)
    try {
      await projectApi.putGuidelines(projectId, {
        guidelines_md: guidelinesMd,
        must_read: mustRead,
        bump: true,
      })
      message.success('标注规范已更新（成员需重新确认）')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '保存规范失败')
    } finally {
      setSavingGuide(false)
    }
  }

  function openEdit(item: GoldenItem) {
    setEditId(item.id)
    const data = item.golden_answer?.data ?? item.golden_answer ?? {}
    setAnswerJson(JSON.stringify(data, null, 2))
  }

  async function saveAnswer() {
    if (editId == null) return
    try {
      const parsed = JSON.parse(answerJson) as Record<string, unknown>
      await qualityApi.updateGoldenAnswer(editId, parsed)
      message.success('黄金答案已保存')
      setEditId(null)
      load()
    } catch (e: unknown) {
      const err = e as { message?: string; response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || err.message || '保存失败（JSON 需合法）')
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="px-3 py-1.5 rounded-lg text-xs border border-[#f59e0b]/35 text-[#f59e0b]
          hover:bg-[#f59e0b]/10 transition-all"
      >
        质控{report?.golden_tasks != null ? ` (${report.golden_tasks})` : ''}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 z-40 w-[420px] max-h-[80vh] overflow-y-auto bg-[#12121a] border border-[#1e1e2e] rounded-xl shadow-xl p-3 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs text-white/60">标注规范 / 黄金题 / 质控</div>
            <button type="button" onClick={() => setOpen(false)} className="text-white/30 text-xs hover:text-white/60">
              关闭
            </button>
          </div>

          <div className="space-y-2 border-b border-[#1e1e2e] pb-3">
            <div className="text-[10px] text-white/40 uppercase tracking-wider">标注规范 (Markdown)</div>
            <textarea
              rows={5}
              value={guidelinesMd}
              onChange={e => setGuidelinesMd(e.target.value)}
              placeholder="边界框紧贴目标；模糊目标不标…"
              className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-2 py-1.5 text-[11px] text-white/70 resize-none"
            />
            <label className="flex items-center gap-2 text-[11px] text-white/50 cursor-pointer">
              <input
                type="checkbox"
                checked={mustRead}
                onChange={e => setMustRead(e.target.checked)}
                className="rounded border-[#1e1e2e]"
              />
              标注员领取前必须确认
            </label>
            <button
              type="button"
              disabled={savingGuide}
              onClick={() => void saveGuidelines()}
              className="w-full py-1.5 rounded-lg text-xs border border-[#00d4ff]/30 text-[#00d4ff] hover:bg-[#00d4ff]/10 disabled:opacity-40"
            >
              {savingGuide ? '保存中…' : '保存规范并升版本'}
            </button>
          </div>

          <div className="space-y-2 border-b border-[#1e1e2e] pb-3">
            <div className="text-[10px] text-white/40 uppercase tracking-wider">日常质控</div>
            <label className="flex items-center gap-2 text-[11px] text-white/50 cursor-pointer">
              <input
                type="checkbox"
                checked={autoApprove}
                onChange={e => setAutoApprove(e.target.checked)}
                className="rounded border-[#1e1e2e]"
              />
              交叉一致率达标自动过审
            </label>
            <div className="flex items-center gap-2">
              <label className="text-[10px] text-white/35 whitespace-nowrap">最低一致率</label>
              <input
                type="number"
                min={0.5}
                max={1}
                step={0.05}
                value={minAgreement}
                onChange={e => setMinAgreement(Number(e.target.value))}
                className="w-20 bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1 text-xs text-white/70"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-[10px] text-white/35 whitespace-nowrap">黄金题连错暂停</label>
              <input
                type="number"
                min={1}
                max={20}
                step={1}
                value={goldenFailThreshold}
                onChange={e => setGoldenFailThreshold(Number(e.target.value))}
                className="w-16 bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1 text-xs text-white/70"
              />
            </div>
            <button
              type="button"
              onClick={() => void saveDailyQc()}
              className="w-full py-1.5 rounded-lg text-xs border border-[#10b981]/30 text-[#10b981] hover:bg-[#10b981]/10"
            >
              保存日常质控
            </button>
          </div>

          {report && (
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg bg-[#0a0a0f] border border-[#1e1e2e] p-2">
                <div className="text-[10px] text-white/30">黄金题</div>
                <div className="text-sm font-mono text-[#f59e0b]">{report.golden_tasks ?? 0}</div>
              </div>
              <div className="rounded-lg bg-[#0a0a0f] border border-[#1e1e2e] p-2">
                <div className="text-[10px] text-white/30">通过率</div>
                <div className="text-sm font-mono text-[#10b981]">
                  {Number(report.approval_rate ?? 0) > 1
                    ? Number(report.approval_rate).toFixed(0)
                    : ((report.approval_rate ?? 0) * 100).toFixed(0)}
                  %
                </div>
              </div>
              <div className="rounded-lg bg-[#0a0a0f] border border-[#1e1e2e] p-2">
                <div className="text-[10px] text-white/30">质量分</div>
                <div className="text-sm font-mono text-white/70">
                  {Number(report.quality_score ?? 0) > 1
                    ? Number(report.quality_score).toFixed(0)
                    : ((report.quality_score ?? 0) * 100).toFixed(0)}
                </div>
              </div>
            </div>
          )}

          <div className="flex items-center gap-2">
            <label className="text-[10px] text-white/35 whitespace-nowrap">插入比例</label>
            <input
              type="number"
              min={0.05}
              max={0.3}
              step={0.05}
              value={ratio}
              onChange={e => setRatio(Number(e.target.value))}
              className="w-16 bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1 text-xs text-white/70"
            />
            <button
              type="button"
              onClick={handleInsert}
              className="flex-1 py-1.5 rounded-lg text-xs border border-[#f59e0b]/30 text-[#f59e0b] hover:bg-[#f59e0b]/10"
            >
              插入黄金题
            </button>
          </div>

          <label className="flex items-center gap-2 text-[11px] text-white/50 cursor-pointer">
            <input
              type="checkbox"
              checked={rotationOn}
              onChange={e => void toggleRotation(e.target.checked)}
              className="rounded border-[#1e1e2e]"
            />
            定时轮换（Celery beat 每小时维持比例）
          </label>

          <div className="text-[10px] text-white/30">
            标注员工作台不会看到黄金标记（盲测）。专家在此编辑标准答案。
          </div>

          {loading ? (
            <div className="text-[11px] text-white/30 py-4 text-center">加载中…</div>
          ) : items.length === 0 ? (
            <div className="text-[11px] text-white/30 py-3 text-center">暂无黄金题</div>
          ) : (
            <div className="max-h-40 overflow-y-auto space-y-1">
              {items.map(item => (
                <div
                  key={item.id}
                  className="flex items-center justify-between px-2 py-1.5 rounded-lg bg-[#0a0a0f] text-xs"
                >
                  <div className="truncate">
                    <span className="font-mono text-white/50">#{item.id}</span>
                    <span className="text-white/30 ml-2">
                      {item.has_golden_answer ? '有答案' : '待填答案'}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => openEdit(item)}
                    className="text-[10px] text-[#00d4ff] hover:underline shrink-0"
                  >
                    编辑答案
                  </button>
                </div>
              ))}
            </div>
          )}

          {editId != null && (
            <div className="border-t border-[#1e1e2e] pt-3 space-y-2">
              <div className="text-[10px] text-white/40">编辑 #{editId} 标准答案 (JSON)</div>
              <textarea
                rows={6}
                value={answerJson}
                onChange={e => setAnswerJson(e.target.value)}
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-2 py-1.5 text-[11px] font-mono text-white/70"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setEditId(null)}
                  className="flex-1 py-1.5 rounded-lg text-xs border border-white/10 text-white/40"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={saveAnswer}
                  className="flex-1 py-1.5 rounded-lg text-xs border border-[#10b981]/35 text-[#10b981]"
                >
                  保存
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
