import { useState, useRef, useCallback } from 'react'
import { message } from 'antd'
import api from '../../services/api'

// ─── Types ────────────────────────────────────────────────────────────────────

type ImportMethod = 'url' | 'text' | 'zip' | 'coco' | 'yolo' | 'csv' | 'jsonl'

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

// ─── Method config ────────────────────────────────────────────────────────────

const METHODS: { id: ImportMethod; label: string; desc: string; icon: JSX.Element; color: string; forCategories?: string[] }[] = [
  {
    id: 'url',
    label: 'URL 列表',
    desc: '粘贴图像/音频/视频链接，每行一个',
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
    id: 'zip',
    label: 'ZIP 文件夹',
    desc: '上传包含图像/音频/点云的压缩包',
    color: '#f59e0b',
    icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4"><path d="M4 2h5l3 3v9a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M9 2v3h3M7 8v5M5.5 9.5L7 8l1.5 1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  },
  {
    id: 'coco',
    label: 'COCO JSON',
    desc: '导入 MS COCO 格式标注数据集',
    color: '#10b981',
    forCategories: ['image_2d'],
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
    forCategories: ['nlp', 'multimodal', 'embodied'],
    icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4"><path d="M4 4C4 4 2 5 2 8s2 4 2 4M12 4c0 0 2 1 2 4s-2 4-2 4M6 9l1.5-2L9 9l1.5-2" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  },
]

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
  const [method, setMethod] = useState<ImportMethod>('url')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ImportResult | null>(null)

  // Form states
  const [urlText, setUrlText] = useState('')
  const [bodyText, setBodyText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [classNames, setClassNames] = useState('')
  const [textColumn, setTextColumn] = useState('text')
  const [labelColumn, setLabelColumn] = useState('')
  const [importAnns, setImportAnns] = useState(true)
  const [goldenRatio, setGoldenRatio] = useState(5)
  const [priority, setPriority] = useState(5)

  // Filter methods by category
  const availableMethods = METHODS.filter(m =>
    !m.forCategories || m.forCategories.includes(category)
  )

  const activeMethod = METHODS.find(m => m.id === method)!

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

      } else if (method === 'zip') {
        if (!file) throw new Error('请选择 ZIP 文件')
        const form = new FormData()
        form.append('file', file)
        form.append('priority', String(priority))
        form.append('golden_ratio', String(goldenRatio / 100))
        const { data } = await api.post(`/projects/${projectId}/import/zip`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        res = data

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
        const { data } = await api.post(`/projects/${projectId}/import/yolo`, form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        res = data

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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
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
    </div>
  )
}
