import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import { isAdminRole } from '../utils/permissions'
import { CATEGORY_HUBS } from '../utils/categoryHubs'
import OrgSwitcher from './OrgSwitcher'
import NotificationBell from './NotificationBell'

const NAV = [
  {
    to: '/',
    label: '工作台',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
        <rect x="2" y="2" width="7" height="7" rx="1.5" />
        <rect x="11" y="2" width="7" height="7" rx="1.5" />
        <rect x="2" y="11" width="7" height="7" rx="1.5" />
        <rect x="11" y="11" width="7" height="7" rx="1.5" />
      </svg>
    ),
  },
  {
    to: '/projects',
    label: '项目',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
        <path d="M3 6a2 2 0 012-2h3l2 2h5a2 2 0 012 2v7a2 2 0 01-2 2H5a2 2 0 01-2-2V6z" />
      </svg>
    ),
  },
  {
    to: '/tasks',
    label: '任务',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
        <path d="M9 5H7a2 2 0 00-2 2v8a2 2 0 002 2h6a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h0a2 2 0 002-2M9 5a2 2 0 012-2h0a2 2 0 012 2" strokeLinecap="round" />
        <path d="M7 11l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    to: '/review',
    label: '审核',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
        <path d="M4 4h12v12H4z" strokeLinejoin="round" />
        <path d="M7 10l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    to: '/leaderboard',
    label: '排行榜',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
        <path d="M4 16V9h3v7H4zM8.5 16V5h3v11h-3zM13 16v-4h3v4h-3z" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    to: '/profile',
    label: '账户',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
        <circle cx="10" cy="7" r="3" />
        <path d="M4 17c0-3.3 2.7-6 6-6s6 2.7 6 6" strokeLinecap="round" />
      </svg>
    ),
  },
]

const ADMIN_NAV = {
  to: '/users',
  label: '用户管理',
  icon: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <path d="M7 8a3 3 0 106 0 3 3 0 00-6 0zM3 17c0-2.8 2.2-5 5-5h4c2.8 0 5 2.2 5 5" strokeLinecap="round" />
    </svg>
  ),
}

export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const showAdmin = user?.is_admin || isAdminRole(user?.role)
  const navItems = showAdmin ? [...NAV, ADMIN_NAV] : NAV

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-[#0a0a0f] text-white overflow-hidden">
      <aside
        className={`flex flex-col bg-[#12121a] border-r border-[#1e1e2e] transition-all duration-200 flex-shrink-0
          ${collapsed ? 'w-14' : 'w-52'}`}
      >
        <div className="h-12 flex items-center gap-2.5 px-4 border-b border-[#1e1e2e]">
          <div className="w-6 h-6 rounded-md bg-[#00d4ff]/20 border border-[#00d4ff]/40 flex items-center justify-center flex-shrink-0">
            <div className="w-2 h-2 rounded-sm bg-[#00d4ff]" />
          </div>
          {!collapsed && (
            <span className="text-sm font-semibold tracking-tight text-white/90">Dasshine</span>
          )}
          <button
            type="button"
            onClick={() => setCollapsed(v => !v)}
            className="ml-auto text-white/20 hover:text-white/60 transition-colors"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
              {collapsed
                ? <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
                : <path d="M10 4L6 8l4 4" strokeLinecap="round" strokeLinejoin="round" />}
            </svg>
          </button>
        </div>

        <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm transition-all
                ${isActive
                  ? 'bg-[#00d4ff]/10 text-[#00d4ff] ring-1 ring-[#00d4ff]/20'
                  : 'text-white/40 hover:text-white/70 hover:bg-white/5'}`
              }
            >
              <span className="flex-shrink-0">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}

          {!collapsed && (
            <div className="pt-3 mt-2 border-t border-[#1e1e2e]/80">
              <div className="px-2.5 mb-1.5 text-[10px] uppercase tracking-wider text-white/25">
                类别入口
              </div>
              {CATEGORY_HUBS.map(hub => (
                <NavLink
                  key={hub.id}
                  to={hub.projectsHref}
                  className={({ isActive }) =>
                    `flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs transition-all
                    ${isActive
                      ? 'bg-white/5 text-white/80'
                      : 'text-white/35 hover:text-white/65 hover:bg-white/[0.03]'}`
                  }
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ background: hub.color }}
                  />
                  <span className="truncate">{hub.label}</span>
                </NavLink>
              ))}
            </div>
          )}
        </nav>

        <div className="p-3 border-t border-[#1e1e2e]">
          <OrgSwitcher collapsed={collapsed} />
          <div className="flex items-center gap-2.5 px-1">
            <div className="w-7 h-7 rounded-full bg-[#7c3aed]/30 border border-[#7c3aed]/40 flex items-center justify-center flex-shrink-0">
              <span className="text-[10px] font-medium text-[#a78bfa]">
                {user?.username?.[0]?.toUpperCase() ?? 'U'}
              </span>
            </div>
            {!collapsed && (
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium text-white/80 truncate">{user?.username}</div>
                <div className="text-[10px] text-white/30 capitalize">{user?.level ?? 'novice'}</div>
              </div>
            )}
            <NotificationBell />
            {!collapsed && (
              <button
                type="button"
                onClick={handleLogout}
                className="text-white/20 hover:text-red-400 transition-colors"
                title="退出登录"
              >
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
                  <path d="M6 3H3a1 1 0 00-1 1v8a1 1 0 001 1h3M10 5l3 3-3 3M6 8h7" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
