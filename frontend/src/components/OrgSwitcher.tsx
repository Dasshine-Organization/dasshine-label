import { useEffect, useState } from 'react'
import { orgApi } from '../services/api'
import useAuthStore from '../store/authStore'

type OrgItem = { id: number; name: string; slug: string }

/** 侧栏组织切换：切换后刷新页面以重载项目列表作用域 */
export default function OrgSwitcher({ collapsed }: { collapsed: boolean }) {
  const { user, updateUser } = useAuthStore()
  const [orgs, setOrgs] = useState<OrgItem[]>([])
  const [activeId, setActiveId] = useState<number | null>(user?.active_org_id ?? null)
  const [busy, setBusy] = useState(false)

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

  if (collapsed || orgs.length === 0) return null

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
    </div>
  )
}
