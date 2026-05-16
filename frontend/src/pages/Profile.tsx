import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import useAuthStore from '../store/authStore'
import { authApi, rolesApi } from '../services/api'
import { ROLE_LABELS, validatePassword, type PlatformRole } from '../utils/permissions'

export default function Profile() {
  const { user, token, setAuth } = useAuthStore()
  const [permissions, setPermissions] = useState<string[]>([])
  const [pwd, setPwd] = useState({ current: '', next: '', confirm: '' })
  const [pwdLoading, setPwdLoading] = useState(false)

  useEffect(() => {
    rolesApi.list().then(({ data }) => {
      setPermissions(data.current_permissions)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!token) return
    authApi.getMe().then(({ data }) => {
      setAuth(
        {
          id: data.id,
          username: data.username,
          email: data.email,
          level: data.level,
          role: data.role,
          is_admin: data.is_admin,
        },
        token,
      )
    }).catch(() => {})
  }, [token, setAuth])

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault()
    const err = validatePassword(pwd.next)
    if (err) { toast.error(err); return }
    if (pwd.next !== pwd.confirm) { toast.error('两次新密码不一致'); return }

    setPwdLoading(true)
    try {
      await authApi.changePassword({
        current_password: pwd.current,
        new_password: pwd.next,
      })
      toast.success('密码已更新')
      setPwd({ current: '', next: '', confirm: '' })
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : '修改失败')
    } finally {
      setPwdLoading(false)
    }
  }

  const roleLabel = ROLE_LABELS[(user?.role ?? 'annotator') as PlatformRole] ?? user?.role

  return (
    <div className="p-8 max-w-xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">账户设置</h1>
        <p className="text-sm text-white/30 mt-1">管理个人信息与登录密码</p>
      </div>

      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-2xl p-6 space-y-4">
        <h2 className="text-sm font-medium text-white/60">基本信息</h2>
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-[11px] text-white/30 mb-1">用户名</dt>
            <dd className="text-white/80 font-mono">{user?.username}</dd>
          </div>
          <div>
            <dt className="text-[11px] text-white/30 mb-1">邮箱</dt>
            <dd className="text-white/80">{user?.email || '—'}</dd>
          </div>
          <div>
            <dt className="text-[11px] text-white/30 mb-1">平台角色</dt>
            <dd className="text-[#00d4ff]">{roleLabel}</dd>
          </div>
          <div>
            <dt className="text-[11px] text-white/30 mb-1">标注等级</dt>
            <dd className="text-white/80 capitalize">{user?.level ?? 'novice'}</dd>
          </div>
        </dl>
        {permissions.length > 0 && (
          <div>
            <p className="text-[11px] text-white/30 mb-2">当前权限</p>
            <div className="flex flex-wrap gap-1.5">
              {permissions.map(p => (
                <span key={p} className="text-[10px] px-2 py-0.5 rounded-full bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/20">
                  {p}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-2xl p-6">
        <h2 className="text-sm font-medium text-white/60 mb-4">修改密码</h2>
        <form onSubmit={handleChangePassword} className="space-y-4">
          {[
            { key: 'current' as const, label: '当前密码' },
            { key: 'next' as const, label: '新密码' },
            { key: 'confirm' as const, label: '确认新密码' },
          ].map(f => (
            <div key={f.key}>
              <label className="block text-xs text-white/40 mb-1.5">{f.label}</label>
              <input
                type="password"
                value={pwd[f.key]}
                onChange={e => setPwd(prev => ({ ...prev, [f.key]: e.target.value }))}
                required
                className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-sm
                  focus:outline-none focus:border-[#00d4ff]/50"
              />
            </div>
          ))}
          <button
            type="submit"
            disabled={pwdLoading}
            className="px-4 py-2 rounded-lg text-sm bg-[#00d4ff]/15 text-[#00d4ff] border border-[#00d4ff]/30
              hover:bg-[#00d4ff]/25 disabled:opacity-40"
          >
            {pwdLoading ? '保存中…' : '更新密码'}
          </button>
        </form>
      </div>
    </div>
  )
}
