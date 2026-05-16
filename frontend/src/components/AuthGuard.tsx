import { Navigate, useLocation } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import { hasPermission, isAdminRole } from '../utils/permissions'

interface GuardProps {
  children: React.ReactNode
}

/** Redirect to /login if not authenticated */
export function AuthGuard({ children }: GuardProps) {
  const { isAuthenticated } = useAuthStore()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return <>{children}</>
}

/** Redirect to / if already authenticated */
export function GuestGuard({ children }: GuardProps) {
  const { isAuthenticated } = useAuthStore()

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
  const { isAuthenticated, user } = useAuthStore()
  const location = useLocation()

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
