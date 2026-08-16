import { useCallback, useEffect, useState } from 'react'
import { message } from 'antd'
import { projectApi, userApi, type UserRecord } from '../../services/api'

type Member = {
  user_id: number
  username: string
  level: string
  role: string
  accuracy_score?: number
  completed_tasks?: number
}

const ROLES = [
  { id: 'annotator', label: '标注员' },
  { id: 'reviewer', label: '审核员' },
  { id: 'manager', label: '管理员' },
]

interface Props {
  projectId: number
}

export default function ProjectMembersPanel({ projectId }: Props) {
  const [open, setOpen] = useState(false)
  const [members, setMembers] = useState<Member[]>([])
  const [users, setUsers] = useState<UserRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [addUserId, setAddUserId] = useState('')
  const [addRole, setAddRole] = useState('annotator')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await projectApi.getMembers(projectId)
      setMembers(data ?? [])
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '加载成员失败')
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    if (open) load()
  }, [open, load])

  useEffect(() => {
    if (!open) return
    userApi
      .getList({ limit: 100 })
      .then(res => setUsers(res.data ?? []))
      .catch(() => setUsers([]))
  }, [open])

  async function handleAdd() {
    const uid = Number(addUserId)
    if (!uid) {
      message.warning('请选择用户')
      return
    }
    try {
      await projectApi.addMember(projectId, uid, addRole)
      message.success('已添加成员')
      setAddUserId('')
      load()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '添加失败')
    }
  }

  async function handleRemove(userId: number) {
    try {
      await projectApi.removeMember(projectId, userId)
      message.success('已移除')
      load()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '移除失败')
    }
  }

  const memberIds = new Set(members.map(m => m.user_id))
  const candidates = users.filter(u => !memberIds.has(u.id))

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="px-3 py-1.5 rounded-lg text-xs border border-[#1e1e2e] text-white/50
          hover:text-white/70 hover:border-white/20 transition-all"
      >
        成员管理{members.length ? ` (${members.length})` : ''}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 z-40 w-80 bg-[#12121a] border border-[#1e1e2e] rounded-xl shadow-xl p-3 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs text-white/60">项目成员</div>
            <button type="button" onClick={() => setOpen(false)} className="text-white/30 text-xs hover:text-white/60">
              关闭
            </button>
          </div>

          {loading ? (
            <div className="text-[11px] text-white/30 py-4 text-center">加载中…</div>
          ) : members.length === 0 ? (
            <div className="text-[11px] text-white/30 py-3 text-center">暂无成员</div>
          ) : (
            <div className="max-h-40 overflow-y-auto space-y-1">
              {members.map(m => (
                <div
                  key={m.user_id}
                  className="flex items-center justify-between px-2 py-1.5 rounded-lg bg-[#0a0a0f] text-xs"
                >
                  <div>
                    <span className="text-white/70">{m.username}</span>
                    <span className="text-white/30 ml-2">{m.role}</span>
                  </div>
                  {m.role !== 'owner' && (
                    <button
                      type="button"
                      onClick={() => handleRemove(m.user_id)}
                      className="text-[10px] text-[#ef4444]/70 hover:text-[#ef4444]"
                    >
                      移除
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="border-t border-[#1e1e2e] pt-3 space-y-2">
            <div className="text-[10px] text-white/35 uppercase tracking-wider">添加成员</div>
            <select
              value={addUserId}
              onChange={e => setAddUserId(e.target.value)}
              className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-2 py-1.5 text-xs text-white/70"
            >
              <option value="">选择用户…</option>
              {candidates.map(u => (
                <option key={u.id} value={u.id}>
                  {u.username} ({u.role})
                </option>
              ))}
            </select>
            <div className="flex gap-2">
              <select
                value={addRole}
                onChange={e => setAddRole(e.target.value)}
                className="flex-1 bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-2 py-1.5 text-xs text-white/70"
              >
                {ROLES.map(r => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleAdd}
                className="px-3 py-1.5 rounded-lg text-xs border border-[#00d4ff]/30 text-[#00d4ff] hover:bg-[#00d4ff]/10"
              >
                添加
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
