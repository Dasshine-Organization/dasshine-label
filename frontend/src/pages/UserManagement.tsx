import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import useAuthStore from '../store/authStore'
import { userApi, type UserRecord } from '../services/api'
import {
  ROLE_LABELS,
  ROLE_COLORS,
  STATUS_LABELS,
  assignableRoles,
  validatePassword,
  type PlatformRole,
} from '../utils/permissions'

const STATUS_OPTIONS = ['active', 'inactive', 'suspended'] as const

type FormMode = 'create' | 'edit' | 'reset' | null

const EMPTY_CREATE = {
  username: '',
  email: '',
  password: '',
  full_name: '',
  role: 'annotator' as PlatformRole,
}

export default function UserManagement() {
  const { user: actor } = useAuthStore()
  const [users, setUsers] = useState<UserRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [mode, setMode] = useState<FormMode>(null)
  const [selected, setSelected] = useState<UserRecord | null>(null)
  const [createForm, setCreateForm] = useState(EMPTY_CREATE)
  const [editForm, setEditForm] = useState({ role: 'annotator' as PlatformRole, status: 'active', full_name: '' })
  const [newPassword, setNewPassword] = useState('')
  const [saving, setSaving] = useState(false)

  const rolesCanAssign = assignableRoles(actor?.role)

  const loadUsers = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await userApi.getList({
        limit: 100,
        ...(roleFilter ? { role: roleFilter } : {}),
        ...(statusFilter ? { status: statusFilter } : {}),
      })
      setUsers(data)
    } catch {
      toast.error('加载用户列表失败')
    } finally {
      setLoading(false)
    }
  }, [roleFilter, statusFilter])

  useEffect(() => { loadUsers() }, [loadUsers])

  function openCreate() {
    setCreateForm({ ...EMPTY_CREATE, role: rolesCanAssign[rolesCanAssign.length - 1] ?? 'annotator' })
    setMode('create')
  }

  function openEdit(u: UserRecord) {
    setSelected(u)
    setEditForm({
      role: u.role as PlatformRole,
      status: u.status,
      full_name: u.full_name ?? '',
    })
    setMode('edit')
  }

  function openReset(u: UserRecord) {
    setSelected(u)
    setNewPassword('')
    setMode('reset')
  }

  function closeModal() {
    setMode(null)
    setSelected(null)
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    const pwdErr = validatePassword(createForm.password)
    if (pwdErr) { toast.error(pwdErr); return }
    setSaving(true)
    try {
      await userApi.create({
        username: createForm.username,
        email: createForm.email,
        password: createForm.password,
        full_name: createForm.full_name || undefined,
        role: createForm.role,
      })
      toast.success('用户已创建')
      closeModal()
      loadUsers()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : '创建失败')
    } finally {
      setSaving(false)
    }
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault()
    if (!selected) return
    setSaving(true)
    try {
      await userApi.update(selected.id, {
        role: editForm.role,
        status: editForm.status,
        full_name: editForm.full_name || undefined,
      })
      toast.success('已保存')
      closeModal()
      loadUsers()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function handleResetPassword(e: React.FormEvent) {
    e.preventDefault()
    if (!selected) return
    const pwdErr = validatePassword(newPassword)
    if (pwdErr) { toast.error(pwdErr); return }
    setSaving(true)
    try {
      await userApi.resetPassword(selected.id, newPassword)
      toast.success('密码已重置')
      closeModal()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : '重置失败')
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(u: UserRecord) {
    if (!confirm(`确定删除用户「${u.username}」？`)) return
    try {
      await userApi.delete(u.id)
      toast.success('用户已删除')
      loadUsers()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : '删除失败')
    }
  }

  return (
    <div className="p-8 max-w-5xl space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">用户管理</h1>
          <p className="text-sm text-white/30 mt-1">管理平台账户、角色与状态</p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="px-4 py-2 rounded-lg text-sm bg-[#7c3aed]/15 text-[#a78bfa] border border-[#7c3aed]/30 hover:bg-[#7c3aed]/25"
        >
          新建用户
        </button>
      </div>

      <div className="flex flex-wrap gap-3">
        <select
          value={roleFilter}
          onChange={e => setRoleFilter(e.target.value)}
          className="bg-[#12121a] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white/70"
        >
          <option value="">全部角色</option>
          {Object.entries(ROLE_LABELS).map(([v, l]) => (
            <option key={v} value={v}>{l}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="bg-[#12121a] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white/70"
        >
          <option value="">全部状态</option>
          {STATUS_OPTIONS.map(s => (
            <option key={s} value={s}>{STATUS_LABELS[s] ?? s}</option>
          ))}
        </select>
      </div>

      <div className="bg-[#12121a] border border-[#1e1e2e] rounded-2xl overflow-hidden">
        {loading ? (
          <p className="p-8 text-sm text-white/30 text-center">加载中…</p>
        ) : users.length === 0 ? (
          <p className="p-8 text-sm text-white/30 text-center">暂无用户</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e1e2e] text-[11px] text-white/30 uppercase tracking-wider">
                <th className="text-left px-4 py-3">用户</th>
                <th className="text-left px-4 py-3">角色</th>
                <th className="text-left px-4 py-3">状态</th>
                <th className="text-left px-4 py-3">完成数</th>
                <th className="text-right px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => {
                const role = u.role as PlatformRole
                const color = ROLE_COLORS[role] ?? '#9ba0ad'
                return (
                  <tr key={u.id} className="border-b border-[#1e1e2e]/60 hover:bg-white/[0.02]">
                    <td className="px-4 py-3">
                      <div className="font-medium text-white/80">{u.username}</div>
                      <div className="text-[11px] text-white/30">{u.email}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ color, background: `${color}15`, border: `1px solid ${color}30` }}>
                        {ROLE_LABELS[role] ?? u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-white/50">{STATUS_LABELS[u.status] ?? u.status}</td>
                    <td className="px-4 py-3 font-mono text-white/60">{u.completed_tasks}</td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button type="button" onClick={() => openEdit(u)} className="text-xs text-[#00d4ff]/70 hover:text-[#00d4ff]">编辑</button>
                      <button type="button" onClick={() => openReset(u)} className="text-xs text-[#a78bfa]/70 hover:text-[#a78bfa]">重置密码</button>
                      {u.id !== actor?.id && u.role !== 'super_admin' && (
                        <button type="button" onClick={() => handleDelete(u)} className="text-xs text-red-400/70 hover:text-red-400">删除</button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {mode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={closeModal}>
          <div
            className="w-full max-w-md bg-[#12121a] border border-[#1e1e2e] rounded-2xl p-6 shadow-xl"
            onClick={e => e.stopPropagation()}
          >
            {mode === 'create' && (
              <>
                <h2 className="text-base font-medium mb-4">新建用户</h2>
                <form onSubmit={handleCreate} className="space-y-3">
                  {[
                    { key: 'username' as const, label: '用户名', type: 'text' },
                    { key: 'email' as const, label: '邮箱', type: 'email' },
                    { key: 'password' as const, label: '初始密码', type: 'password' },
                    { key: 'full_name' as const, label: '姓名（可选）', type: 'text' },
                  ].map(f => (
                    <div key={f.key}>
                      <label className="block text-xs text-white/40 mb-1">{f.label}</label>
                      <input
                        type={f.type}
                        required={f.key !== 'full_name'}
                        value={createForm[f.key]}
                        onChange={e => setCreateForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                        className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm"
                      />
                    </div>
                  ))}
                  <div>
                    <label className="block text-xs text-white/40 mb-1">角色</label>
                    <select
                      value={createForm.role}
                      onChange={e => setCreateForm(prev => ({ ...prev, role: e.target.value as PlatformRole }))}
                      className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm"
                    >
                      {rolesCanAssign.map(r => (
                        <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex gap-2 pt-2">
                    <button type="button" onClick={closeModal} className="flex-1 py-2 text-sm text-white/40 border border-[#1e1e2e] rounded-lg">取消</button>
                    <button type="submit" disabled={saving} className="flex-1 py-2 text-sm bg-[#7c3aed]/20 text-[#a78bfa] border border-[#7c3aed]/40 rounded-lg disabled:opacity-40">
                      {saving ? '创建中…' : '创建'}
                    </button>
                  </div>
                </form>
              </>
            )}

            {mode === 'edit' && selected && (
              <>
                <h2 className="text-base font-medium mb-1">编辑用户</h2>
                <p className="text-xs text-white/30 mb-4">{selected.username}</p>
                <form onSubmit={handleEdit} className="space-y-3">
                  <div>
                    <label className="block text-xs text-white/40 mb-1">姓名</label>
                    <input
                      value={editForm.full_name}
                      onChange={e => setEditForm(prev => ({ ...prev, full_name: e.target.value }))}
                      className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-white/40 mb-1">角色</label>
                    <select
                      value={editForm.role}
                      onChange={e => setEditForm(prev => ({ ...prev, role: e.target.value as PlatformRole }))}
                      disabled={selected.role === 'super_admin' && actor?.role !== 'super_admin'}
                      className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm disabled:opacity-50"
                    >
                      {(selected.role === 'super_admin' ? ['super_admin' as PlatformRole] : rolesCanAssign).map(r => (
                        <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-white/40 mb-1">状态</label>
                    <select
                      value={editForm.status}
                      onChange={e => setEditForm(prev => ({ ...prev, status: e.target.value }))}
                      className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm"
                    >
                      {STATUS_OPTIONS.map(s => (
                        <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex gap-2 pt-2">
                    <button type="button" onClick={closeModal} className="flex-1 py-2 text-sm text-white/40 border border-[#1e1e2e] rounded-lg">取消</button>
                    <button type="submit" disabled={saving} className="flex-1 py-2 text-sm bg-[#00d4ff]/15 text-[#00d4ff] border border-[#00d4ff]/30 rounded-lg disabled:opacity-40">
                      {saving ? '保存中…' : '保存'}
                    </button>
                  </div>
                </form>
              </>
            )}

            {mode === 'reset' && selected && (
              <>
                <h2 className="text-base font-medium mb-1">重置密码</h2>
                <p className="text-xs text-white/30 mb-4">{selected.username}</p>
                <form onSubmit={handleResetPassword} className="space-y-3">
                  <div>
                    <label className="block text-xs text-white/40 mb-1">新密码</label>
                    <input
                      type="password"
                      required
                      value={newPassword}
                      onChange={e => setNewPassword(e.target.value)}
                      className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="flex gap-2 pt-2">
                    <button type="button" onClick={closeModal} className="flex-1 py-2 text-sm text-white/40 border border-[#1e1e2e] rounded-lg">取消</button>
                    <button type="submit" disabled={saving} className="flex-1 py-2 text-sm bg-[#a78bfa]/15 text-[#a78bfa] border border-[#a78bfa]/30 rounded-lg disabled:opacity-40">
                      {saving ? '提交中…' : '重置'}
                    </button>
                  </div>
                </form>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
