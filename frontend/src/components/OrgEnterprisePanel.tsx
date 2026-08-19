import { useEffect, useState } from 'react'
import { message } from 'antd'
import { orgApi } from '../services/api'
import { useLocale } from '../i18n/LocaleProvider'

type Props = {
  orgId: number
  orgName?: string
  collapsed?: boolean
}

/** 组织企业设置：邀请 / API Key / Webhook / 审计 */
export default function OrgEnterprisePanel({ orgId, orgName, collapsed }: Props) {
  const { t } = useLocale()
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<'invite' | 'keys' | 'hooks' | 'audit'>('invite')
  const [email, setEmail] = useState('')
  const [inviteUrl, setInviteUrl] = useState('')
  const [keys, setKeys] = useState<Array<Record<string, unknown>>>([])
  const [hooks, setHooks] = useState<Array<Record<string, unknown>>>([])
  const [audit, setAudit] = useState<Array<Record<string, unknown>>>([])
  const [hookUrl, setHookUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [newKey, setNewKey] = useState('')

  useEffect(() => {
    if (!open || !orgId) return
    void loadTab()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, orgId, tab])

  async function loadTab() {
    try {
      if (tab === 'keys') {
        const { data } = await orgApi.listApiKeys(orgId)
        setKeys(data.items || [])
      } else if (tab === 'hooks') {
        const { data } = await orgApi.listWebhooks(orgId)
        setHooks(data.items || [])
      } else if (tab === 'audit') {
        const { data } = await orgApi.listAudit(orgId, 50)
        setAudit(data.items || [])
      }
    } catch {
      /* ignore */
    }
  }

  async function sendInvite() {
    if (!email.trim()) return
    setBusy(true)
    try {
      const { data } = await orgApi.createInvite(orgId, { email: email.trim(), role: 'member' })
      setInviteUrl(String(data.accept_url || ''))
      message.success('邀请已创建（未配 SMTP 时见后端日志）')
      setEmail('')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '邀请失败')
    } finally {
      setBusy(false)
    }
  }

  async function createKey() {
    setBusy(true)
    try {
      const { data } = await orgApi.createApiKey(orgId, { name: 'default' })
      setNewKey(String(data.key || ''))
      message.success('API Key 已创建，请立即复制')
      await loadTab()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '创建失败')
    } finally {
      setBusy(false)
    }
  }

  async function addHook() {
    if (!hookUrl.trim()) return
    setBusy(true)
    try {
      await orgApi.createWebhook(orgId, {
        url: hookUrl.trim(),
        events: ['task.submitted', 'review.decided', 'export.done'],
      })
      message.success('Webhook 已添加')
      setHookUrl('')
      await loadTab()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '添加失败')
    } finally {
      setBusy(false)
    }
  }

  if (collapsed) {
    return (
      <button
        type="button"
        title={t('org.enterprise')}
        onClick={() => setOpen(true)}
        className="w-full text-[10px] text-white/25 hover:text-white/50 py-1"
      >
        Ent
      </button>
    )
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="w-full text-left text-[10px] text-white/35 hover:text-[#00d4ff] px-1 py-1"
      >
        {t('org.enterprise')} · {orgName || `#${orgId}`}
      </button>
      {open && (
        <div className="absolute left-0 bottom-full mb-2 z-50 w-[340px] bg-[#12121a] border border-[#1e1e2e] rounded-xl shadow-xl p-3 space-y-2">
          <div className="flex gap-1 text-[10px]">
            {(
              [
                ['invite', t('org.invite')],
                ['keys', t('org.apiKeys')],
                ['hooks', t('org.webhooks')],
                ['audit', t('org.audit')],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                type="button"
                onClick={() => setTab(k)}
                className={`px-2 py-1 rounded ${tab === k ? 'bg-[#00d4ff]/15 text-[#00d4ff]' : 'text-white/40'}`}
              >
                {label}
              </button>
            ))}
            <button type="button" className="ml-auto text-white/30" onClick={() => setOpen(false)}>
              ×
            </button>
          </div>

          {tab === 'invite' && (
            <div className="space-y-2">
              <input
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1.5 text-xs"
                placeholder="email@company.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => void sendInvite()}
                className="w-full py-1.5 text-xs border border-[#00d4ff]/30 text-[#00d4ff] rounded-lg"
              >
                发送邀请
              </button>
              {inviteUrl && (
                <div className="text-[10px] text-white/40 break-all">链接：{inviteUrl}</div>
              )}
            </div>
          )}

          {tab === 'keys' && (
            <div className="space-y-2">
              <button
                type="button"
                disabled={busy}
                onClick={() => void createKey()}
                className="w-full py-1.5 text-xs border border-[#10b981]/30 text-[#10b981] rounded-lg"
              >
                新建 API Key
              </button>
              {newKey && (
                <div className="text-[10px] font-mono text-[#f59e0b] break-all bg-black/40 p-2 rounded">
                  {newKey}
                </div>
              )}
              <ul className="max-h-28 overflow-y-auto space-y-1">
                {keys.map(k => (
                  <li key={String(k.id)} className="text-[10px] text-white/45 flex justify-between gap-2">
                    <span>
                      {String(k.name)} · {String(k.prefix)}…
                    </span>
                    {!k.revoked_at && (
                      <button
                        type="button"
                        className="text-red-400"
                        onClick={() =>
                          void orgApi.revokeApiKey(orgId, Number(k.id)).then(loadTab)
                        }
                      >
                        撤销
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {tab === 'hooks' && (
            <div className="space-y-2">
              <input
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded px-2 py-1.5 text-xs"
                placeholder="https://example.com/hook"
                value={hookUrl}
                onChange={e => setHookUrl(e.target.value)}
              />
              <button
                type="button"
                disabled={busy}
                onClick={() => void addHook()}
                className="w-full py-1.5 text-xs border border-[#a78bfa]/30 text-[#a78bfa] rounded-lg"
              >
                添加 Webhook
              </button>
              <ul className="max-h-28 overflow-y-auto space-y-1">
                {hooks.map(h => (
                  <li key={String(h.id)} className="text-[10px] text-white/45 flex justify-between gap-2">
                    <span className="truncate">{String(h.url)}</span>
                    <button
                      type="button"
                      className="text-red-400 shrink-0"
                      onClick={() =>
                        void orgApi.deleteWebhook(orgId, Number(h.id)).then(loadTab)
                      }
                    >
                      删
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {tab === 'audit' && (
            <ul className="max-h-40 overflow-y-auto space-y-1">
              {audit.length === 0 ? (
                <li className="text-[10px] text-white/30">暂无记录</li>
              ) : (
                audit.map(a => (
                  <li key={String(a.id)} className="text-[10px] text-white/45 font-mono">
                    {String(a.action)} · {String(a.created_at || '').slice(0, 19)}
                  </li>
                ))
              )}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
