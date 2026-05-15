import type { AuthUser } from '../store/authStore'

/** 项目内角色（可由任务入口 URL 传入 ?pm=owner|manager|annotator|reviewer） */
export type ProjectMemberRole = 'owner' | 'manager' | 'annotator' | 'reviewer' | 'viewer'

export function parseProjectMemberRole(raw: string | null): ProjectMemberRole | null {
  if (!raw) return null
  const v = raw.toLowerCase()
  if (['owner', 'manager', 'annotator', 'reviewer', 'viewer'].includes(v)) return v as ProjectMemberRole
  return null
}

/**
 * 新建/修改标签类：超级管理员、平台管理员、项目 owner/manager/annotator；
 * 未传 pm 时视为有编辑权限（兼容旧链接）。
 */
export function canAddOrEditLabelClasses(
  user: AuthUser | null,
  projectMember: ProjectMemberRole | null
): boolean {
  if (!user) return false
  const r = user.role ?? ''
  if (r === 'super_admin' || r === 'admin') return true
  if (!projectMember) return true
  if (projectMember === 'viewer' || projectMember === 'reviewer') return false
  return ['owner', 'manager', 'annotator'].includes(projectMember)
}

/** 删除标签类：仅超级管理员或项目所有者 */
export function canDeleteLabelClasses(user: AuthUser | null, isProjectOwner: boolean): boolean {
  if (!user) return false
  if (user.role === 'super_admin') return true
  return isProjectOwner
}

/** 项目所有者：URL ?pm=owner，或与 ?creator=<用户id> 一致 */
export function resolveIsProjectOwner(
  user: AuthUser | null,
  projectMember: ProjectMemberRole | null,
  creatorUserIdParam: string | null
): boolean {
  if (projectMember === 'owner') return true
  if (user && creatorUserIdParam != null && creatorUserIdParam !== '') {
    const n = Number(creatorUserIdParam)
    if (!Number.isNaN(n) && user.id === n) return true
  }
  return false
}
