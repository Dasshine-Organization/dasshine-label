import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { message } from 'antd'
import api from '../../services/api'
import {
  AnnotationCategory, AnnotationType, CategoryMeta,
  LabelClass, ProjectCreatePayload, DispatchStrategy, UserLevel, ProjectSummary,
} from '../../types/project'

// ─── Constants ────────────────────────────────────────────────────────────────

const CATEGORY_ICONS: Record<string, JSX.Element> = {
  image_2d: <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5"><rect x="2" y="4" width="16" height="12" rx="2"/><circle cx="7" cy="9" r="1.5" fill="currentColor" stroke="none"/><path d="M2 14l4-4 3 3 3-3 4 4" strokeLinejoin="round"/></svg>,
  pointcloud_3d: <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5"><path d="M10 2l8 4v8l-8 4-8-4V6l8-4z" strokeLinejoin="round"/><line x1="10" y1="2" x2="10" y2="10" strokeDasharray="2 1"/><line x1="2" y1="6" x2="10" y2="10" strokeDasharray="2 1"/><line x1="18" y1="6" x2="10" y2="10" strokeDasharray="2 1"/></svg>,
  video: <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5"><rect x="2" y="4" width="12" height="12" rx="2"/><path d="M14 8l4-2v8l-4-2V8z" strokeLinejoin="round"/></svg>,
  audio: <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5"><circle cx="10" cy="10" r="3"/><path d="M10 2v3M10 15v3M2 10h3M15 10h3" strokeLinecap="round"/><path d="M4.2 4.2l2.1 2.1M13.7 13.7l2.1 2.1M4.2 15.8l2.1-2.1M13.7 6.3l2.1-2.1" strokeLinecap="round"/></svg>,
  nlp: <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5"><path d="M3 5h14M3 9h10M3 13h12M3 17h8" strokeLinecap="round"/></svg>,
  embodied: <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5"><circle cx="10" cy="4" r="2"/><path d="M10 6v5M7 8h6M8 11l-2 5M12 11l2 5M8 16h4" strokeLinecap="round" strokeLinejoin="round"/></svg>,
  ocr: <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5"><rect x="2" y="3" width="16" height="14" rx="1.5"/><path d="M5 7h4M5 10h10M5 13h7" strokeLinecap="round"/></svg>,
  multimodal: <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-5 h-5"><rect x="2" y="2" width="7" height="7" rx="1"/><rect x="11" y="2" width="7" height="7" rx="1"/><rect x="2" y="11" width="7" height="7" rx="1"/><rect x="11" y="11" width="7" height="7" rx="1"/></svg>,
}

const PRESET_COLORS = [
  '#00d4ff','#a78bfa','#10b981','#f59e0b','#ec4899',
  '#f97316','#06b6d4','#8b5cf6','#ef4444','#84cc16',
]

// ─── Step indicator ───────────────────────────────────────────────────────────

function StepDots({ current, total }: { current: number; total: number }) {
  return (
    <div className="flex items-center gap-1.5">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`rounded-full transition-all ${
            i === current ? 'w-4 h-1.5 bg-[#00d4ff]' :
            i < current  ? 'w-1.5 h-1.5 bg-[#00d4ff]/40' :
                           'w-1.5 h-1.5 bg-white/10'
          }`}
        />
      ))}
    </div>
  )
}

// ─── Step 1: Category & type selection ───────────────────────────────────────

function StepType({
  categories, selected, onSelect,
}: {
  categories: CategoryMeta[]
  selected: { category: AnnotationCategory | null; ann_type: AnnotationType | null }
  onSelect: (cat: AnnotationCategory, type: AnnotationType) => void
}) {
  const [activeCat, setActiveCat] = useState<AnnotationCategory | null>(selected.category)
  const currentCat = categories.find(c => c.id === activeCat)

  return (
    <div className="space-y-5">
      {/* Category grid */}
      <div>
        <div className="text-xs text-white/40 mb-3 uppercase tracking-widest">选择数据类型</div>
        <div className="grid grid-cols-4 gap-2">
          {categories.map(cat => (
            <button
              key={cat.id}
              onClick={() => setActiveCat(cat.id)}
              className={`flex flex-col items-center gap-2 p-3 rounded-xl border transition-all
                ${activeCat === cat.id
                  ? 'border-opacity-100 ring-1'
                  : 'border-[#1e1e2e] hover:border-white/20'}`}
              style={{
                background: activeCat === cat.id ? `${cat.color}12` : undefined,
                borderColor: activeCat === cat.id ? cat.color : undefined,
                boxShadow: activeCat === cat.id ? `0 0 0 1px ${cat.color}30` : undefined,
              }}
            >
              <span style={{ color: activeCat === cat.id ? cat.color : '#ffffff50' }}>
                {CATEGORY_ICONS[cat.id]}
              </span>
              <span className={`text-[11px] text-center leading-tight
                ${activeCat === cat.id ? 'text-white/80' : 'text-white/30'}`}>
                {cat.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Type list */}
      {currentCat && (
        <div>
          <div className="text-xs text-white/40 mb-3 uppercase tracking-widest">
            选择标注方式 — {currentCat.label}
          </div>
          <div className="grid grid-cols-2 gap-2">
            {currentCat.types.map(t => {
              const isSelected = selected.ann_type === t.id && selected.category === activeCat
              return (
                <button
                  key={t.id}
                  onClick={() => onSelect(activeCat!, t.id)}
                  className={`flex items-start gap-3 p-3 rounded-xl border text-left transition-all
                    ${isSelected ? 'border-opacity-100' : 'border-[#1e1e2e] hover:border-white/20'}`}
                  style={{
                    background: isSelected ? `${currentCat.color}12` : undefined,
                    borderColor: isSelected ? currentCat.color : undefined,
                    boxShadow: isSelected ? `0 0 0 1px ${currentCat.color}30` : undefined,
                  }}
                >
                  <div className={`w-2 h-2 rounded-full mt-1 flex-shrink-0`}
                    style={{ background: isSelected ? currentCat.color : '#ffffff20' }} />
                  <div>
                    <div className={`text-xs font-medium ${isSelected ? 'text-white/90' : 'text-white/50'}`}>
                      {t.label}
                    </div>
                    <div className="text-[10px] text-white/25 mt-0.5">{t.desc}</div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Step 2: Basic info ───────────────────────────────────────────────────────

function StepInfo({
  form, onChange,
}: {
  form: Partial<ProjectCreatePayload>
  onChange: (patch: Partial<ProjectCreatePayload>) => void
}) {
  return (
    <div className="space-y-5">
      {/* Name */}
      <div>
        <label className="block text-xs text-white/40 mb-1.5">项目名称 *</label>
        <input
          value={form.name ?? ''}
          onChange={e => onChange({ name: e.target.value })}
          placeholder="例：自动驾驶 2D 目标检测"
          className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-sm text-white
            placeholder-white/20 focus:outline-none focus:border-[#00d4ff]/50 focus:ring-1 focus:ring-[#00d4ff]/20 transition-all"
        />
      </div>

      {/* Description */}
      <div>
        <label className="block text-xs text-white/40 mb-1.5">项目描述</label>
        <textarea
          value={form.description ?? ''}
          onChange={e => onChange({ description: e.target.value })}
          placeholder="标注要求、数据来源、注意事项…"
          rows={3}
          className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-sm text-white
            placeholder-white/20 focus:outline-none focus:border-[#00d4ff]/50 resize-none transition-all"
        />
      </div>

      {/* Color */}
      <div>
        <label className="block text-xs text-white/40 mb-2">主题颜色</label>
        <div className="flex items-center gap-2 flex-wrap">
          {PRESET_COLORS.map(c => (
            <button
              key={c}
              onClick={() => onChange({ cover_color: c })}
              className={`w-6 h-6 rounded-full transition-all ${form.cover_color === c ? 'ring-2 ring-offset-1 ring-offset-[#12121a] scale-110' : 'hover:scale-110'}`}
              style={{
                background: c,
                ...(form.cover_color === c ? { boxShadow: `0 0 0 2px ${c}` } : {}),
              }}
            />
          ))}
          <input
            type="color"
            value={form.cover_color ?? '#00d4ff'}
            onChange={e => onChange({ cover_color: e.target.value })}
            className="w-6 h-6 rounded-full cursor-pointer border-0 p-0 bg-transparent"
            title="自定义颜色"
          />
        </div>
      </div>

      {/* Pricing */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-white/40 mb-1.5">单价 (¥/任务)</label>
          <input
            type="number" min="0" step="0.01"
            value={form.price_per_task ?? 0.1}
            onChange={e => onChange({ price_per_task: parseFloat(e.target.value) })}
            className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-sm text-white
              focus:outline-none focus:border-[#00d4ff]/50 transition-all"
          />
        </div>
        <div>
          <label className="block text-xs text-white/40 mb-1.5">截止日期（可选）</label>
          <input
            type="date"
            value={form.deadline?.split('T')[0] ?? ''}
            onChange={e => onChange({ deadline: e.target.value ? new Date(e.target.value).toISOString() : undefined })}
            className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-sm text-white
              focus:outline-none focus:border-[#00d4ff]/50 transition-all"
          />
        </div>
      </div>
    </div>
  )
}

// ─── Step 3: Label classes ────────────────────────────────────────────────────

function StepLabels({
  labels, onChange,
}: {
  labels: LabelClass[]
  color?: string
  onChange: (labels: LabelClass[]) => void
}) {
  const [newName, setNewName] = useState('')

  const add = () => {
    const n = newName.trim()
    if (!n || labels.find(l => l.name === n)) return
    const palette = ['#ef4444','#f59e0b','#10b981','#3b82f6','#8b5cf6','#ec4899','#14b8a6','#f97316']
    onChange([...labels, { name: n, color: palette[labels.length % palette.length] }])
    setNewName('')
  }

  const remove = (i: number) => onChange(labels.filter((_, idx) => idx !== i))

  const updateColor = (i: number, c: string) =>
    onChange(labels.map((l, idx) => idx === i ? { ...l, color: c } : l))

  const updateHotkey = (i: number, k: string) =>
    onChange(labels.map((l, idx) => idx === i ? { ...l, hotkey: k.slice(0, 1) } : l))

  return (
    <div className="space-y-4">
      <div className="text-xs text-white/40 uppercase tracking-widest">标签类别</div>

      {/* Add row */}
      <div className="flex gap-2">
        <input
          value={newName}
          onChange={e => setNewName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && add()}
          placeholder="输入标签名称，回车添加"
          className="flex-1 bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm text-white
            placeholder-white/20 focus:outline-none focus:border-[#00d4ff]/50 transition-all"
        />
        <button
          onClick={add}
          className="px-4 py-2 rounded-lg text-xs bg-[#00d4ff]/10 text-[#00d4ff] border border-[#00d4ff]/20
            hover:bg-[#00d4ff]/20 active:scale-95 transition-all"
        >
          添加
        </button>
      </div>

      {/* Label list */}
      {labels.length === 0 ? (
        <div className="text-center py-6 text-xs text-white/20">
          暂无标签，部分任务类型（如文本分类、情感分析）需要预定义标签
        </div>
      ) : (
        <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
          {labels.map((lc, i) => (
            <div key={i} className="flex items-center gap-2.5 bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2">
              <input
                type="color"
                value={lc.color}
                onChange={e => updateColor(i, e.target.value)}
                className="w-5 h-5 rounded cursor-pointer border-0 bg-transparent p-0 flex-shrink-0"
              />
              <span className="text-sm text-white/80 flex-1">{lc.name}</span>
              <input
                value={lc.hotkey ?? ''}
                onChange={e => updateHotkey(i, e.target.value)}
                placeholder="快捷键"
                maxLength={1}
                className="w-12 text-center bg-[#1e1e2e] border border-white/10 rounded px-1 py-0.5 text-xs text-white/50 focus:outline-none focus:border-[#00d4ff]/40"
              />
              <button
                onClick={() => remove(i)}
                className="text-white/20 hover:text-red-400 transition-colors flex-shrink-0"
              >
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
                  <path d="M2 2l10 10M2 12L12 2" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Step 4: Dispatch settings ────────────────────────────────────────────────

function StepDispatch({
  form, onChange,
}: {
  form: Partial<ProjectCreatePayload>
  onChange: (patch: Partial<ProjectCreatePayload>) => void
}) {
  const STRATEGIES = [
    { id: 'smart',       label: '智能分派', desc: '综合技能/质量/负载评分选择最优标注员' },
    { id: 'round_robin', label: '轮询分派', desc: '依次循环分配，确保均衡' },
    { id: 'random',      label: '随机分派', desc: '随机选择符合条件的标注员' },
    { id: 'manual',      label: '手动分派', desc: '项目经理手动指定标注员' },
  ]
  const LEVELS = ['novice','junior','intermediate','senior','expert']
  const LEVEL_LABELS: Record<string, string> = {
    novice: '新手', junior: '初级', intermediate: '中级', senior: '高级', expert: '专家'
  }

  return (
    <div className="space-y-5">
      {/* Strategy */}
      <div>
        <div className="text-xs text-white/40 mb-3 uppercase tracking-widest">分派策略</div>
        <div className="grid grid-cols-2 gap-2">
          {STRATEGIES.map(s => {
            const isSelected = (form.dispatch_strategy ?? 'smart') === s.id
            return (
              <button
                key={s.id}
                onClick={() => onChange({ dispatch_strategy: s.id as DispatchStrategy })}
                className={`p-3 rounded-xl border text-left transition-all
                  ${isSelected
                    ? 'bg-[#00d4ff]/10 border-[#00d4ff]/40 ring-1 ring-[#00d4ff]/20'
                    : 'border-[#1e1e2e] hover:border-white/20'}`}
              >
                <div className={`text-xs font-medium mb-0.5 ${isSelected ? 'text-[#00d4ff]' : 'text-white/60'}`}>
                  {s.label}
                </div>
                <div className="text-[10px] text-white/25 leading-tight">{s.desc}</div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Numeric settings */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-white/40 mb-1.5">每人批次任务数</label>
          <input
            type="number" min="1" max="500"
            value={form.tasks_per_annotator ?? 10}
            onChange={e => onChange({ tasks_per_annotator: parseInt(e.target.value) })}
            className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-sm text-white
              focus:outline-none focus:border-[#00d4ff]/50 transition-all"
          />
        </div>
        <div>
          <label className="block text-xs text-white/40 mb-1.5">交叉验证人数</label>
          <input
            type="number" min="1" max="5"
            value={form.cross_validate_count ?? 1}
            onChange={e => onChange({ cross_validate_count: parseInt(e.target.value) })}
            className="w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2.5 text-sm text-white
              focus:outline-none focus:border-[#00d4ff]/50 transition-all"
          />
          <div className="text-[10px] text-white/20 mt-1">每个任务由几人独立标注</div>
        </div>
      </div>

      {/* Min level */}
      <div>
        <label className="block text-xs text-white/40 mb-2">最低标注员等级</label>
        <div className="flex gap-2">
          {LEVELS.map(lv => (
            <button
              key={lv}
              onClick={() => onChange({ min_level: lv as UserLevel })}
              className={`flex-1 py-1.5 rounded-lg text-xs transition-all
                ${(form.min_level ?? 'novice') === lv
                  ? 'bg-[#00d4ff]/15 text-[#00d4ff] border border-[#00d4ff]/30'
                  : 'bg-[#0a0a0f] border border-[#1e1e2e] text-white/30 hover:text-white/60'}`}
            >
              {LEVEL_LABELS[lv]}
            </button>
          ))}
        </div>
      </div>

      {/* Auto-label */}
      <div className="bg-[#0a0a0f] border border-[#1e1e2e] rounded-xl p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="text-xs font-medium text-white/70">AI 自动预标注</div>
            <div className="text-[10px] text-white/30 mt-0.5">减少 70% 人工工作量</div>
          </div>
          <button
            onClick={() => onChange({ auto_label_enabled: !form.auto_label_enabled })}
            className={`w-10 h-5 rounded-full transition-all relative flex-shrink-0
              ${form.auto_label_enabled ? 'bg-[#00d4ff]/30' : 'bg-white/10'}`}
          >
            <span className={`absolute top-0.5 w-4 h-4 rounded-full transition-all
              ${form.auto_label_enabled ? 'left-5.5 bg-[#00d4ff]' : 'left-0.5 bg-white/40'}`}
              style={{ left: form.auto_label_enabled ? '1.375rem' : '0.125rem' }}
            />
          </button>
        </div>
        {form.auto_label_enabled && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] text-white/30 mb-1">模型</label>
              <select
                value={form.auto_label_model ?? 'gpt-4o'}
                onChange={e => onChange({ auto_label_model: e.target.value })}
                className="w-full bg-[#12121a] border border-[#1e1e2e] rounded-lg px-2 py-1.5 text-xs text-white
                  focus:outline-none focus:border-[#00d4ff]/50 transition-all"
              >
                <option value="gpt-4o">GPT-4o</option>
                <option value="gpt-4-vision">GPT-4 Vision</option>
                <option value="claude-3-opus">Claude 3 Opus</option>
                <option value="qwen-vl">通义千问 VL</option>
                <option value="ernie-4">文心 4.0</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] text-white/30 mb-1">
                置信度阈值 {Math.round((form.auto_label_threshold ?? 0.8) * 100)}%
              </label>
              <input
                type="range" min="0.5" max="0.99" step="0.01"
                value={form.auto_label_threshold ?? 0.8}
                onChange={e => onChange({ auto_label_threshold: parseFloat(e.target.value) })}
                className="w-full"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ─── CreateProjectModal ───────────────────────────────────────────────────────

interface Props {
  onClose: () => void
  onCreated: (project: ProjectSummary) => void
}

const STEPS = ['类型', '基本信息', '标签', '分派设置']
const TOTAL = STEPS.length

const FALLBACK_CATEGORIES = [
  { id: 'image_2d', label: '图像 2D', icon: 'image', color: '#00d4ff', types: [
      { id: 'bbox_2d', label: '矩形框', desc: '目标检测' },
      { id: 'polygon', label: '多边形', desc: '实例轮廓' },
      { id: 'polyline', label: '折线', desc: '车道线/骨架' },
      { id: 'keypoint', label: '关键点', desc: '姿态 · 可插 COCO-17' },
      { id: 'segmentation', label: '语义分割', desc: '像素画笔' },
      { id: 'classification', label: '图像分类', desc: '整图标签' },
  ]},
  { id: 'pointcloud_3d', label: '3D 点云', icon: 'cube', color: '#a78bfa', types: [
      { id: 'bbox_3d', label: '3D 包围盒', desc: '自动驾驶检测' },
      { id: 'lidar_seg', label: '点云分割', desc: '逐点语义刷' },
  ]},
  { id: 'video', label: '视频', icon: 'video', color: '#f59e0b', types: [
      { id: 'video_tracking', label: '目标追踪', desc: '帧上画框 + track_id + 插值' },
      { id: 'video_action', label: '动作识别', desc: '时序片段' },
      { id: 'video_caption', label: '视频描述', desc: '字幕/描述' },
  ]},
  { id: 'audio', label: '语音', icon: 'mic', color: '#10b981', types: [
      { id: 'asr', label: '语音转写', desc: 'ASR 标注' },
      { id: 'tts_label', label: '语音质量', desc: 'TTS MOS' },
      { id: 'speaker_diarize', label: '说话人分离', desc: '多人对话' },
      { id: 'emotion_audio', label: '情绪识别', desc: '语音情感' },
  ]},
  { id: 'nlp', label: '语料', icon: 'text', color: '#ec4899', types: [
      { id: 'ner', label: '命名实体识别', desc: 'NER' },
      { id: 're', label: '关系抽取', desc: '实体关系' },
      { id: 'sentiment', label: '情感分析', desc: '正负中性' },
      { id: 'text_classify', label: '文本分类', desc: '多标签' },
      { id: 'qa_pair', label: '问答对', desc: 'SFT 数据' },
      { id: 'summarization', label: '摘要', desc: '文本压缩' },
      { id: 'translation', label: '翻译', desc: '双语对齐' },
  ]},
  { id: 'embodied', label: '具身机器人', icon: 'robot', color: '#f97316', types: [
      { id: 'robot_traj', label: '轨迹标注', desc: '运动路径' },
      { id: 'robot_action', label: '动作序列', desc: '操作步骤' },
      { id: 'robot_grasp', label: '抓取标注', desc: '抓取点/姿态' },
      { id: 'robot_scene', label: '场景理解', desc: '空间关系' },
  ]},
  { id: 'ocr', label: 'OCR', icon: 'scan', color: '#06b6d4', types: [
      { id: 'ocr_text', label: '文字检测识别', desc: '端到端 OCR' },
      { id: 'ocr_layout', label: '版面分析', desc: '区域分类' },
      { id: 'ocr_table', label: '表格识别', desc: '结构化提取' },
  ]},
  { id: 'multimodal', label: '多模态', icon: 'layers', color: '#8b5cf6', types: [
      { id: 'image_caption', label: '图文描述', desc: 'Caption 生成' },
      { id: 'vqa', label: '视觉问答', desc: 'VQA 数据' },
      { id: 'rlhf', label: 'RLHF 偏好', desc: '成对回复选择' },
  ]},
] as CategoryMeta[]

export default function CreateProjectModal({ onClose, onCreated }: Props) {
  const [step, setStep] = useState(0)
  const [categories, setCategories] = useState<CategoryMeta[]>(FALLBACK_CATEGORIES)
  const [loading, setLoading] = useState(false)

  const [form, setForm] = useState<Partial<ProjectCreatePayload>>({
    name: '',
    description: '',
    cover_color: '#00d4ff',
    label_classes: [],
    required_skills: [],
    min_level: 'novice',
    dispatch_strategy: 'smart',
    tasks_per_annotator: 10,
    cross_validate_count: 1,
    price_per_task: 0.1,
    bonus_rate: 0,
    auto_label_enabled: false,
    auto_label_model: 'gpt-4o',
    auto_label_threshold: 0.8,
    schema_config: {},
  })

  const patch = (p: Partial<ProjectCreatePayload>) => setForm(f => ({ ...f, ...p }))

  // Load annotation type metadata
  useEffect(() => {
    api.get('/projects/meta/types')
      .then(r => {
        const list = r.data?.categories
        if (Array.isArray(list) && list.length > 0) setCategories(list)
      })
      .catch(() => {
        setCategories(FALLBACK_CATEGORIES)
      })
  }, [])

  // Validation per step
  function canNext(): boolean {
    if (step === 0) return !!(form.category && form.ann_type)
    if (step === 1) return !!(form.name && form.name.length >= 2)
    return true
  }

  async function handleCreate() {
    setLoading(true)
    try {
      const { data } = await api.post('/projects', form)
      message.success({ content: `项目「${form.name}」创建成功`, duration: 3 })
      onCreated({
        id: data.id,
        name: data.name ?? form.name ?? '未命名项目',
        cover_color: data.cover_color ?? form.cover_color,
        category: data.category ?? form.category,
        ann_type: data.ann_type ?? form.ann_type,
        status: data.status ?? 'draft',
        total_items: data.total_items ?? 0,
        approved_items: data.approved_items ?? 0,
        price_per_task: data.price_per_task ?? form.price_per_task ?? 0.1,
        member_count: data.member_count ?? 1,
      })
    } catch (e: any) {
      message.error({ content: e?.response?.data?.detail ?? '创建失败，请检查配置', duration: 3 })
    } finally {
      setLoading(false)
    }
  }

  const color = form.cover_color ?? '#00d4ff'

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-2xl bg-[#12121a] border border-[#1e1e2e] rounded-2xl overflow-hidden"
        style={{ boxShadow: `0 0 60px ${color}15` }}>

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#1e1e2e]"
          style={{ background: `linear-gradient(135deg, ${color}08 0%, transparent 60%)` }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: `${color}15`, border: `1px solid ${color}30` }}>
              <div className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
            </div>
            <div>
              <div className="text-sm font-medium text-white/80">新建项目</div>
              <div className="text-[11px] text-white/30">{STEPS[step]}</div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <StepDots current={step} total={TOTAL} />
            <button type="button" onClick={onClose} className="text-white/30 hover:text-white/70 transition-colors">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
                <path d="M3 3l10 10M13 3L3 13" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5 overflow-y-auto" style={{ maxHeight: '60vh' }}>
          {step === 0 && (
            <StepType
              categories={categories}
              selected={{ category: form.category ?? null, ann_type: form.ann_type ?? null }}
              onSelect={(cat, type) => patch({ category: cat, ann_type: type })}
            />
          )}
          {step === 1 && <StepInfo form={form} onChange={patch} />}
          {step === 2 && (
            <StepLabels
              labels={form.label_classes ?? []}
              color={color}
              onChange={lcs => patch({ label_classes: lcs })}
            />
          )}
          {step === 3 && <StepDispatch form={form} onChange={patch} />}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-[#1e1e2e]">
          <button
            type="button"
            onClick={() => setStep(s => s - 1)}
            disabled={step === 0}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm text-white/40
              hover:text-white/70 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
              <path d="M10 12L6 8l4-4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            上一步
          </button>

          <div className="text-xs text-white/20">{step + 1} / {TOTAL}</div>

          {step < TOTAL - 1 ? (
            <button
              type="button"
              onClick={() => setStep(s => s + 1)}
              disabled={!canNext()}
              className={`flex items-center gap-1.5 px-5 py-2 rounded-lg text-sm font-medium transition-all active:scale-95
                ${canNext()
                  ? 'text-[#00d4ff] border border-[#00d4ff]/30 hover:bg-[#00d4ff]/10'
                  : 'text-white/20 border border-white/10 cursor-not-allowed'}`}
              style={canNext() ? { background: `${color}10` } : undefined}
            >
              下一步
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
                <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleCreate}
              disabled={loading || !canNext()}
              className="flex items-center gap-2 px-6 py-2 rounded-lg text-sm font-medium transition-all active:scale-95
                disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ background: `${color}20`, color, border: `1px solid ${color}40` }}
            >
              {loading
                ? <span className="w-3.5 h-3.5 border border-current/30 border-t-current rounded-full animate-spin" />
                : <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
                    <path d="M2 8l4 4 8-8" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>}
              创建项目
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
