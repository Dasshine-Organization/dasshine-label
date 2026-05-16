import { useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import { getAnnotatePath } from '../utils/annotationRoutes'

const LEVEL_COLORS: Record<string, string> = {
  novice: '#9ba0ad', junior: '#10b981', intermediate: '#00d4ff',
  senior: '#a78bfa', expert: '#f59e0b',
}

type QuickLink =
  | { label: string; desc: string; taskId: number; mode: '2d' | '3d'; color: string; icon: string }
  | { label: string; desc: string; href: string; color: string; icon: string }

const QUICK_LINKS: QuickLink[] = [
  { label: '2D 图像标注', desc: '矩形框 / 多边形 / 关键点', taskId: 1001, mode: '2d', color: '#00d4ff', icon: '◧' },
  { label: '自动驾驶点云标注', desc: '三维 LiDAR 包围盒', taskId: 1002, mode: '3d', color: '#a78bfa', icon: '⬡' },
  { label: '任务列表', desc: '查看并领取待标注任务', href: '/tasks', color: '#10b981', icon: '☰' },
  { label: '项目管理', desc: '浏览所有标注项目', href: '/projects', color: '#f59e0b', icon: '◈' },
]

export default function Dashboard() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const color = LEVEL_COLORS[user?.level ?? 'novice']

  const stats = [
    { label: '今日任务', value: user?.active_tasks ?? 0,      unit: '个', color: '#00d4ff' },
    { label: '累计完成', value: user?.total_completed ?? 0,   unit: '个', color: '#10b981' },
    { label: '准确率',   value: `${((user?.accuracy_rate ?? 0.6) * 100).toFixed(1)}`, unit: '%', color: '#a78bfa' },
    { label: '累计收益', value: `¥${(user?.total_earnings ?? 0).toFixed(2)}`, unit: '', color: '#f59e0b' },
  ]

  return (
    <div className="p-8 space-y-8 max-w-4xl">
      {/* Welcome */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          你好，<span style={{ color }}>{user?.username ?? '标注员'}</span> 👋
        </h1>
        <p className="text-sm text-white/30 mt-1">
          当前等级：<span className="font-medium" style={{ color }}>{user?.level ?? 'novice'}</span>
          　·　今日继续加油！
        </p>
      </div>

      {/* Stats */}
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

      {/* Quick links */}
      <div>
        <h2 className="text-sm font-medium text-white/50 mb-4 uppercase tracking-widest">快速开始</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {QUICK_LINKS.map(l => {
            const href = 'href' in l ? l.href : getAnnotatePath(l.taskId, l.mode)
            return (
            <button
              key={href}
              onClick={() => navigate(href)}
              className="flex items-center gap-4 p-4 bg-[#12121a] border border-[#1e1e2e] rounded-xl text-left
                hover:border-white/20 active:scale-[0.98] transition-all group"
            >
              <div className="w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0"
                style={{ background: `${l.color}15`, border: `1px solid ${l.color}30`, color: l.color }}>
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
          )})}
        </div>
      </div>
    </div>
  )
}
