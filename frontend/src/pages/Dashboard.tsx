import { useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import { isDemoEntriesEnabled } from '../utils/demoMode'

const LEVEL_COLORS: Record<string, string> = {
  novice: '#9ba0ad', junior: '#10b981', intermediate: '#00d4ff',
  senior: '#a78bfa', expert: '#f59e0b',
}

type QuickLink = { label: string; desc: string; href: string; color: string; icon: string }

/** 业务入口：一律进类别项目/任务列表，不跳演示 task id */
const PRODUCT_LINKS: QuickLink[] = [
  { label: '2D 图像标注', desc: '仅图像 2D 项目', href: '/projects?category=image_2d', color: '#00d4ff', icon: '◧' },
  { label: '3D 点云标注', desc: '仅点云项目', href: '/projects?category=pointcloud_3d', color: '#a78bfa', icon: '⬡' },
  { label: '语料 · NER', desc: '仅语料项目', href: '/projects?category=nlp', color: '#ec4899', icon: '✎' },
  { label: '语料任务', desc: '仅语言标注待办', href: '/tasks?category=nlp', color: '#f472b6', icon: '☰' },
  { label: '语音 · ASR', desc: '仅语音项目', href: '/projects?category=audio', color: '#10b981', icon: '♫' },
  { label: '视频标注', desc: '仅视频项目', href: '/projects?category=video', color: '#f59e0b', icon: '▶' },
  { label: '具身机器人', desc: '仅具身项目', href: '/projects?category=embodied', color: '#f97316', icon: '◆' },
  { label: '全部任务', desc: '领取与继续全部任务', href: '/tasks', color: '#10b981', icon: '☰' },
  { label: '全部项目', desc: '浏览与管理全部项目', href: '/projects', color: '#f59e0b', icon: '◈' },
]

/** 离线/样例入口：仅开发或 VITE_ENABLE_DEMO_ENTRIES=true 时展示 */
const DEMO_LINKS: QuickLink[] = [
  { label: '演示 · 2D 样例', desc: '硬编码 task #1001', href: '/annotate-image/1001', color: '#64748b', icon: '◧' },
  { label: '演示 · 点云样例', desc: '硬编码 task #1002', href: '/annotate-3d/1002', color: '#64748b', icon: '⬡' },
  { label: '演示 · 语料 NER', desc: '硬编码 task #3001', href: '/annotate-text/3001', color: '#64748b', icon: '✎' },
  { label: '演示 · 具身 InSight', desc: 'demo 多视角', href: '/annotate-embodied/demo', color: '#64748b', icon: '⎔' },
  { label: '演示 · ALOHA', desc: 'task #2002', href: '/annotate-embodied/2002', color: '#64748b', icon: '⬢' },
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
            <div className="text-xs text-white/30 mt-0.5">{l.desc}</div>
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
        <h1 className="text-2xl font-semibold tracking-tight">
          你好，<span style={{ color }}>{user?.username ?? '标注员'}</span>
        </h1>
        <p className="text-sm text-white/30 mt-1">
          当前等级：<span className="font-medium" style={{ color }}>{user?.level ?? 'novice'}</span>
          　·　从类别进入真实项目，不再默认跳演示任务
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {stats.map(s => (
          <div key={s.label} className="bg-[#12121a] border border-[#1e1e2e] rounded-xl p-4">
            <div className="text-[11px] text-white/30 mb-2">{s.label}</div>
            <div className="text-2xl font-semibold font-mono" style={{ color: s.color }}>
              {s.value}<span className="text-sm font-normal text-white/30 ml-1">{s.unit}</span>
            </div>
          </div>
        ))}
      </div>

      <div>
        <h2 className="text-sm font-medium text-white/50 mb-4 uppercase tracking-widest">业务入口</h2>
        <LinkGrid links={PRODUCT_LINKS} />
      </div>

      {showDemos && (
        <div>
          <h2 className="text-sm font-medium text-white/50 mb-1 uppercase tracking-widest">演示入口</h2>
          <p className="text-xs text-white/25 mb-4">
            仅开发环境或设置 <code className="text-white/40">VITE_ENABLE_DEMO_ENTRIES=true</code> 时显示；生产默认隐藏。
          </p>
          <LinkGrid links={DEMO_LINKS} />
        </div>
      )}
    </div>
  )
}
