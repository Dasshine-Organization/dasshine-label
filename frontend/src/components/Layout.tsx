import { useState } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import { isAdminRole } from '../utils/permissions'

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
    to: '/profile',
    label: '账户',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
        <circle cx="10" cy="7" r="3" />
        <path d="M4 17c0-3.3 2.7-6 6-6s6 2.7 6 6" strokeLinecap="round" />
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
      {/* Sidebar */}
      <aside
        className={`flex flex-col bg-[#12121a] border-r border-[#1e1e2e] transition-all duration-200 flex-shrink-0
          ${collapsed ? 'w-14' : 'w-52'}`}
      >
        {/* Logo */}
        <div className="h-12 flex items-center gap-2.5 px-4 border-b border-[#1e1e2e]">
          <div className="w-6 h-6 rounded-md bg-[#00d4ff]/20 border border-[#00d4ff]/40 flex items-center justify-center flex-shrink-0">
            <div className="w-2 h-2 rounded-sm bg-[#00d4ff]" />
          </div>
          {!collapsed && (
            <span className="text-sm font-semibold tracking-tight text-white/90">Dasshine</span>
          )}
          <button
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

        {/* Nav */}
        <nav className="flex-1 py-3 px-2 space-y-0.5">
          {navItems.map((item) => (
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
        </nav>

        {/* User */}
        <div className="p-3 border-t border-[#1e1e2e]">
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
            {!collapsed && (
              <button
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

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
