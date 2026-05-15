import { useNavigate } from 'react-router-dom'

// ─── Config ───────────────────────────────────────────────────────────────────

const CAT_CONFIG: Record<string, { label: string; color: string }> = {
  image_2d:      { label: '图像 2D',   color: '#00d4ff' },
  pointcloud_3d: { label: '3D 点云',   color: '#a78bfa' },
  video:         { label: '视频',       color: '#f59e0b' },
  audio:         { label: '语音',       color: '#10b981' },
  nlp:           { label: '语料',       color: '#ec4899' },
  embodied:      { label: '具身机器人', color: '#f97316' },
  ocr:           { label: 'OCR',        color: '#06b6d4' },
  multimodal:    { label: '多模态',     color: '#8b5cf6' },
}

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
  project, isAdmin,
  onDispatch, onImport, onNavigate,
}: {
  project: ProjectSummary
  isAdmin: boolean
  onDispatch: (p: ProjectSummary) => void
  onImport: (p: ProjectSummary) => void
  onNavigate: (p: ProjectSummary) => void
}) {
  const cat    = CAT_CONFIG[project.category ?? ''] ?? { label: project.category, color: '#9ba0ad' }
  const st     = STATUS_CONFIG[project.status ?? ''] ?? { label: project.status, color: '#9ba0ad' }
  const color  = project.cover_color ?? '#00d4ff'
  const total  = project.total_items ?? project.total_tasks ?? 0
  const approved = project.approved_items ?? project.approved_tasks ?? 0
  const progress = total > 0 ? Math.round((approved / total) * 100) : 0
  const pending  = total - (project.completed_tasks ?? 0) - approved

  return (
    <div
      onClick={() => onNavigate(project)}
      className="relative bg-[#12121a] border border-[#1e1e2e] rounded-2xl overflow-hidden
        hover:border-white/20 active:scale-[0.99] transition-all group cursor-pointer"
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
          {isAdmin && (
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

const CAT_FILTERS = [
  { id: null, label: '全部' },
  ...Object.entries(CAT_CONFIG).map(([id, c]) => ({ id, label: c.label })),
]

const STATUS_FILTERS = [
  { id: null,       label: '全部状态' },
  { id: 'draft',    label: '草稿' },
  { id: 'active',   label: '进行中' },
  { id: 'paused',   label: '暂停' },
  { id: 'completed',label: '完成' },
]

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyState({ isAdmin, onCreate }: { isAdmin: boolean; onCreate: () => void }) {
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
        {isAdmin ? '创建第一个标注项目开始工作' : '等待管理员将你加入项目'}
      </div>
      {isAdmin && (
        <button
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
  const { user }   = useAuthStore()
  const isAdmin    = user?.is_admin ?? false

  const [projects,       setProjects]       = useState<ProjectSummary[]>([])
  const [loading,        setLoading]        = useState(true)
  const [showCreate,     setShowCreate]     = useState(false)
  const [dispatchTarget, setDispatchTarget] = useState<ProjectSummary | null>(null)
  const [importTarget,   setImportTarget]   = useState<ProjectSummary | null>(null)
  const [catFilter,      setCatFilter]      = useState<string | null>(null)
  const [statusFilter,   setStatusFilter]   = useState<string | null>(null)
  const [search,         setSearch]         = useState('')

  const fetchProjects = useCallback(async () => {
    setLoading(true)
    try {
      const params: any = { skip: 0, limit: 100 }
      if (catFilter)    params.category = catFilter
      if (statusFilter) params.status   = statusFilter
      const { data } = await api.get('/projects', { params })
      setProjects(data)
    } catch {
      // keep existing
    } finally {
      setLoading(false)
    }
  }, [catFilter, statusFilter])

  useEffect(() => { fetchProjects() }, [fetchProjects])

  const filtered = projects.filter(p =>
    (!search || p.name.toLowerCase().includes(search.toLowerCase()))
  )

  const summary = {
    total:  projects.length,
    active: projects.filter(p => p.status === 'active').length,
    tasks:  projects.reduce((a, p) => a + (p.total_items ?? p.total_tasks ?? 0), 0),
  }

  return (
    <div className="p-8 max-w-screen-xl">

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-xl font-semibold">项目管理</h1>
          <div className="flex items-center gap-4 mt-2 text-xs text-white/30">
            <span>{summary.total} 个项目</span>
            <span>{summary.active} 个进行中</span>
            <span>{summary.tasks.toLocaleString()} 个任务</span>
          </div>
        </div>
        {isAdmin && (
          <button
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
          <div className="flex gap-1">
            {STATUS_FILTERS.map(f => (
              <button
                key={String(f.id)}
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
        <div className="flex gap-1.5 flex-wrap">
          {CAT_FILTERS.map(f => (
            <button
              key={String(f.id)}
              onClick={() => setCatFilter(f.id)}
              className={`px-3 py-1 rounded-full text-xs transition-all
                ${catFilter === f.id
                  ? 'bg-[#00d4ff]/15 text-[#00d4ff] border border-[#00d4ff]/30'
                  : 'bg-[#12121a] border border-[#1e1e2e] text-white/40 hover:text-white/70 hover:border-white/20'}`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-56 bg-[#12121a] border border-[#1e1e2e] rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState isAdmin={isAdmin} onCreate={() => setShowCreate(true)} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map(p => (
            <ProjectCard
              key={p.id}
              project={p}
              isAdmin={isAdmin}
              onDispatch={setDispatchTarget}
              onImport={setImportTarget}
              onNavigate={proj => navigate(`/projects/${proj.id}`)}
            />
          ))}
        </div>
      )}

      {/* Modals */}
      {showCreate && (
        <CreateProjectModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { fetchProjects(); setShowCreate(false) }}
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
          onImported={fetchProjects}
        />
      )}
    </div>
  )
}
