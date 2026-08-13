import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import useAuthStore from '../store/authStore'
import type { ProjectSummary } from '../types/project'
import { resolveProjectAnnotatePath } from '../utils/annotationRoutes'
import { CATEGORY_HUB_BY_ID } from '../utils/categoryHubs'
import { hasPermission, isAdminRole } from '../utils/permissions'
import CreateProjectModal from '../components/project/CreateProjectModal'
import DispatchModal from '../components/project/DispatchModal'
import DatasetImportModal from '../components/dataset/DatasetImportModal'
import ProjectManageMenu from '../components/project/ProjectManageMenu'
import {
  resolveProjectCategory,
  resolveProjectStatus,
  useInvalidateProjects,
  useProjectsQuery,
} from '../hooks/queries/useProjects'

// ─── Config ───────────────────────────────────────────────────────────────────

const CAT_CONFIG: Record<string, { label: string; color: string }> = Object.fromEntries(
  Object.entries(CATEGORY_HUB_BY_ID).map(([id, h]) => [id, { label: h.label, color: h.color }]),
)

const CATEGORY_IDS = Object.keys(CAT_CONFIG) as string[]

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  draft:     { label: '草稿',   color: '#5c6070' },
  active:    { label: '进行中', color: '#10b981' },
  paused:    { label: '已暂停', color: '#f59e0b' },
  completed: { label: '已完成', color: '#9ba0ad' },
  archived:  { label: '已归档', color: '#3d3f46' },
  pending:   { label: '待开始', color: '#60a5fa' },
}

// ─── ProjectCard ──────────────────────────────────────────────────────────────

function ProjectCard({
  project, canManage,
  onDispatch, onImport, onNavigate, onChanged,
}: {
  project: ProjectSummary
  canManage: boolean
  onDispatch: (p: ProjectSummary) => void
  onImport: (p: ProjectSummary) => void
  onNavigate: (p: ProjectSummary) => void
  onChanged: () => void
}) {
  const isArchived = resolveProjectStatus(project) === 'archived'
  const category = resolveProjectCategory(project)
  const status = resolveProjectStatus(project)
  const cat    = CAT_CONFIG[category] ?? { label: category || '未分类', color: '#9ba0ad' }
  const st     = STATUS_CONFIG[status] ?? { label: status || '未知', color: '#9ba0ad' }
  const color  = project.cover_color ?? '#00d4ff'
  const total  = project.total_items ?? project.total_tasks ?? 0
  const approved = project.approved_items ?? project.approved_tasks ?? 0
  const progress = total > 0 ? Math.round((approved / total) * 100) : 0
  const pending  = total - (project.completed_tasks ?? 0) - approved

  return (
    <div
      onClick={() => onNavigate(project)}
      className={`relative bg-[#12121a] border border-[#1e1e2e] rounded-2xl overflow-hidden
        hover:border-white/20 active:scale-[0.99] transition-all group cursor-pointer
        ${isArchived ? 'opacity-80' : ''}`}
    >
      {/* Accent bar */}
      <div className="h-0.5 w-full" style={{ background: `linear-gradient(90deg, ${color}, ${color}30)` }} />

      <div className="p-5">
        {/* Header */}
        <div className="flex items-start gap-2 mb-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
              <span className="text-[10px] px-2 py-0.5 rounded-full font-medium whitespace-nowrap"
                style={{ background: `${cat.color}15`, color: cat.color, border: `1px solid ${cat.color}20` }}>
                {cat.label}
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded-full whitespace-nowrap"
                style={{ background: `${st.color}15`, color: st.color }}>
                {st.label}
              </span>
            </div>
            <h3 className="text-sm font-medium text-white/80 group-hover:text-white transition-colors line-clamp-2">
              {project.name}
            </h3>
          </div>
          {canManage && <ProjectManageMenu project={project} onChanged={onChanged} />}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-2 mb-4">
          {[
            { label: '总任务', value: total,    color: '#9ba0ad' },
            { label: '待分派', value: Math.max(0, pending), color: '#f59e0b' },
            { label: '已通过', value: approved, color: '#10b981' },
          ].map(s => (
            <div key={s.label} className="bg-[#0a0a0f] rounded-lg p-2 text-center border border-[#1e1e2e]">
              <div className="text-[9px] text-white/25 mb-1">{s.label}</div>
              <div className="text-sm font-mono font-semibold" style={{ color: s.color }}>
                {s.value.toLocaleString()}
              </div>
            </div>
          ))}
        </div>

        {/* Progress */}
        <div className="space-y-1.5 mb-4">
          <div className="flex justify-between text-[10px] text-white/25">
            <span>完成率</span>
            <span className="font-mono">{progress}%</span>
          </div>
          <div className="h-1 bg-[#1e1e2e] rounded-full overflow-hidden">
            <div className="h-full rounded-full transition-all"
              style={{
                width: `${progress}%`,
                background: progress === 100 ? '#10b981' : `linear-gradient(90deg, ${color}, ${color}60)`,
              }} />
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-all"
          onClick={e => e.stopPropagation()}>
          {canManage && !isArchived && (
            <>
              <button
                onClick={() => onImport(project)}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[11px] border border-[#1e1e2e]
                  text-white/40 hover:text-white/70 hover:border-white/20 transition-all"
              >
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3 h-3">
                  <path d="M7 2v7M4 6l3-3 3 3M2 10v1a1 1 0 001 1h8a1 1 0 001-1v-1" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                导入数据
              </button>
              {project.status === 'active' && pending > 0 && (
                <button
                  onClick={() => onDispatch(project)}
                  className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[11px] border transition-all"
                  style={{ background: `${color}12`, color, borderColor: `${color}30` }}
                >
                  <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3 h-3">
                    <path d="M2 7h10M8 3l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  分派任务
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Bottom meta */}
      <div className="px-5 pb-4 flex items-center justify-between">
        <div className="flex items-center gap-1 text-[10px] text-white/20">
          <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3 h-3">
            <circle cx="6" cy="4" r="2"/><path d="M2 10a4 4 0 018 0" strokeLinecap="round"/>
          </svg>
          {project.member_count} 人
        </div>
        <div className="text-[10px] text-white/20 font-mono">
          ¥{project.price_per_task}/任务
        </div>
      </div>
    </div>
  )
}

// ─── Category filter pills ────────────────────────────────────────────────────

const CAT_FILTERS: { id: string | null; label: string }[] = [
  { id: null, label: '全部' },
  ...CATEGORY_IDS.map(id => ({ id, label: CAT_CONFIG[id].label })),
]

const STATUS_FILTERS: { id: string | null; label: string }[] = [
  { id: null,       label: '全部状态' },
  { id: 'draft',    label: '草稿' },
  { id: 'active',   label: '进行中' },
  { id: 'paused',   label: '暂停' },
  { id: 'completed',label: '完成' },
  { id: 'archived',  label: '已归档' },
]

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyState({ canCreate, onCreate }: { canCreate: boolean; onCreate: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-32 text-center">
      <div className="w-20 h-20 rounded-2xl bg-[#12121a] border border-[#1e1e2e] flex items-center justify-center mx-auto mb-5">
        <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-10 h-10 text-white/15">
          <rect x="4" y="4" width="10" height="10" rx="2"/>
          <rect x="18" y="4" width="10" height="10" rx="2"/>
          <rect x="4" y="18" width="10" height="10" rx="2"/>
          <rect x="18" y="18" width="10" height="10" rx="2"/>
        </svg>
      </div>
      <div className="text-sm text-white/30 mb-1">暂无项目</div>
      <div className="text-xs text-white/15 mb-6">
        {canCreate ? '创建第一个标注项目开始工作' : '等待管理员将你加入项目'}
      </div>
      {canCreate && (
        <button
          type="button"
          onClick={onCreate}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium
            bg-[#00d4ff]/15 text-[#00d4ff] border border-[#00d4ff]/30
            hover:bg-[#00d4ff]/25 active:scale-95 transition-all"
        >
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
            <path d="M8 3v10M3 8h10" strokeLinecap="round"/>
          </svg>
          新建第一个项目
        </button>
      )}
    </div>
  )
}

// ─── Projects page ────────────────────────────────────────────────────────────

export default function Projects() {
  const navigate   = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { user }   = useAuthStore()
  const canManageProjects =
    Boolean(user?.is_admin) ||
    isAdminRole(user?.role) ||
    hasPermission(user?.role, 'projects.manage')

  const categoryFromUrl = searchParams.get('category')
  const initialCat =
    categoryFromUrl && CAT_CONFIG[categoryFromUrl] ? categoryFromUrl : null

  const { data: projects = [], isLoading: loading, refetch } = useProjectsQuery()
  const invalidateProjects = useInvalidateProjects()
  const fetchProjects = () => {
    void invalidateProjects()
    return refetch()
  }

  const [showCreate,     setShowCreate]     = useState(false)
  const [dispatchTarget, setDispatchTarget] = useState<ProjectSummary | null>(null)
  const [importTarget,   setImportTarget]   = useState<ProjectSummary | null>(null)
  const [catFilter,      setCatFilter]      = useState<string | null>(initialCat)
  const [statusFilter,   setStatusFilter]   = useState<string | null>(null)
  const [search,         setSearch]         = useState('')

  // URL ?category=nlp 与筛选标签双向同步（只改本地筛选，不重新请求）
  useEffect(() => {
    const c = searchParams.get('category')
    if (c && CAT_CONFIG[c]) setCatFilter(c)
    else if (!c) setCatFilter(null)
  }, [searchParams])

  function applyCatFilter(id: string | null) {
    setCatFilter(id)
    const next = new URLSearchParams(searchParams)
    if (id) next.set('category', id)
    else next.delete('category')
    setSearchParams(next, { replace: true })
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return projects.filter(p => {
      if (q && !(p.name ?? '').toLowerCase().includes(q)) return false
      if (catFilter && resolveProjectCategory(p) !== catFilter) return false
      if (statusFilter && resolveProjectStatus(p) !== statusFilter) return false
      return true
    })
  }, [projects, search, catFilter, statusFilter])

  /** 各类别在「当前状态 + 搜索」条件下的数量 */
  const categoryCounts = useMemo(() => {
    const q = search.trim().toLowerCase()
    const counts: Record<string, number> = {}
    for (const id of CATEGORY_IDS) counts[id] = 0
    for (const p of projects) {
      if (q && !(p.name ?? '').toLowerCase().includes(q)) continue
      if (statusFilter && resolveProjectStatus(p) !== statusFilter) continue
      const cat = resolveProjectCategory(p)
      if (cat && counts[cat] != null) counts[cat] += 1
    }
    return counts
  }, [projects, search, statusFilter])

  const allVisibleCount = useMemo(() => {
    const q = search.trim().toLowerCase()
    return projects.filter(p => {
      if (q && !(p.name ?? '').toLowerCase().includes(q)) return false
      if (statusFilter && resolveProjectStatus(p) !== statusFilter) return false
      return true
    }).length
  }, [projects, search, statusFilter])

  const summary = useMemo(() => ({
    total: projects.length,
    active: projects.filter(p => resolveProjectStatus(p) === 'active').length,
    tasks: projects.reduce((a, p) => a + (p.total_items ?? p.total_tasks ?? 0), 0),
    shown: filtered.length,
  }), [projects, filtered])

  return (
    <div className="p-8 max-w-screen-xl">

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold">
            {catFilter && CAT_CONFIG[catFilter]
              ? `${CAT_CONFIG[catFilter].label}项目`
              : '项目管理'}
          </h1>
          <div className="flex items-center gap-4 mt-2 text-xs text-white/30">
            <span>{summary.total} 个项目</span>
            <span>{summary.active} 个进行中</span>
            <span>{summary.tasks.toLocaleString()} 个任务</span>
            {(catFilter || statusFilter || search.trim()) && (
              <span className="text-[#00d4ff]/70">
                {catFilter && CAT_CONFIG[catFilter]
                  ? `「${CAT_CONFIG[catFilter].label}」`
                  : ''}
                当前显示 {summary.shown} 个
              </span>
            )}
          </div>
        </div>
        {canManageProjects && (
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all active:scale-95
              bg-[#00d4ff]/15 text-[#00d4ff] border border-[#00d4ff]/30 hover:bg-[#00d4ff]/25 hover:border-[#00d4ff]/50"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
              <path d="M8 3v10M3 8h10" strokeLinecap="round"/>
            </svg>
            新建项目
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="space-y-3 mb-6">
        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="relative">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"
              className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/30 pointer-events-none">
              <circle cx="7" cy="7" r="5"/><path d="M12 12l2 2" strokeLinecap="round"/>
            </svg>
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="搜索项目…"
              className="bg-[#12121a] border border-[#1e1e2e] rounded-xl pl-9 pr-4 py-2 text-sm text-white
                placeholder-white/20 focus:outline-none focus:border-[#00d4ff]/40 transition-all w-52"
            />
          </div>

          {/* Status filter */}
          <div className="flex gap-1 flex-wrap">
            {STATUS_FILTERS.map(f => (
              <button
                key={String(f.id)}
                type="button"
                onClick={() => setStatusFilter(f.id)}
                className={`px-3 py-1.5 rounded-lg text-xs transition-all
                  ${statusFilter === f.id
                    ? 'bg-white/10 text-white/70 border border-white/20'
                    : 'text-white/30 hover:text-white/60'}`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Category pills */}
        <div className="flex gap-1.5 flex-wrap items-center">
          {catFilter && CAT_CONFIG[catFilter] && (
            <span className="text-[11px] text-white/35 mr-1">
              仅展示「{CAT_CONFIG[catFilter].label}」
            </span>
          )}
          {CAT_FILTERS.map(f => {
            const count = f.id == null ? allVisibleCount : (categoryCounts[f.id] ?? 0)
            return (
              <button
                key={String(f.id)}
                type="button"
                onClick={() => applyCatFilter(f.id)}
                className={`px-3 py-1 rounded-full text-xs transition-all
                  ${catFilter === f.id
                    ? 'bg-[#00d4ff]/15 text-[#00d4ff] border border-[#00d4ff]/30'
                    : 'bg-[#12121a] border border-[#1e1e2e] text-white/40 hover:text-white/70 hover:border-white/20'}`}
              >
                {f.label}
                <span className={`ml-1 font-mono ${catFilter === f.id ? 'text-[#00d4ff]/70' : 'text-white/25'}`}>
                  {count}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-56 bg-[#12121a] border border-[#1e1e2e] rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : projects.length === 0 ? (
        <EmptyState canCreate={canManageProjects} onCreate={() => setShowCreate(true)} />
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center border border-dashed border-[#1e1e2e] rounded-2xl">
          <div className="text-sm text-white/30 mb-1">没有符合筛选条件的项目</div>
          <div className="text-xs text-white/15 mb-4 max-w-sm">
            {catFilter && statusFilter
              ? `「${STATUS_CONFIG[statusFilter]?.label ?? statusFilter}」状态下没有「${CAT_CONFIG[catFilter]?.label ?? catFilter}」项目，可先切回「全部状态」再试`
              : catFilter
                ? `当前没有「${CAT_CONFIG[catFilter]?.label ?? catFilter}」项目（可点「全部」查看其它类别）`
                : '试试切换「全部」或清除搜索关键词'}
          </div>
          <button
            type="button"
            onClick={() => {
              applyCatFilter(null)
              setStatusFilter(null)
              setSearch('')
            }}
            className="px-4 py-2 rounded-lg text-xs border border-[#1e1e2e] text-white/40 hover:text-white/70 hover:border-white/20"
          >
            清除筛选
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map(p => (
            <ProjectCard
              key={p.id}
              project={p}
              canManage={canManageProjects}
              onDispatch={setDispatchTarget}
              onImport={setImportTarget}
              onNavigate={(p) => navigate(resolveProjectAnnotatePath(p))}
              onChanged={fetchProjects}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      {showCreate && (
        <CreateProjectModal
          onClose={() => setShowCreate(false)}
          onCreated={(created) => {
            setShowCreate(false)
            void fetchProjects()
            // 创建后自动打开导入数据引导
            setImportTarget({
              id: created.id,
              name: created.name,
              cover_color: created.cover_color,
              category: created.category,
              ann_type: created.ann_type,
              status: created.status ?? 'draft',
              total_items: created.total_items ?? 0,
              approved_items: created.approved_items ?? 0,
              price_per_task: created.price_per_task ?? 0.1,
              member_count: created.member_count ?? 1,
            })
          }}
        />
      )}
      {dispatchTarget && (
        <DispatchModal
          project={dispatchTarget}
          onClose={() => setDispatchTarget(null)}
          onDispatched={fetchProjects}
        />
      )}
      {importTarget && (
        <DatasetImportModal
          projectId={importTarget.id}
          projectName={importTarget.name}
          category={importTarget.category ?? 'image_2d'}
          onClose={() => setImportTarget(null)}
          onImported={() => {
            fetchProjects()
            if (importTarget?.category === 'image_2d' && importTarget.id) {
              navigate(`/projects/${importTarget.id}/tasks`)
            }
          }}
        />
      )}
    </div>
  )
}
