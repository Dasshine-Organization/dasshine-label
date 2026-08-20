import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import { hasPermission, isAdminRole } from '../utils/permissions'

interface GuardProps {
  children: React.ReactNode
}

/** Zustand persist 未完成前不要判登录，否则会闪到 /login 再弹回（E2E/刷新都会踩）。 */
function useAuthHydrated() {
  const [hydrated, setHydrated] = useState(() => useAuthStore.persist.hasHydrated())
  useEffect(() => {
    setHydrated(useAuthStore.persist.hasHydrated())
    return useAuthStore.persist.onFinishHydration(() => setHydrated(true))
  }, [])
  return hydrated
}

/** Redirect to /login if not authenticated */
export function AuthGuard({ children }: GuardProps) {
  const hydrated = useAuthHydrated()
  const { isAuthenticated } = useAuthStore()
  const location = useLocation()

  if (!hydrated) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center text-white/30 text-xs">
        加载中…
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return <>{children}</>
}

/** Redirect to / if already authenticated */
export function GuestGuard({ children }: GuardProps) {
  const hydrated = useAuthHydrated()
  const { isAuthenticated } = useAuthStore()

  if (!hydrated) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center text-white/30 text-xs">
        加载中…
      </div>
    )
  }

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}

interface AdminGuardProps extends GuardProps {
  /** 需要特定权限时使用，默认仅要求 is_admin */
  permission?: string
}

/** 管理员路由守卫 */
export function AdminGuard({ children, permission = 'users.manage' }: AdminGuardProps) {
  const hydrated = useAuthHydrated()
  const { isAuthenticated, user } = useAuthStore()
  const location = useLocation()

  if (!hydrated) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center text-white/30 text-xs">
        加载中…
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  const allowed =
    user?.is_admin ||
    isAdminRole(user?.role) ||
    hasPermission(user?.role, permission)

  if (!allowed) {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
