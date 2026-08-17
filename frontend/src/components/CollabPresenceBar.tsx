import type { CollabPeer } from '../hooks/useYjsCollab'

/** 共编在线用户条 */
export default function CollabPresenceBar({
  peers,
  connected,
}: {
  peers: CollabPeer[]
  connected: boolean
}) {
  if (!connected && peers.length === 0) return null
  const names = peers.map(p => p.username || `#${p.user_id}`).join('、')
  return (
    <div className="px-4 py-1.5 text-[11px] bg-cyan-500/10 text-cyan-200/90 border-b border-cyan-500/20 flex items-center gap-2">
      <span
        className={`inline-block w-1.5 h-1.5 rounded-full ${connected ? 'bg-cyan-400' : 'bg-white/30'}`}
      />
      <span>
        共编 {connected ? '已连接' : '断开'}
        {peers.length > 0 ? ` · 在线 ${peers.length} 人：${names}` : ''}
      </span>
    </div>
  )
}
