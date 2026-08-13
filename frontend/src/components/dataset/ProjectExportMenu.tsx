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
    })()
    return () => {
      cancelled = true
    }
  }, [pid])

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
        <div className="absolute right-0 top-full mt-1 z-50 min-w-[220px] rounded-xl border border-[#1e1e2e] bg-[#12121a] shadow-xl py-1">
          {menuFormats.map(f => (
            <button
              key={f.id}
              type="button"
              onClick={() => void doExport(f.id, f.label)}
              className="w-full text-left px-3 py-2 hover:bg-white/5 transition-colors"
            >
              <div className="text-xs text-white/80">{f.label}</div>
              <div className="text-[10px] text-white/30 mt-0.5 line-clamp-2">{f.description}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
