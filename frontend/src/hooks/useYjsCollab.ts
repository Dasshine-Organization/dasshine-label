/** Yjs 任务共编：WebSocket 中继 + draft Map 同步。 */

import { useCallback, useEffect, useRef, useState } from 'react'
import * as Y from 'yjs'
import useAuthStore from '../store/authStore'
import { isDemoTaskId } from '../utils/annotationRoutes'

export type CollabPeer = { user_id: number; username?: string }

function wsBase(): string {
  const api = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
  try {
    const u = new URL(api, window.location.origin)
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
    // api path 常为 .../api/v1 → 拼 /ws/...
    const base = u.origin
    const path = u.pathname.replace(/\/$/, '')
    return `${base}${path}`
  } catch {
    return 'ws://localhost:8000/api/v1'
  }
}

function toB64(u8: Uint8Array): string {
  let s = ''
  u8.forEach(b => {
    s += String.fromCharCode(b)
  })
  return btoa(s)
}

function fromB64(s: string): Uint8Array {
  if (!s) return new Uint8Array()
  const bin = atob(s)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i)
  return out
}

export function useYjsCollab(
  taskId: string | undefined,
  enabled = true,
  onRemoteDraft?: (draft: Record<string, unknown>) => void,
) {
  const token = useAuthStore(s => s.token)
  const user = useAuthStore(s => s.user)
  const [peers, setPeers] = useState<CollabPeer[]>([])
  const [connected, setConnected] = useState(false)
  const docRef = useRef<Y.Doc | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const applyingRemote = useRef(false)

  const pushDraft = useCallback((draft: Record<string, unknown>) => {
    const doc = docRef.current
    const ws = wsRef.current
    if (!doc || !ws || ws.readyState !== WebSocket.OPEN) return
    applyingRemote.current = true
    try {
      const map = doc.getMap('draft')
      map.set('payload', draft)
      map.set('updated_by', user?.id ?? null)
      map.set('updated_at', Date.now())
      const update = Y.encodeStateAsUpdate(doc)
      ws.send(JSON.stringify({ type: 'update', update_b64: toB64(update) }))
    } finally {
      applyingRemote.current = false
    }
  }, [user?.id])

  const persist = useCallback(() => {
    const doc = docRef.current
    const ws = wsRef.current
    if (!doc || !ws || ws.readyState !== WebSocket.OPEN) return
    const update = Y.encodeStateAsUpdate(doc)
    ws.send(JSON.stringify({ type: 'persist', state_b64: toB64(update) }))
  }, [])

  useEffect(() => {
    if (!enabled || !token || !taskId || !/^\d+$/.test(taskId) || isDemoTaskId(taskId)) {
      setPeers([])
      setConnected(false)
      return
    }

    const doc = new Y.Doc()
    docRef.current = doc
    const map = doc.getMap('draft')
    map.observe(() => {
      if (applyingRemote.current) return
      const payload = map.get('payload')
      if (payload && typeof payload === 'object' && onRemoteDraft) {
        onRemoteDraft(payload as Record<string, unknown>)
      }
    })

    const url = `${wsBase()}/ws/tasks/${taskId}/collab?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)
    ws.onmessage = ev => {
      try {
        const msg = JSON.parse(String(ev.data))
        if (msg.type === 'init') {
          const raw = fromB64(msg.state_b64 || '')
          if (raw.length) {
            applyingRemote.current = true
            try {
              Y.applyUpdate(doc, raw)
            } finally {
              applyingRemote.current = false
            }
          }
          setPeers(Array.isArray(msg.presence) ? msg.presence : [])
        } else if (msg.type === 'update' && msg.update_b64) {
          applyingRemote.current = true
          try {
            Y.applyUpdate(doc, fromB64(msg.update_b64))
          } finally {
            applyingRemote.current = false
          }
        } else if (msg.type === 'presence') {
          setPeers(Array.isArray(msg.presence) ? msg.presence : [])
        }
      } catch {
        /* ignore */
      }
    }

    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
        persist()
      }
    }, 30_000)

    return () => {
      clearInterval(ping)
      try {
        persist()
      } catch {
        /* ignore */
      }
      ws.close()
      doc.destroy()
      docRef.current = null
      wsRef.current = null
      setConnected(false)
      setPeers([])
    }
  }, [taskId, token, enabled, onRemoteDraft, persist])

  return { peers, connected, pushDraft, persist }
}
