import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { message } from 'antd'
import api from '../../services/api'
import useAuthStore from '../../store/authStore'

// ─── Types ────────────────────────────────────────────────────────────────────

type ImportMethod = 'url' | 'text' | 'local_files' | 'zip' | 'coco' | 'yolo' | 'csv' | 'jsonl' | 'embodied' | 'storage'

const IMAGE_ACCEPT = '.jpg,.jpeg,.png,.webp,.bmp,.tiff,.gif'
const DEFAULT_FILE_SERVER =
  import.meta.env.VITE_FILE_SERVER_URL || 'http://localhost:8000'

interface ImportResult {
  batch_id: string
  total: number
  success: number
  skipped: number
  errors: string[]
}

interface Props {
  projectId: number
  projectName: string
  category: string
  onClose: () => void
  onImported: () => void
}

async function pollImportJob(jobId: string, maxAttempts = 120): Promise<Record<string, unknown>> {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 2000))
    const { data } = await api.get(`/projects/import-jobs/${jobId}`)
    if (data.ready && data.successful) {
      return (data.result as Record<string, unknown>) || data
    }
    if (data.ready && data.successful === false) {
      throw new Error((data.error as string) || '后台导入失败')
    }
  }
  throw new Error('后台导入超时，请稍后在任务列表刷新查看')
}

// ─── Method config ────────────────────────────────────────────────────────────

const METHODS: { id: ImportMethod; label: string; desc: string; icon: JSX.Element; color: string; forCategories?: string[] }[] = [
  {
    id: 'url',
    label: 'URL 列表',
    desc: '粘贴图像 / 音频 / 视频 / 点云链接，每行一个',
    color: '#00d4ff',
    icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4"><path d="M6.5 9.5a3 3 0 004.24 0l2-2a3 3 0 00-4.24-4.24l-1 1" strokeLinecap="round"/><path d="M9.5 6.5a3 3 0 00-4.24 0l-2 2a3 3 0 004.24 4.24l1-1" strokeLinecap="round"/></svg>,
  },
  {
    id: 'text',
    label: '文本粘贴',
    desc: '直接粘贴文本内容，每行一条',
    color: '#ec4899',
    forCategories: ['nlp', 'audio'],
    icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4"><path d="M2 4h12M2 7h8M2 10h10M2 13h6" strokeLinecap="round"/></svg>,
  },
  {
    id: 'local_files',
    label: '本地图片',
    desc: '拖入文件夹或多张图片（jpg/png/webp 等）',
    color: '#22d3ee',
    forCategories: ['image_2d', 'ocr'],
    icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4"><rect x="2" y="3" width="12" height="10" rx="1"/><circle cx="5.5" cy="7" r="1.2"/><path d="M2 11l3.5-3.5 2.5 2.5L11 7l3 4" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  },
  {
    id: 'zip',
    label: 'ZIP 文件夹',
    desc: '图像 / 音频 / 视频 / 点云（pcd/bin/ply）压缩包',
    color: '#f59e0b',
    icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4"><path d="M4 2h5l3 3v9a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M9 2v3h3M7 8v5M5.5 9.5L7 8l1.5 1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  },
  {
    id: 'coco',
    label: 'COCO JSON',
    desc: '导入 MS COCO 格式标注数据集',
    color: '#10b981',
    forCategories: ['image_2d', 'ocr'],
    icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4"><rect x="2" y="2" width="5" height="5" rx="1"/><rect x="9" y="2" width="5" height="5" rx="1"/><rect x="2" y="9" width="5" height="5" rx="1"/><rect x="9" y="9" width="5" height="5" rx="1"/></svg>,
  },
  {
    id: 'yolo',
    label: 'YOLO 格式',
    desc: '导入 Darknet YOLO 格式（images/+labels/）',
    color: '#a78bfa',
    forCategories: ['image_2d'],
    icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4"><rect x="3" y="3" width="10" height="10" rx="1" strokeDasharray="3 2"/><rect x="5" y="5" width="6" height="6" rx="0.5"/></svg>,
  },
  {
    id: 'csv',
    label: 'CSV 文件',
    desc: '表格数据，支持文本列和标签列',
    color: '#06b6d4',
    forCategories: ['nlp', 'multimodal'],
    icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4"><rect x="2" y="2" width="12" height="12" rx="1"/><path d="M2 6h12M2 10h12M6 2v12" strokeLinecap="round"/></svg>,
  },
  {
    id: 'jsonl',
    label: 'JSONL 文件',
    desc: '每行一个 JSON 对象，适合对话/QA 数据',
    color: '#f97316',
    forCategories: ['nlp', 'multimodal'],
    icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4"><path d="M4 4C4 4 2 5 2 8s2 4 2 4M12 4c0 0 2 1 2 4s-2 4-2 4M6 9l1.5-2L9 9l1.5-2" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  },
  {
    id: 'embodied',
    label: '具身 Episode',
    desc: 'Episode JSON / JSONL（多机位 streams + 可选 proprioception）',
    color: '#f97316',
    forCategories: ['embodied'],
    icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4"><circle cx="8" cy="8" r="5"/><path d="M8 5v3l2 1" strokeLinecap="round"/></svg>,
  },
  {
    id: 'storage',
    label: '存储目录',
    desc: '浏览 local / S3 前缀并批量导入',
    color: '#94a3b8',
    icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4"><path d="M2 5.5A2.5 2.5 0 014.5 3h7A2.5 2.5 0 0114 5.5v5A2.5 2.5 0 0111.5 13h-7A2.5 2.5 0 012 10.5v-5z"/><path d="M5 8h6M8 5v6" strokeLinecap="round"/></svg>,
  },
]

const IMAGE_EXT_RE = /\.(jpe?g|png|webp|bmp|tiff?|gif)$/i

function isImageFile(file: File) {
  return IMAGE_EXT_RE.test(file.name)
}

async function collectImageFilesFromDrop(dt: DataTransfer): Promise<File[]> {
  const out: File[] = []
  const items = dt.items
  if (!items?.length) {
    return Array.from(dt.files).filter(isImageFile)
  }

  const readEntry = (entry: FileSystemEntry): Promise<void> =>
    new Promise((resolve, reject) => {
      if (entry.isFile) {
        ;(entry as FileSystemFileEntry).file(
          f => {
            if (isImageFile(f)) out.push(f)
            resolve()
          },
          reject,
        )
      } else if (entry.isDirectory) {
        const reader = (entry as FileSystemDirectoryEntry).createReader()
        const readBatch = () => {
          reader.readEntries(async entries => {
            if (!entries.length) {
              resolve()
              return
            }
            for (const e of entries) await readEntry(e)
            readBatch()
          }, reject)
        }
        readBatch()
      } else {
        resolve()
      }
    })

  for (let i = 0; i < items.length; i++) {
    const entry = items[i].webkitGetAsEntry?.()
    if (entry) await readEntry(entry)
  }
  if (!out.length) return Array.from(dt.files).filter(isImageFile)
  return out
}

// ─── Multi-image drop zone ────────────────────────────────────────────────────

function MultiImageDropZone({
  files,
  onFiles,
}: {
  files: File[]
  onFiles: (files: File[]) => void
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const folderInputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  useEffect(() => {
    const el = folderInputRef.current
    if (el) {
      el.setAttribute('webkitdirectory', '')
      el.setAttribute('directory', '')
    }
  }, [])

  const mergeFiles = (incoming: File[]) => {
    const map = new Map<string, File>()
    for (const f of [...files, ...incoming]) {
      const key = `${f.webkitRelativePath || ''}/${f.name}/${f.size}`
      map.set(key, f)
    }
    onFiles([...map.values()])
  }

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={async e => {
        e.preventDefault()
        setDragging(false)
        const picked = await collectImageFilesFromDrop(e.dataTransfer)
        if (picked.length) mergeFiles(picked)
      }}
      className={`
        border-2 border-dashed rounded-xl p-8 text-center transition-all
        ${dragging ? 'border-[#00d4ff]/60 bg-[#00d4ff]/5' : 'border-[#1e1e2e] hover:border-white/20 hover:bg-white/[0.02]'}
      `}
    >
      <div className="flex gap-2 mb-3">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="flex-1 py-2 rounded-lg text-xs border border-[#1e1e2e] text-white/50 hover:border-white/20"
        >
          选择图片
        </button>
        <button
          type="button"
          onClick={() => folderInputRef.current?.click()}
          className="flex-1 py-2 rounded-lg text-xs border border-[#1e1e2e] text-white/50 hover:border-white/20"
        >
          选择文件夹
        </button>
      </div>
      <input
        ref={fileInputRef}
        type="file"
        accept={IMAGE_ACCEPT}
        multiple
        className="hidden"
        onChange={e => {
          const list = Array.from(e.target.files ?? []).filter(isImageFile)
          if (list.length) mergeFiles(list)
          e.target.value = ''
        }}
      />
      <input
        ref={folderInputRef}
        type="file"
        accept={IMAGE_ACCEPT}
        multiple
        className="hidden"
        onChange={e => {
          const list = Array.from(e.target.files ?? []).filter(isImageFile)
          if (list.length) mergeFiles(list)
          e.target.value = ''
        }}
      />
      {files.length > 0 ? (
        <div className="space-y-2">
          <div className="text-sm text-[#00d4ff]">已选择 {files.length} 张图片</div>
          <div className="text-[10px] text-white/30 max-h-16 overflow-y-auto">
            {files.slice(0, 5).map(f => <div key={f.name}>{f.name}</div>)}
            {files.length > 5 && <div>… 等 {files.length} 个文件</div>}
          </div>
          <div className="text-xs text-white/20">点击继续添加，或拖入更多</div>
        </div>
      ) : (
        <div className="space-y-2">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
            className="w-8 h-8 mx-auto text-white/20">
            <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <div className="text-sm text-white/40">拖入图片或整个文件夹</div>
          <div className="text-xs text-white/20">支持 jpg · png · webp · bmp · tiff · gif</div>
        </div>
      )}
    </div>
  )
}

// ─── File drop zone ───────────────────────────────────────────────────────────

function DropZone({
  accept, label, onFile,
}: {
  accept: string
  label: string
  onFile: (file: File) => void
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [fileName, setFileName] = useState('')

  const handleFile = (file: File) => {
    setFileName(file.name)
    onFile(file)
  }

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={e => {
        e.preventDefault()
        setDragging(false)
        const f = e.dataTransfer.files[0]
        if (f) handleFile(f)
      }}
      className={`
        border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
        ${dragging ? 'border-[#00d4ff]/60 bg-[#00d4ff]/5' : 'border-[#1e1e2e] hover:border-white/20 hover:bg-white/[0.02]'}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
      />
      {fileName ? (
        <div className="space-y-1">
          <div className="text-sm text-[#00d4ff]">✓ {fileName}</div>
          <div className="text-xs text-white/30">点击重新选择</div>
        </div>
      ) : (
        <div className="space-y-2">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
            className="w-8 h-8 mx-auto text-white/20">
            <path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <div className="text-sm text-white/40">{label}</div>
          <div className="text-xs text-white/20">拖拽文件到此处，或点击选择</div>
        </div>
      )}
    </div>
  )
}

// ─── Result banner ────────────────────────────────────────────────────────────

function ResultBanner({ result }: { result: ImportResult }) {
  const ok = result.success > 0
  return (
    <div className={`rounded-xl p-4 border space-y-2 ${ok ? 'bg-[#10b981]/10 border-[#10b981]/25' : 'bg-[#ef4444]/10 border-[#ef4444]/25'}`}>
      <div className="flex items-center justify-between">
        <span className={`text-sm font-medium ${ok ? 'text-[#10b981]' : 'text-[#ef4444]'}`}>
          {ok ? `✓ 成功导入 ${result.success} 条数据` : '导入失败'}
        </span>
        <span className="text-xs text-white/30 font-mono">{result.batch_id.slice(0, 8)}…</span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="text-center"><div className="text-white/30">总计</div><div className="text-white/70 font-mono">{result.total}</div></div>
        <div className="text-center"><div className="text-white/30">成功</div><div className="text-[#10b981] font-mono">{result.success}</div></div>
        <div className="text-center"><div className="text-white/30">跳过</div><div className="text-white/40 font-mono">{result.skipped}</div></div>
      </div>
      {result.errors.length > 0 && (
        <div className="text-[10px] text-[#ef4444]/70 bg-[#ef4444]/5 rounded-lg p-2 space-y-0.5 max-h-20 overflow-y-auto">
          {result.errors.map((e, i) => <div key={i}>• {e}</div>)}
        </div>
      )}
    </div>
  )
}

// ─── DatasetImportModal ───────────────────────────────────────────────────────

export default function DatasetImportModal({ projectId, projectName, category, onClose, onImported }: Props) {
  const [method, setMethod] = useState<ImportMethod>(
    category === 'image_2d' || category === 'ocr' ? 'local_files' : 'url',
  )
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ImportResult | null>(null)

  // Form states
  const [urlText, setUrlText] = useState('')
  const [bodyText, setBodyText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [localFiles, setLocalFiles] = useState<File[]>([])
  const [fileServerUrl, setFileServerUrl] = useState(DEFAULT_FILE_SERVER)
  const [storageInfo, setStorageInfo] = useState<{
    backend?: string
    configured?: boolean
    bucket?: string
    endpoint?: string
    public_base_url?: string
    hint?: string
  } | null>(null)
  const [classNames, setClassNames] = useState('')
  const [textColumn, setTextColumn] = useState('text')
  const [labelColumn, setLabelColumn] = useState('')
  const [importAnns, setImportAnns] = useState(true)
  const [goldenRatio, setGoldenRatio] = useState(5)
  const [priority, setPriority] = useState(5)
  const [storagePrefix, setStoragePrefix] = useState('projects/')
  const [browseItems, setBrowseItems] = useState<Array<{ key: string; size?: number; url?: string; is_dir?: boolean }>>([])
  const [browseBusy, setBrowseBusy] = useState(false)
  const [mounts, setMounts] = useState<Array<{ id: number; name: string; root_prefix: string }>>([])
  const [selectedMountId, setSelectedMountId] = useState<number | null>(null)
  const [mountPath, setMountPath] = useState('')
  const activeOrgId = useAuthStore(s => s.user?.active_org_id ?? null)

  // Filter methods by category
  const availableMethods = METHODS.filter(m =>
    !m.forCategories || m.forCategories.includes(category)
  )

  const activeMethod = METHODS.find(m => m.id === method)!

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const { data } = await api.get('/storage/config')
        if (cancelled) return
        setStorageInfo(data)
        if (data?.public_base_url) {
          setFileServerUrl(String(data.public_base_url))
        }
      } catch {
        /* 保持默认本机前缀 */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (method !== 'storage' || !activeOrgId) {
      setMounts([])
      return
    }
    let cancelled = false
    api
      .get(`/orgs/${activeOrgId}/storage-mounts`)
      .then(res => {
        if (cancelled) return
        setMounts((res.data?.items as Array<{ id: number; name: string; root_prefix: string }>) || [])
      })
      .catch(() => {
        if (!cancelled) setMounts([])
      })
    return () => {
      cancelled = true
    }
  }, [method, activeOrgId])

  async function handleImport() {
    setLoading(true)
    setResult(null)
    try {
      let res: any

      if (method === 'url') {
        const urls = urlText.split('\n').map(u => u.trim()).filter(Boolean)
        if (!urls.length) throw new Error('请输入至少一个 URL')
        const { data } = await api.post(`/projects/${projectId}/import/urls`, {
          urls, priority, golden_ratio: goldenRatio / 100,
        })
        res = data

      } else if (method === 'text') {
        const texts = bodyText.split('\n').map(t => t.trim()).filter(Boolean)
        if (!texts.length) throw new Error('请输入至少一条文本')
        const { data } = await api.post(`/projects/${projectId}/import/texts`, {
          texts, priority, golden_ratio: goldenRatio / 100,
        })
        res = data

      } else if (method === 'local_files') {
        if (!localFiles.length) throw new Error('请至少选择一张图片')
        const form = new FormData()
        for (const f of localFiles) {
          const name = f.webkitRelativePath || f.name
          form.append('files', f, name)
        }
        form.append('file_server_base_url', fileServerUrl.trim())
        form.append('priority', String(priority))
        form.append('golden_ratio', String(goldenRatio / 100))
        const { data } = await api.post(`/projects/${projectId}/import/files`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 300_000,
        })
        res = data

      } else if (method === 'zip') {
        if (!file) throw new Error('请选择 ZIP 文件')
        const zipName = file.name.toLowerCase()
        if (!zipName.endsWith('.zip') && file.type !== 'application/zip' && file.type !== 'application/x-zip-compressed') {
          throw new Error('请上传 .zip 格式的压缩包')
        }
        const form = new FormData()
        form.append('file', file, file.name.endsWith('.zip') ? file.name : `${file.name}.zip`)
        form.append('file_server_base_url', fileServerUrl.trim())
        form.append('priority', String(priority))
        form.append('golden_ratio', String(goldenRatio / 100))
        // 大于 8MB 走后台导入，避免长请求超时
        const useJob = file.size > 8 * 1024 * 1024
        if (useJob) {
          const { data: job } = await api.post(`/projects/${projectId}/import/zip/jobs`, form, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 120_000,
          })
          const jobId = job.job_id as string
          message.info('已提交后台导入，正在等待完成…')
          res = await pollImportJob(jobId)
        } else {
          const { data } = await api.post(`/projects/${projectId}/import/zip`, form, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 300_000,
          })
          res = data
        }

      } else if (method === 'coco') {
        if (!file) throw new Error('请选择 COCO JSON 文件')
        const form = new FormData()
        form.append('file', file)
        const { data } = await api.post(`/projects/${projectId}/import/coco`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
          params: { import_annotations: importAnns },
        })
        res = data

      } else if (method === 'yolo') {
        if (!file) throw new Error('请选择 YOLO ZIP 文件')
        const form = new FormData()
        form.append('file', file)
        form.append('class_names', classNames)
        form.append('priority', String(priority))
        form.append('file_server_base_url', fileServerUrl.trim())
        if (file.size > 8 * 1024 * 1024) {
          const { data: job } = await api.post(`/projects/${projectId}/import/yolo/jobs`, form, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 120_000,
          })
          message.info('已提交后台 YOLO 导入，正在等待完成…')
          res = await pollImportJob(job.job_id as string)
        } else {
          const { data } = await api.post(`/projects/${projectId}/import/yolo`, form, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
          res = data
        }

      } else if (method === 'csv') {
        if (!file) throw new Error('请选择 CSV 文件')
        const form = new FormData()
        form.append('file', file)
        form.append('text_column', textColumn)
        form.append('label_column', labelColumn)
        form.append('priority', String(priority))
        form.append('golden_ratio', String(goldenRatio / 100))
        const { data } = await api.post(`/projects/${projectId}/import/csv`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        res = data

      } else if (method === 'jsonl') {
        if (!file && !bodyText) throw new Error('请选择文件或粘贴内容')
        if (file) {
          const form = new FormData()
          form.append('file', file)
          const { data } = await api.post(`/projects/${projectId}/import/jsonl`, form, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
          res = data
        } else {
          const { data } = await api.post(`/projects/${projectId}/import/jsonl`, {
            content: bodyText, priority, golden_ratio: goldenRatio / 100,
          })
          res = data
        }
      } else if (method === 'embodied') {
        if (!file) throw new Error('请选择 Episode JSON / JSONL 文件')
        const form = new FormData()
        form.append('file', file)
        form.append('priority', String(priority))
        const { data } = await api.post(`/projects/${projectId}/import/embodied`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        res = data
      } else if (method === 'storage') {
        if (selectedMountId) {
          const { data } = await api.post(`/projects/${projectId}/import/from-storage`, {
            mount_id: selectedMountId,
            path: mountPath.trim(),
            limit: 500,
            priority,
            golden_ratio: goldenRatio / 100,
          })
          res = data
        } else {
          const prefix = storagePrefix.trim()
          if (!prefix) throw new Error('请填写存储前缀或选择挂载')
          const { data } = await api.post(`/projects/${projectId}/import/from-storage`, {
            prefix,
            limit: 500,
            priority,
            golden_ratio: goldenRatio / 100,
          })
          res = data
        }
      }

      setResult(res)
      if (res.success > 0) {
        onImported()
        message.success({ content: `成功导入 ${res.success} 条数据`, duration: 3 })
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail ?? e?.message ?? '导入失败'
      message.error({ content: msg, duration: 4 })
    } finally {
      setLoading(false)
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
      onClick={e => e.target === e.currentTarget && onClose()}>

      <div className="w-full max-w-2xl bg-[#12121a] border border-[#1e1e2e] rounded-2xl overflow-hidden"
        style={{ boxShadow: '0 0 60px rgba(0,212,255,0.08)' }}>

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#1e1e2e]">
          <div>
            <div className="text-sm font-medium text-white/80">导入数据集</div>
            <div className="text-[11px] text-white/30 mt-0.5 truncate max-w-80">{projectName}</div>
          </div>
          <button onClick={onClose} className="text-white/30 hover:text-white/70 transition-colors">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
              <path d="M3 3l10 10M13 3L3 13" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        <div className="flex" style={{ maxHeight: '75vh' }}>
          {/* Left: method selector */}
          <div className="w-44 border-r border-[#1e1e2e] py-3 flex-shrink-0 overflow-y-auto">
            {availableMethods.map(m => (
              <button
                key={m.id}
                onClick={() => { setMethod(m.id); setResult(null) }}
                className={`w-full flex items-center gap-2.5 px-3 py-2.5 text-left transition-all
                  ${method === m.id ? 'bg-white/5' : 'hover:bg-white/[0.03]'}`}
              >
                <span className={`flex-shrink-0 ${method === m.id ? '' : 'opacity-40'}`}
                  style={{ color: method === m.id ? m.color : undefined }}>
                  {m.icon}
                </span>
                <div>
                  <div className={`text-xs font-medium ${method === m.id ? 'text-white/80' : 'text-white/30'}`}>
                    {m.label}
                  </div>
                </div>
                {method === m.id && (
                  <div className="ml-auto w-0.5 h-4 rounded-full flex-shrink-0"
                    style={{ background: m.color }} />
                )}
              </button>
            ))}
          </div>

          {/* Right: form */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {/* Method desc */}
            <div className="flex items-center gap-2.5 p-3 rounded-xl border border-[#1e1e2e] bg-[#0a0a0f]">
              <span style={{ color: activeMethod.color }}>{activeMethod.icon}</span>
              <div>
                <div className="text-xs font-medium text-white/70">{activeMethod.label}</div>
                <div className="text-[10px] text-white/30">{activeMethod.desc}</div>
              </div>
            </div>

            {/* URL input */}
            {method === 'url' && (
              <div>
                <label className="block text-xs text-white/40 mb-1.5">URL 列表（每行一个）</label>
                <textarea
                  value={urlText}
                  onChange={e => setUrlText(e.target.value)}
                  placeholder={"https://example.com/image1.jpg\nhttps://example.com/image2.png\n…"}
                  rows={8}
                  className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-xs text-white font-mono
                    placeholder-white/15 focus:outline-none focus:border-[#00d4ff]/40 resize-none transition-all"
                />
                <div className="text-[10px] text-white/20 mt-1">
                  已输入 {urlText.split('\n').filter(u => u.trim()).length} 个 URL
                </div>
              </div>
            )}

            {/* Text input */}
            {method === 'text' && (
              <div>
                <label className="block text-xs text-white/40 mb-1.5">文本内容（每行一条）</label>
                <textarea
                  value={bodyText}
                  onChange={e => setBodyText(e.target.value)}
                  placeholder={"今天天气很好，适合出门。\n这部电影非常精彩，值得推荐。\n…"}
                  rows={8}
                  className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-xs text-white
                    placeholder-white/15 focus:outline-none focus:border-[#00d4ff]/40 resize-none transition-all"
                />
                <div className="text-[10px] text-white/20 mt-1">
                  已输入 {bodyText.split('\n').filter(t => t.trim()).length} 条文本
                </div>
              </div>
            )}

            {(method === 'local_files' || method === 'zip' || method === 'yolo') && (
              <div className="space-y-2">
                {storageInfo && (
                  <div className="rounded-lg border border-[#1e1e2e] bg-[#0a0a0f] px-3 py-2 text-[11px] text-white/45 space-y-0.5">
                    <div>
                      存储后端：
                      <span className="text-white/70 font-mono ml-1">
                        {storageInfo.backend === 's3' ? 'S3 兼容' : '本地'}
                      </span>
                      {storageInfo.backend === 's3' && storageInfo.bucket && (
                        <span className="text-white/30 ml-2">bucket={storageInfo.bucket}</span>
                      )}
                    </div>
                    {storageInfo.endpoint && (
                      <div className="font-mono text-white/30 truncate">endpoint={storageInfo.endpoint}</div>
                    )}
                    {storageInfo.hint && <div className="text-white/25">{storageInfo.hint}</div>}
                    {storageInfo.backend === 's3' && storageInfo.configured === false && (
                      <div className="text-[#f59e0b]">未配置完整 S3 凭证，导入可能失败</div>
                    )}
                  </div>
                )}
                <div>
                  <label className="block text-xs text-white/40 mb-1.5">
                    {storageInfo?.backend === 's3' ? '公开访问前缀（可选覆盖）' : '文件服务地址'}
                  </label>
                  <input
                    value={fileServerUrl}
                    onChange={e => setFileServerUrl(e.target.value)}
                    placeholder={
                      storageInfo?.backend === 's3'
                        ? 'https://cdn.example.com/bucket'
                        : 'http://localhost:8000'
                    }
                    className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white font-mono
                      placeholder-white/20 focus:outline-none focus:border-[#00d4ff]/40 transition-all"
                  />
                  <div className="text-[10px] text-white/20 mt-1">
                    {storageInfo?.backend === 's3'
                      ? '对象写入 S3/MinIO；此地址用于拼 data_url，默认同环境 S3_PUBLIC_BASE_URL'
                      : '导入后图片 URL 前缀，默认本机后端；生产环境填写实际文件服务域名'}
                  </div>
                </div>
              </div>
            )}

            {method === 'local_files' && (
              <MultiImageDropZone files={localFiles} onFiles={setLocalFiles} />
            )}

            {/* ZIP */}
            {method === 'zip' && (
              <DropZone
                accept=".zip"
                label="拖入或选择 ZIP 文件（图像/音频/点云文件夹）"
                onFile={setFile}
              />
            )}

            {/* COCO */}
            {method === 'coco' && (
              <div className="space-y-3">
                <DropZone
                  accept=".json"
                  label="拖入或选择 COCO JSON 文件"
                  onFile={setFile}
                />
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setImportAnns(!importAnns)}
                    className={`w-9 h-5 rounded-full transition-all relative flex-shrink-0
                      ${importAnns ? 'bg-[#10b981]/30' : 'bg-white/10'}`}
                  >
                    <span className={`absolute top-0.5 w-4 h-4 rounded-full transition-all
                      ${importAnns ? 'bg-[#10b981]' : 'bg-white/40'}`}
                      style={{ left: importAnns ? '1.25rem' : '0.125rem' }} />
                  </button>
                  <span className="text-xs text-white/50">同时导入已有标注（作为预标注）</span>
                </div>
              </div>
            )}

            {/* YOLO */}
            {method === 'yolo' && (
              <div className="space-y-3">
                <DropZone
                  accept=".zip"
                  label="拖入 YOLO 格式 ZIP（含 images/ 和 labels/ 文件夹）"
                  onFile={setFile}
                />
                <div>
                  <label className="block text-xs text-white/40 mb-1.5">类别名称（逗号分隔，与 classes.txt 对应）</label>
                  <input
                    value={classNames}
                    onChange={e => setClassNames(e.target.value)}
                    placeholder="car, person, truck, bicycle"
                    className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-sm text-white
                      placeholder-white/20 focus:outline-none focus:border-[#00d4ff]/40 transition-all"
                  />
                </div>
              </div>
            )}

            {/* CSV */}
            {method === 'csv' && (
              <div className="space-y-3">
                <DropZone accept=".csv" label="拖入或选择 CSV 文件" onFile={setFile} />
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-white/40 mb-1.5">文本列名</label>
                    <input
                      value={textColumn}
                      onChange={e => setTextColumn(e.target.value)}
                      placeholder="text"
                      className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white
                        focus:outline-none focus:border-[#00d4ff]/40 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-white/40 mb-1.5">标签列名（可选）</label>
                    <input
                      value={labelColumn}
                      onChange={e => setLabelColumn(e.target.value)}
                      placeholder="label"
                      className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white
                        focus:outline-none focus:border-[#00d4ff]/40 transition-all"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* JSONL */}
            {method === 'jsonl' && (
              <div className="space-y-3">
                <DropZone accept=".jsonl,.json" label="拖入 JSONL 文件（每行一个 JSON 对象）" onFile={setFile} />
                <div className="text-xs text-white/30 text-center">或粘贴内容</div>
                <textarea
                  value={bodyText}
                  onChange={e => setBodyText(e.target.value)}
                  placeholder={'{"text": "示例文本", "label": "正面"}\n{"question": "问题", "answer": "答案"}'}
                  rows={4}
                  className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-xs text-white font-mono
                    placeholder-white/15 focus:outline-none focus:border-[#00d4ff]/40 resize-none transition-all"
                />
              </div>
            )}

            {method === 'embodied' && (
              <div className="space-y-2">
                <DropZone
                  accept=".json,.jsonl"
                  label="拖入 Episode JSON（{episodes:[…]} 或单 episode）/ JSONL"
                  onFile={setFile}
                />
                <p className="text-[10px] text-white/25 leading-relaxed">
                  每个 episode 需含 streams；可选 instruction、success、proprioception（真值关节）、segments。
                </p>
              </div>
            )}

            {method === 'storage' && (
              <div className="space-y-2">
                {mounts.length > 0 && (
                  <div>
                    <label className="text-xs text-white/40">组织挂载（可选）</label>
                    <select
                      value={selectedMountId ?? ''}
                      onChange={e => {
                        const v = e.target.value
                        setSelectedMountId(v ? Number(v) : null)
                        setBrowseItems([])
                      }}
                      className="mt-1 w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-xs text-white
                        focus:outline-none focus:border-[#00d4ff]/40"
                    >
                      <option value="">使用全局前缀</option>
                      {mounts.map(m => (
                        <option key={m.id} value={m.id}>
                          {m.name} · {m.root_prefix}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
                {selectedMountId ? (
                  <>
                    <label className="text-xs text-white/40">相对路径</label>
                    <div className="flex gap-2">
                      <input
                        value={mountPath}
                        onChange={e => setMountPath(e.target.value)}
                        placeholder="留空为挂载根；如 raw/batch1"
                        className="flex-1 bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-xs text-white
                          placeholder-white/15 focus:outline-none focus:border-[#00d4ff]/40"
                      />
                      <button
                        type="button"
                        disabled={browseBusy}
                        onClick={async () => {
                          setBrowseBusy(true)
                          try {
                            const { data } = await api.get(`/storage/mounts/${selectedMountId}/browse`, {
                              params: { path: mountPath.trim(), limit: 100 },
                            })
                            setBrowseItems(data.items || [])
                            message.success(`列出 ${data.count ?? 0} 项`)
                          } catch (e: any) {
                            message.error(e?.response?.data?.detail ?? '浏览失败')
                          } finally {
                            setBrowseBusy(false)
                          }
                        }}
                        className="px-3 py-2 text-xs rounded-lg border border-[#1e1e2e] text-white/60 hover:bg-white/5"
                      >
                        {browseBusy ? '…' : '预览'}
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <label className="text-xs text-white/40">存储前缀</label>
                    <div className="flex gap-2">
                      <input
                        value={storagePrefix}
                        onChange={e => setStoragePrefix(e.target.value)}
                        placeholder="projects/1/ 或 datasets/raw/"
                        className="flex-1 bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-xs text-white
                          placeholder-white/15 focus:outline-none focus:border-[#00d4ff]/40"
                      />
                      <button
                        type="button"
                        disabled={browseBusy}
                        onClick={async () => {
                          setBrowseBusy(true)
                          try {
                            const { data } = await api.get('/storage/browse', {
                              params: { prefix: storagePrefix.trim(), limit: 100 },
                            })
                            setBrowseItems(data.items || [])
                            message.success(`列出 ${data.count ?? 0} 项`)
                          } catch (e: any) {
                            message.error(e?.response?.data?.detail ?? '浏览失败')
                          } finally {
                            setBrowseBusy(false)
                          }
                        }}
                        className="px-3 py-2 text-xs rounded-lg border border-[#1e1e2e] text-white/60 hover:bg-white/5"
                      >
                        {browseBusy ? '…' : '预览'}
                      </button>
                    </div>
                  </>
                )}
                <p className="text-[10px] text-white/25">
                  后端：{storageInfo?.backend || 'local'}
                  {storageInfo?.hint ? ` · ${storageInfo.hint}` : ''}
                </p>
                {browseItems.length > 0 && (
                  <div className="max-h-36 overflow-auto rounded-lg border border-[#1e1e2e] bg-[#0a0a0f] text-[10px] font-mono text-white/50 p-2 space-y-0.5">
                    {browseItems.slice(0, 50).map(it => (
                      <div key={it.key}>
                        {it.is_dir ? '📁 ' : '📄 '}
                        {it.key}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Common options */}
            {method !== 'coco' && (
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[#1e1e2e]">
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs text-white/40">黄金样本比例</label>
                    <span className="text-[11px] text-white/40 font-mono">{goldenRatio}%</span>
                  </div>
                  <input
                    type="range" min="0" max="20" step="1"
                    value={goldenRatio}
                    onChange={e => setGoldenRatio(parseInt(e.target.value))}
                    className="w-full"
                  />
                  <div className="text-[10px] text-white/20 mt-0.5">用于质量控制的测试题比例</div>
                </div>
                <div>
                  <label className="block text-xs text-white/40 mb-1.5">
                    任务优先级 <span className="font-mono">{priority}</span>
                  </label>
                  <input
                    type="range" min="1" max="10" step="1"
                    value={priority}
                    onChange={e => setPriority(parseInt(e.target.value))}
                    className="w-full"
                  />
                  <div className="text-[10px] text-white/20 mt-0.5">影响任务分派顺序</div>
                </div>
              </div>
            )}

            {/* Result */}
            {result && <ResultBanner result={result} />}
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-3 px-6 py-4 border-t border-[#1e1e2e]">
          <button
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl text-sm border border-white/10 text-white/40
              hover:text-white/60 hover:border-white/20 transition-all"
          >
            {result ? '关闭' : '取消'}
          </button>
          <button
            onClick={handleImport}
            disabled={loading}
            className="flex-1 py-2.5 rounded-xl text-sm font-medium transition-all active:scale-95
              disabled:opacity-40 disabled:cursor-not-allowed
              bg-[#00d4ff]/15 text-[#00d4ff] border border-[#00d4ff]/30
              hover:bg-[#00d4ff]/25 hover:border-[#00d4ff]/50"
          >
            {loading
              ? <span className="flex items-center justify-center gap-2">
                  <span className="w-3.5 h-3.5 border border-[#00d4ff]/30 border-t-[#00d4ff] rounded-full animate-spin" />
                  导入中…
                </span>
              : '开始导入'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
