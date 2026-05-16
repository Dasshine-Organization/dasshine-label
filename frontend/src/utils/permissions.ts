/** 平台角色与权限（与后端 UserRole / PLATFORM_PERMISSIONS 对齐） */

export type PlatformRole =
  | 'super_admin'
  | 'admin'
  | 'manager'
  | 'annotator'
  | 'reviewer'

export const ROLE_LABELS: Record<PlatformRole, string> = {
  super_admin: '超级管理员',
  admin: '管理员',
  manager: '项目经理',
  annotator: '标注员',
  reviewer: '审核员',
}

export const ROLE_COLORS: Record<PlatformRole, string> = {
  super_admin: '#f59e0b',
  admin: '#ef4444',
  manager: '#00d4ff',
  annotator: '#10b981',
  reviewer: '#a78bfa',
}

export const STATUS_LABELS: Record<string, string> = {
  active: '活跃',
  inactive: '未激活',
  suspended: '已暂停',
  deleted: '已删除',
}

const PLATFORM_PERMISSIONS: Record<PlatformRole, string[]> = {
  super_admin: [
    'users.manage',
    'users.assign_role',
    'users.reset_password',
    'projects.manage',
    'tasks.manage',
    'export.run',
    'quality.run',
  ],
  admin: [
    'users.manage',
    'users.assign_role',
    'users.reset_password',
    'projects.manage',
    'tasks.manage',
    'export.run',
    'quality.run',
  ],
  manager: ['projects.manage', 'tasks.manage', 'export.run'],
  reviewer: ['tasks.review'],
  annotator: [],
}

export function isAdminRole(role?: string | null): boolean {
  return role === 'super_admin' || role === 'admin'
}

export function hasPermission(role: string | undefined | null, permission: string): boolean {
  if (!role) return false
  const perms = PLATFORM_PERMISSIONS[role as PlatformRole] ?? []
  return perms.includes(permission)
}

/** 当前操作者可分配的角色 */
export function assignableRoles(actorRole?: string | null): PlatformRole[] {
  if (actorRole === 'super_admin') {
    return ['super_admin', 'admin', 'manager', 'annotator', 'reviewer']
  }
  if (actorRole === 'admin') {
    return ['admin', 'manager', 'annotator', 'reviewer']
  }
  return []
}

export const MIN_PASSWORD_LENGTH = 6

export function validatePassword(password: string): string | null {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `密码至少 ${MIN_PASSWORD_LENGTH} 位`
  }
  return null
}
