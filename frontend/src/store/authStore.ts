import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface AuthUser {
  id: number
  username: string
  email: string
  level: string
  /** 平台角色，如 super_admin / admin / annotator（与后端 UserRole 对齐） */
  role?: string
  is_admin: boolean
  skill_tags: string[]
  accuracy_rate: number
  total_completed: number
  total_earnings: number
  active_tasks: number
}

interface AuthState {
  user: AuthUser | null
  token: string | null
  isAuthenticated: boolean
  setAuth: (user: Partial<AuthUser> & Pick<AuthUser, 'id' | 'username'>, token: string) => void
  logout: () => void
  updateUser: (patch: Partial<AuthUser>) => void
}

function normalizeAuthUser(
  u: Partial<AuthUser> & Pick<AuthUser, 'id' | 'username'>
): AuthUser {
  const role = u.role ?? 'annotator'
  // 角色优先：即使本地缓存里 is_admin 为 false，admin/super_admin 仍视为管理员
  const isAdmin = role === 'super_admin' || role === 'admin' || Boolean(u.is_admin)
  return {
    id: u.id,
    username: u.username,
    email: u.email ?? '',
    level: u.level ?? 'novice',
    role,
    is_admin: isAdmin,
    skill_tags: u.skill_tags ?? [],
    accuracy_rate: u.accuracy_rate ?? 0,
    total_completed: u.total_completed ?? 0,
    total_earnings: u.total_earnings ?? 0,
    active_tasks: u.active_tasks ?? 0,
  }
}

const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      setAuth: (user, token) =>
        set({ user: normalizeAuthUser(user), token, isAuthenticated: true }),

      logout: () => set({ user: null, token: null, isAuthenticated: false }),

      updateUser: (patch) =>
        set((s) => ({
          user: s.user ? normalizeAuthUser({ ...s.user, ...patch }) : null,
        })),
    }),
    {
      name: 'dasshine_auth',
      partialize: (s) => ({ user: s.user, token: s.token, isAuthenticated: s.isAuthenticated }),
      onRehydrateStorage: () => (state) => {
        if (state?.user) {
          state.user = normalizeAuthUser(state.user)
        }
      },
    }
  )
)

export default useAuthStore
