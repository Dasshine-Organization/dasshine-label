import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { notificationsApi } from '../services/api'
import useAuthStore from '../store/authStore'

type Notif = {
  id: number
  type: string
  title: string
  body?: string
  payload?: Record<string, unknown>
  read: boolean
  created_at?: string
}

export default function NotificationBell() {
  const { token } = useAuthStore()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [unread, setUnread] = useState(0)
  const [items, setItems] = useState<Notif[]>([])

  const load = useCallback(async () => {
    if (!token) return
    try {
      const { data } = await notificationsApi.list({ limit: 30 })
      setUnread(data.unread ?? 0)
      setItems(data.items ?? [])
    } catch {
      /* ignore */
    }
  }, [token])

  useEffect(() => {
    load()
    const t = window.setInterval(load, 45000)
    return () => window.clearInterval(t)
  }, [load])

  async function onOpen() {
    setOpen(v => !v)
    if (!open) await load()
  }

  async function markAll() {
    try {
      await notificationsApi.markAllRead()
      await load()
    } catch {
      message.error('标记失败')
    }
  }

  async function clickItem(n: Notif) {
    try {
      if (!n.read) await notificationsApi.markRead(n.id)
    } catch {
      /* ignore */
    }
    const tid = n.payload?.task_id
    const pid = n.payload?.project_id
    setOpen(false)
    await load()
    if (typeof tid === 'number') {
      if (typeof pid === 'number') navigate(`/projects/${pid}/tasks`)
      else navigate('/tasks')
    }
  }

  if (!token) return null

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => void onOpen()}
        className="relative p-1.5 rounded-lg text-white/40 hover:text-white/80 hover:bg-white/5"
        title="通知"
      >
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
          <path d="M10 2a5 5 0 015 5v2.5l1.2 2.4a1 1 0 01-.9 1.5H4.7a1 1 0 01-.9-1.5L5 9.5V7a5 5 0 015-5z" />
          <path d="M8 16a2 2 0 004 0" strokeLinecap="round" />
        </svg>
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[14px] h-3.5 px-0.5 rounded-full bg-[#ef4444] text-[9px] text-white flex items-center justify-center">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-9 w-80 max-h-96 overflow-hidden rounded-xl border border-[#1e1e2e] bg-[#12121a] shadow-xl z-50">
          <div className="flex items-center justify-between px-3 py-2 border-b border-[#1e1e2e]">
            <span className="text-xs text-white/60">通知</span>
            <button type="button" onClick={() => void markAll()} className="text-[10px] text-[#00d4ff]/80">
              全部已读
            </button>
          </div>
          <div className="overflow-y-auto max-h-80">
            {items.length === 0 ? (
              <div className="text-[11px] text-white/30 p-4 text-center">暂无通知</div>
            ) : (
              items.map(n => (
                <button
                  key={n.id}
                  type="button"
                  onClick={() => void clickItem(n)}
                  className={`w-full text-left px-3 py-2.5 border-b border-[#1e1e2e]/60 hover:bg-white/5 ${
                    n.read ? 'opacity-60' : ''
                  }`}
                >
                  <div className="text-xs text-white/80">{n.title}</div>
                  {n.body && <div className="text-[10px] text-white/40 mt-0.5 line-clamp-2">{n.body}</div>}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
