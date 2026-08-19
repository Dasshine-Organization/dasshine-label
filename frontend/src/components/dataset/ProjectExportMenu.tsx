import { useCallback, useEffect, useRef, useState } from 'react'
import { message } from 'antd'
import { exportApi } from '../../services/api'

export type ExportFormatInfo = {
  id: string
  label: string
  ext: string
  description: string
  primary?: boolean
}

type Props = {
  projectId: number | string | null | undefined
  projectName?: string
  status?: string
  className?: string
  /** compact: smaller button for annotation headers */
  compact?: boolean
}

function filenameFromDisposition(header: string | undefined, fallback: string): string {
  if (!header) return fallback
  const m = /filename="?([^";]+)"?/i.exec(header)
  return m?.[1] || fallback
}

const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/api\/v1\/?$/, '')
  || ''

export default function ProjectExportMenu({
  projectId,
  projectName = 'project',
  status = 'approved',
  className = '',
  compact = false,
}: Props) {
  const pid = Number(projectId)
  const [open, setOpen] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [formats, setFormats] = useState<ExportFormatInfo[]>([])
  const [defaultFormat, setDefaultFormat] = useState('coco')
  const [snapshots, setSnapshots] = useState<
    Array<{ id: number; version: number; format: string; download_url?: string; task_count: number }>
  >([])
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!pid || Number.isNaN(pid)) return
    let cancelled = false
    ;(async () => {
      try {
        const { data } = await exportApi.getStats(pid)
        if (cancelled) return
        const list = (data?.formats as ExportFormatInfo[]) || []
        if (list.length) {
          setFormats(list)
        } else if (Array.isArray(data?.export_formats)) {
          setFormats(
            (data.export_formats as string[]).map(id => ({
              id,
              label: id,
              ext: id,
              description: id,
              primary: id !== 'raw_json' && id !== 'json',
            })),
          )
        }
        if (data?.default_format) setDefaultFormat(String(data.default_format))
      } catch {
        /* keep empty — menu still shows fallback */
      }
      try {
        const { data: snaps } = await exportApi.listSnapshots(pid, 8)
        if (!cancelled) setSnapshots(snaps.items ?? [])
      } catch {
        if (!cancelled) setSnapshots([])
      }
    })()
    return () => {
      cancelled = true
    }
  }, [pid, open])

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open])

  const primaryFormats = formats.filter(f => f.primary !== false && f.id !== 'raw_json')
  const rawFormats = formats.filter(f => f.primary === false || f.id === 'raw_json')
  const menuFormats =
    primaryFormats.length > 0
      ? [...primaryFormats, ...rawFormats]
      : [
          { id: defaultFormat, label: defaultFormat.toUpperCase(), ext: '', description: '默认格式', primary: true },
        ]

  const doExport = useCallback(
    async (formatId: string, label: string) => {
      if (!pid || Number.isNaN(pid)) {
        message.error('缺少项目 ID')
        return
      }
      setExporting(true)
      setOpen(false)
      try {
        const res = await exportApi.exportProject(pid, formatId, status)
        const blob =
          res.data instanceof Blob
            ? res.data
            : new Blob([res.data], { type: 'application/octet-stream' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        const fallback = `${projectName}_${formatId}`
        a.download = filenameFromDisposition(
          res.headers?.['content-disposition'] as string | undefined,
          fallback,
        )
        a.click()
        URL.revokeObjectURL(url)
        message.success(`已导出 ${label}`)
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } | Blob } }
        let detail = '导出失败（需有已通过任务）'
        const body = err.response?.data
        if (body instanceof Blob) {
          try {
            const text = await body.text()
            const parsed = JSON.parse(text) as { detail?: string }
            if (parsed.detail) detail = parsed.detail
          } catch {
            /* ignore */
          }
        } else if (typeof body === 'object' && body && 'detail' in body) {
          detail = String((body as { detail?: string }).detail)
        }
        message.error(detail)
      } finally {
        setExporting(false)
      }
    },
    [pid, projectName, status],
  )

  const doBackgroundExport = useCallback(
    async (formatId: string, label: string) => {
      if (!pid || Number.isNaN(pid)) {
        message.error('缺少项目 ID')
        return
      }
      setExporting(true)
      setOpen(false)
      try {
        const { data } = await exportApi.startJob(pid, formatId, status)
        const jobId = data.job_id
        message.loading({ content: `后台导出 ${label}…`, key: 'export-job', duration: 0 })
        for (let i = 0; i < 90; i++) {
          await new Promise(r => setTimeout(r, 2000))
          const { data: job } = await exportApi.getJob(jobId)
          if (job.status === 'completed' && job.download_url) {
            message.success({ content: `后台导出完成：${label}`, key: 'export-job' })
            const href = job.download_url.startsWith('http')
              ? job.download_url
              : `${API_ORIGIN}${job.download_url}`
            window.open(href, '_blank')
            return
          }
          if (job.status === 'failed') {
            throw new Error(job.error || '后台导出失败')
          }
        }
        message.error({ content: '后台导出超时，请稍后重试或用同步导出', key: 'export-job' })
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string }; status?: number }; message?: string }
        const detail =
          err.response?.data?.detail
          || err.message
          || '后台导出不可用，请用同步导出'
        message.error({ content: String(detail), key: 'export-job' })
      } finally {
        setExporting(false)
      }
    },
    [pid, status],
  )

  if (!pid || Number.isNaN(pid)) return null

  const btnClass = compact
    ? 'text-xs px-3 py-1.5 rounded-lg border border-[#10b981]/30 text-[#10b981] hover:bg-[#10b981]/10 transition-all disabled:opacity-40'
    : 'px-3 py-1.5 rounded-lg text-xs border border-[#10b981]/30 text-[#10b981] hover:bg-[#10b981]/10 transition-all disabled:opacity-40'

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        disabled={exporting}
        onClick={() => setOpen(v => !v)}
        className={btnClass}
      >
        {exporting ? '导出中…' : '导出数据 ▾'}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 min-w-[240px] rounded-xl border border-[#1e1e2e] bg-[#12121a] shadow-xl py-1">
          {menuFormats.map(f => (
            <div key={f.id} className="border-b border-[#1e1e2e]/60 last:border-0">
              <button
                type="button"
                onClick={() => void doExport(f.id, f.label)}
                className="w-full text-left px-3 py-2 hover:bg-white/5 transition-colors"
              >
                <div className="text-xs text-white/80">{f.label}</div>
                <div className="text-[10px] text-white/30 mt-0.5 line-clamp-2">{f.description}</div>
              </button>
              <button
                type="button"
                onClick={() => void doBackgroundExport(f.id, f.label)}
                className="w-full text-left px-3 pb-2 text-[10px] text-[#00d4ff]/70 hover:text-[#00d4ff]"
              >
                后台导出（大包）
              </button>
            </div>
          ))}
          {snapshots.length > 0 && (
            <div className="border-t border-[#1e1e2e] px-3 py-2 space-y-1">
              <div className="text-[10px] text-white/35 uppercase tracking-wider">历史快照</div>
              {snapshots.map(s => (
                <div key={s.id} className="flex items-center justify-between gap-2 text-[10px]">
                  <span className="text-white/50">
                    v{s.version} · {s.format} · {s.task_count} 条
                  </span>
                  {s.download_url && (
                    <a
                      href={s.download_url.startsWith('http') ? s.download_url : `${API_ORIGIN}${s.download_url}`}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[#00d4ff] hover:underline shrink-0"
                    >
                      下载
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
