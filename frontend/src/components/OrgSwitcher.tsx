import { useEffect, useState } from 'react'
import { message } from 'antd'
import { billingApi, orgApi } from '../services/api'
import useAuthStore from '../store/authStore'

type OrgItem = {
  id: number
  name: string
  slug: string
  credits?: number
  quota?: { credits?: number }
}

type Pack = { id: string; credits: number; label: string; amount_cents: number }

/** 侧栏组织切换：切换后刷新页面以重载项目列表作用域 */
export default function OrgSwitcher({ collapsed }: { collapsed: boolean }) {
  const { user, updateUser } = useAuthStore()
  const [orgs, setOrgs] = useState<OrgItem[]>([])
  const [activeId, setActiveId] = useState<number | null>(user?.active_org_id ?? null)
  const [busy, setBusy] = useState(false)
  const [packs, setPacks] = useState<Pack[]>([])
  const [stripeOk, setStripeOk] = useState(false)

  useEffect(() => {
    let cancelled = false
    orgApi
      .list()
      .then(res => {
        if (cancelled) return
        const items = (res.data?.items ?? []) as OrgItem[]
        setOrgs(items)
        const aid = (res.data?.active_org_id as number | null) ?? user?.active_org_id ?? null
        setActiveId(aid)
        if (aid != null && aid !== user?.active_org_id) {
          updateUser({ active_org_id: aid })
        }
      })
      .catch(() => undefined)
    billingApi
      .listPacks()
      .then(res => {
        if (cancelled) return
        setStripeOk(Boolean(res.data?.configured))
        setPacks((res.data?.items as Pack[]) || [])
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [user?.active_org_id, updateUser])

  async function onChange(next: number) {
    if (!next || next === activeId || busy) return
    setBusy(true)
    try {
      await orgApi.activate(next)
      setActiveId(next)
      updateUser({ active_org_id: next })
      window.location.reload()
    } catch {
      /* ignore */
    } finally {
      setBusy(false)
    }
  }

  async function checkout(packId: string) {
    if (!activeId || busy) return
    setBusy(true)
    try {
      const { data } = await billingApi.checkout(activeId, packId)
      if (data?.url) {
        window.location.href = data.url as string
        return
      }
      message.error('未返回支付链接')
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(detail || '创建支付会话失败（可改用管理员充值）')
    } finally {
      setBusy(false)
    }
  }

  if (collapsed || orgs.length === 0) return null

  const active = orgs.find(o => o.id === activeId)
  const credits = active?.credits ?? active?.quota?.credits

  return (
    <div className="px-1 mb-2">
      <div className="text-[10px] uppercase tracking-wider text-white/25 mb-1 px-1">组织</div>
      <select
        value={activeId ?? ''}
        disabled={busy}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-md text-xs text-white/70
          px-2 py-1.5 outline-none focus:border-[#00d4ff]/40"
      >
        {orgs.map(o => (
          <option key={o.id} value={o.id}>
            {o.name}
          </option>
        ))}
      </select>
      {typeof credits === 'number' && (
        <div className="text-[10px] text-white/35 mt-1 px-1">积分 {credits.toLocaleString()}</div>
      )}
      {stripeOk && packs.length > 0 && activeId && (
        <div className="mt-1.5 space-y-1 px-0.5">
          {packs.slice(0, 2).map(p => (
            <button
              key={p.id}
              type="button"
              disabled={busy}
              onClick={() => void checkout(p.id)}
              className="w-full text-[10px] px-2 py-1 rounded border border-[#1e1e2e] text-white/50
                hover:text-[#00d4ff]/90 hover:border-[#00d4ff]/30 disabled:opacity-40"
            >
              充值 {p.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
