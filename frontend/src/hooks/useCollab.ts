/** Automerge 任务共编：对象 Map + 稀疏像素/点标签 CRDT。 */

import { useCallback, useEffect, useRef, useState } from 'react'
import * as A from '@automerge/automerge'
import useAuthStore from '../store/authStore'
import { isDemoTaskId } from '../utils/annotationRoutes'

export type CollabPeer = { user_id: number; username?: string }

type CollabDoc = {
  objects: Record<string, unknown>
  pixels: Record<string, string>
  pointLabels: Record<string, string>
  payload: Record<string, unknown>
}

function emptyDoc(): CollabDoc {
  return { objects: {}, pixels: {}, pointLabels: {}, payload: {} }
}

function wsBase(): string {
  const api = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
  try {
    const u = new URL(api, window.location.origin)
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
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

function clonePlain<T>(v: T): T {
  return JSON.parse(JSON.stringify(v)) as T
}

function stripUndef(obj: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(obj)) {
    if (v === undefined) continue
    out[k] = v
  }
  return out
}

function loadOrInit(bytes: Uint8Array): A.Doc<CollabDoc> {
  if (!bytes.length) return A.from<CollabDoc>(emptyDoc())
  try {
    return A.load<CollabDoc>(bytes)
  } catch {
    return A.from<CollabDoc>(emptyDoc())
  }
}

function docToDraft(doc: A.Doc<CollabDoc>): Record<string, unknown> {
  const objects = (doc.objects || {}) as Record<string, Record<string, unknown>>
  const annotations2d: Record<string, unknown>[] = []
  const boxes3d: Record<string, unknown>[] = []
  for (const [id, val] of Object.entries(objects)) {
    if (!val || typeof val !== 'object') continue
    const o = clonePlain(val)
    if (id.startsWith('b:') || o.center) {
      boxes3d.push({ ...o, id: String(o.id || id.replace(/^b:/, '')) })
    } else if (id.startsWith('a:') || o.points) {
      annotations2d.push({ ...o, id: String(o.id || id.replace(/^a:/, '')) })
    }
  }
  return {
    ...clonePlain((doc.payload || {}) as Record<string, unknown>),
    annotations2d,
    boxes3d,
    pixelLabels: clonePlain(doc.pixels || {}),
    pointLabels: clonePlain(doc.pointLabels || {}),
  }
}

export function useCollab(
  taskId: string | undefined,
  enabled = true,
  onRemoteDraft?: (draft: Record<string, unknown>) => void,
) {
  const token = useAuthStore(s => s.token)
  const user = useAuthStore(s => s.user)
  const [peers, setPeers] = useState<CollabPeer[]>([])
  const [connected, setConnected] = useState(false)
  const docRef = useRef<A.Doc<CollabDoc> | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const applyingRemote = useRef(false)
  const pushedA = useRef<Set<string>>(new Set())
  const pushedB = useRef<Set<string>>(new Set())
  const pushedPixels = useRef<Set<string>>(new Set())
  const pushedPoints = useRef<Set<string>>(new Set())

  const syncPushed = useCallback((doc: A.Doc<CollabDoc>) => {
    const objs = doc.objects || {}
    pushedA.current = new Set(Object.keys(objs).filter(k => k.startsWith('a:')))
    pushedB.current = new Set(Object.keys(objs).filter(k => k.startsWith('b:')))
    pushedPixels.current = new Set(Object.keys(doc.pixels || {}))
    pushedPoints.current = new Set(Object.keys(doc.pointLabels || {}))
  }, [])

  const sendChanges = useCallback((before: A.Doc<CollabDoc>, after: A.Doc<CollabDoc>) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    let changes: Uint8Array[] = []
    try {
      changes = A.getChanges(before, after)
    } catch {
      const last = A.getLastLocalChange(after)
      if (last) changes = [last]
    }
    for (const ch of changes) {
      ws.send(
        JSON.stringify({
          type: 'update',
          engine: 'automerge',
          update_b64: toB64(ch),
        }),
      )
    }
  }, [])

  const persist = useCallback(() => {
    const doc = docRef.current
    const ws = wsRef.current
    if (!doc || !ws || ws.readyState !== WebSocket.OPEN) return
    ws.send(
      JSON.stringify({
        type: 'persist',
        engine: 'automerge',
        state_b64: toB64(A.save(doc)),
      }),
    )
  }, [])

  const pushDraft = useCallback(
    (draft: Record<string, unknown>) => {
      const doc = docRef.current
      const ws = wsRef.current
      if (!doc || !ws || ws.readyState !== WebSocket.OPEN) return
      applyingRemote.current = true
      try {
        const next = A.change(doc, d => {
          if (!d.objects) d.objects = {}
          if (!d.pixels) d.pixels = {}
          if (!d.pointLabels) d.pointLabels = {}
          if (!d.payload) d.payload = {}
          if (Array.isArray(draft.annotations2d)) {
            const ids = new Set<string>()
            for (const raw of draft.annotations2d) {
              if (!raw || typeof raw !== 'object') continue
              const a = raw as { id?: string }
              if (!a.id) continue
              const key = `a:${a.id}`
              ids.add(key)
              d.objects[key] = stripUndef(clonePlain(raw as Record<string, unknown>))
            }
            for (const k of pushedA.current) {
              if (!ids.has(k)) delete d.objects[k]
            }
            pushedA.current = ids
          }
          if (Array.isArray(draft.boxes3d)) {
            const ids = new Set<string>()
            for (const raw of draft.boxes3d) {
              if (!raw || typeof raw !== 'object') continue
              const a = raw as { id?: string }
              if (!a.id) continue
              const key = `b:${a.id}`
              ids.add(key)
              d.objects[key] = stripUndef(clonePlain(raw as Record<string, unknown>))
            }
            for (const k of pushedB.current) {
              if (!ids.has(k)) delete d.objects[k]
            }
            pushedB.current = ids
          }
          if (draft.pixelLabels && typeof draft.pixelLabels === 'object') {
            const pix = draft.pixelLabels as Record<string, string>
            const ids = new Set(Object.keys(pix))
            for (const [k, v] of Object.entries(pix)) d.pixels[k] = String(v)
            for (const k of pushedPixels.current) {
              if (!ids.has(k)) delete d.pixels[k]
            }
            pushedPixels.current = ids
          }
          if (draft.pointLabels && typeof draft.pointLabels === 'object') {
            const pts = draft.pointLabels as Record<string, string>
            const ids = new Set(Object.keys(pts))
            for (const [k, v] of Object.entries(pts)) d.pointLabels[k] = String(v)
            for (const k of pushedPoints.current) {
              if (!ids.has(k)) delete d.pointLabels[k]
            }
            pushedPoints.current = ids
          }
          const skip = new Set([
            'annotations2d',
            'boxes3d',
            'pixelLabels',
            'pointLabels',
          ])
          for (const [k, v] of Object.entries(draft)) {
            if (skip.has(k) || v === undefined) continue
            d.payload[k] = v as never
          }
          d.payload.updated_by = user?.id ?? null
          d.payload.updated_at = Date.now()
        })
        sendChanges(doc, next)
        docRef.current = next
      } finally {
        applyingRemote.current = false
      }
    },
    [sendChanges, user?.id],
  )

  useEffect(() => {
    if (!enabled || !token || !taskId || !/^\d+$/.test(taskId) || isDemoTaskId(taskId)) {
      setPeers([])
      setConnected(false)
      return
    }

    let doc = A.from<CollabDoc>(emptyDoc())
    docRef.current = doc
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
          applyingRemote.current = true
          try {
            doc = loadOrInit(raw)
            docRef.current = doc
            syncPushed(doc)
            if (raw.length && onRemoteDraft) onRemoteDraft(docToDraft(doc))
          } finally {
            applyingRemote.current = false
          }
          setPeers(Array.isArray(msg.presence) ? msg.presence : [])
        } else if (msg.type === 'update' && msg.update_b64) {
          const cur = docRef.current
          if (!cur) return
          applyingRemote.current = true
          try {
            const next = A.applyChanges(cur, [fromB64(msg.update_b64)])[0]
            docRef.current = next
            syncPushed(next)
            if (onRemoteDraft) onRemoteDraft(docToDraft(next))
          } catch {
            /* 非 Automerge 变更忽略 */
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
      docRef.current = null
      wsRef.current = null
      setConnected(false)
      setPeers([])
    }
  }, [taskId, token, enabled, onRemoteDraft, persist, syncPushed])

  return { peers, connected, pushDraft, persist, engine: 'automerge' as const }
}

/** @deprecated 使用 useCollab；保留导出以免旧引用断裂 */
export const useYjsCollab = useCollab
