import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import { isDemoEntriesEnabled, subscribeDemoEntries } from '../utils/demoMode'
import { CATEGORY_HUBS } from '../utils/categoryHubs'

const LEVEL_COLORS: Record<string, string> = {
  novice: '#9ba0ad', junior: '#10b981', intermediate: '#00d4ff',
  senior: '#a78bfa', expert: '#f59e0b',
}

type QuickLink = { label: string; desc?: string; href: string; color: string; icon: string }

/** 业务入口：与侧栏类别 Hub 同源（不展示「仅 xxx」类副标题） */
const PRODUCT_LINKS: QuickLink[] = [
  ...CATEGORY_HUBS.map(h => ({
    label: `${h.label}项目`,
    href: h.projectsHref,
    color: h.color,
    icon: '◈',
  })),
  { label: '语料任务', href: '/tasks?category=nlp', color: '#f472b6', icon: '☰' },
  { label: '全部任务', href: '/tasks', color: '#10b981', icon: '☰' },
  { label: '审核工作台', href: '/review', color: '#a78bfa', icon: '☑' },
  { label: '全部项目', href: '/projects', color: '#f59e0b', icon: '◈' },
]

/** 离线/样例入口：仅开发或 VITE_ENABLE_DEMO_ENTRIES=true 时展示 */
const DEMO_LINKS: QuickLink[] = [
  { label: '演示 · 2D 样例', href: '/annotate-image/1001', color: '#64748b', icon: '◧' },
  { label: '演示 · 点云样例', href: '/annotate-3d/1002', color: '#64748b', icon: '⬡' },
  { label: '演示 · 语料 NER', href: '/annotate-text/3001', color: '#64748b', icon: '✎' },
  { label: '演示 · 具身 InSight', href: '/annotate-embodied/demo', color: '#64748b', icon: '⎔' },
  { label: '演示 · ALOHA', href: '/annotate-embodied/2002', color: '#64748b', icon: '⬢' },
]

function LinkGrid({ links }: { links: QuickLink[] }) {
  const navigate = useNavigate()
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {links.map(l => (
        <button
          key={l.href + l.label}
          type="button"
          onClick={() => navigate(l.href)}
          className="flex items-center gap-4 p-4 bg-[#12121a] border border-[#1e1e2e] rounded-xl text-left
            hover:border-white/20 active:scale-[0.98] transition-all group"
        >
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
            style={{ background: `${l.color}15`, border: `1px solid ${l.color}30`, color: l.color }}
          >
            {l.icon}
          </div>
          <div>
            <div className="text-sm font-medium text-white/80 group-hover:text-white transition-colors">{l.label}</div>
            {l.desc ? <div className="text-xs text-white/30 mt-0.5">{l.desc}</div> : null}
          </div>
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"
            className="w-4 h-4 text-white/20 group-hover:text-white/50 ml-auto transition-colors">
            <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuthStore()
  const color = LEVEL_COLORS[user?.level ?? 'novice']
  const [, setDemoTick] = useState(0)
  useEffect(() => subscribeDemoEntries(() => setDemoTick(t => t + 1)), [])
  const showDemos = isDemoEntriesEnabled()

  const stats = [
    { label: '今日任务', value: user?.active_tasks ?? 0, unit: '个', color: '#00d4ff' },
    { label: '累计完成', value: user?.total_completed ?? 0, unit: '个', color: '#10b981' },
    { label: '准确率', value: `${((user?.accuracy_rate ?? 0.6) * 100).toFixed(1)}`, unit: '%', color: '#a78bfa' },
    { label: '累计收益', value: `¥${(user?.total_earnings ?? 0).toFixed(2)}`, unit: '', color: '#f59e0b' },
  ]

  return (
    <div className="p-8 space-y-8 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold">
          你好，<span style={{ color }}>{user?.username}</span>
        </h1>
        <p className="text-xs text-white/30 mt-1">从类别入口进入真实项目，或领取任务开始标注</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats.map(s => (
          <div key={s.label} className="bg-[#12121a] border border-[#1e1e2e] rounded-xl p-4">
            <div className="text-[10px] text-white/30 mb-1">{s.label}</div>
            <div className="text-lg font-mono font-semibold" style={{ color: s.color }}>
              {s.value}
              <span className="text-xs text-white/30 ml-1">{s.unit}</span>
            </div>
          </div>
        ))}
      </div>

      <section>
        <h2 className="text-sm font-medium text-white/60 mb-3">业务入口</h2>
        <LinkGrid links={PRODUCT_LINKS} />
      </section>

      {showDemos && (
        <section>
          <h2 className="text-sm font-medium text-white/40 mb-3">演示入口</h2>
          <LinkGrid links={DEMO_LINKS} />
        </section>
      )}
    </div>
  )
}
