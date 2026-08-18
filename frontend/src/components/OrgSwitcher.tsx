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
type Plan = { id: string; label: string; credits_per_month: number; price_id: string }

/** 侧栏组织切换：切换后刷新页面以重载项目列表作用域 */
export default function OrgSwitcher({ collapsed }: { collapsed: boolean }) {
  const { user, updateUser } = useAuthStore()
  const [orgs, setOrgs] = useState<OrgItem[]>([])
  const [activeId, setActiveId] = useState<number | null>(user?.active_org_id ?? null)
  const [busy, setBusy] = useState(false)
  const [packs, setPacks] = useState<Pack[]>([])
  const [plans, setPlans] = useState<Plan[]>([])
  const [stripeOk, setStripeOk] = useState(false)
  const [subStatus, setSubStatus] = useState<string | null>(null)
  const [connectEnabled, setConnectEnabled] = useState(false)
  const [connectReady, setConnectReady] = useState(false)

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
    billingApi
      .listPlans()
      .then(res => {
        if (cancelled) return
        setPlans((res.data?.items as Plan[]) || [])
      })
      .catch(() => undefined)
    billingApi
      .features()
      .then(res => {
        if (cancelled) return
        setConnectEnabled(Boolean(res.data?.connect_enabled))
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [user?.active_org_id, updateUser])

  useEffect(() => {
    if (!activeId || !stripeOk) {
      setSubStatus(null)
      return
    }
    let cancelled = false
    billingApi
      .getSubscription(activeId)
      .then(res => {
        if (cancelled) return
        setSubStatus((res.data?.subscription_status as string) || null)
        setConnectReady(Boolean(res.data?.connect_charges_enabled))
      })
      .catch(() => {
        if (!cancelled) setSubStatus(null)
      })
    return () => {
      cancelled = true
    }
  }, [activeId, stripeOk])

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

  async function subscribe(planId: string) {
    if (!activeId || busy) return
    setBusy(true)
    try {
      const { data } = await billingApi.subscribe(activeId, planId)
      if (data?.url) {
        window.location.href = data.url as string
        return
      }
      message.error('未返回订阅链接')
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(detail || '创建订阅失败')
    } finally {
      setBusy(false)
    }
  }

  async function openPortal() {
    if (!activeId || busy) return
    setBusy(true)
    try {
      const { data } = await billingApi.portal(activeId)
      if (data?.url) {
        window.location.href = data.url as string
        return
      }
      message.error('未返回门户链接')
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(detail || '打开订阅管理失败（需先完成订阅）')
    } finally {
      setBusy(false)
    }
  }

  async function openConnect() {
    if (!activeId || busy) return
    setBusy(true)
    try {
      const api = connectReady ? billingApi.connectLogin : billingApi.connectOnboard
      const { data } = await api(activeId)
      if (data?.url) {
        window.location.href = data.url
        return
      }
      message.error('未返回 Connect 链接')
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      message.error(detail || 'Connect 入驻失败')
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
      {subStatus && (
        <div className="text-[10px] text-white/30 mt-0.5 px-1">订阅 {subStatus}</div>
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
      {stripeOk && plans.length > 0 && activeId && (
        <div className="mt-1 space-y-1 px-0.5">
          {plans.slice(0, 2).map(p => (
            <button
              key={p.id}
              type="button"
              disabled={busy}
              onClick={() => void subscribe(p.id)}
              className="w-full text-[10px] px-2 py-1 rounded border border-[#1e1e2e] text-white/50
                hover:text-[#10b981]/90 hover:border-[#10b981]/30 disabled:opacity-40"
            >
              订阅 {p.label}
            </button>
          ))}
          <button
            type="button"
            disabled={busy}
            onClick={() => void openPortal()}
            className="w-full text-[10px] px-2 py-1 rounded border border-[#1e1e2e] text-white/40
              hover:text-white/70 hover:border-white/20 disabled:opacity-40"
          >
            管理订阅
          </button>
        </div>
      )}
      {connectEnabled && activeId && (
        <button
          type="button"
          disabled={busy}
          onClick={() => void openConnect()}
          className="mt-1 w-full text-[10px] px-2 py-1 rounded border border-[#1e1e2e] text-white/40
            hover:text-amber-300/90 hover:border-amber-400/30 disabled:opacity-40"
        >
          {connectReady ? '收款账户' : '连接收款'}
        </button>
      )}
    </div>
  )
}
