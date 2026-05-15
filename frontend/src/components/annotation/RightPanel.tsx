import { useState } from 'react';
import { Slider, Switch, Modal, Input, message } from 'antd';
import { v4 as uuid } from 'uuid';
import useAnnotationStore, { LabelClass } from '../../store/annotationStore';

export interface LabelClassAcl {
  canAddEdit: boolean;
  canDelete: boolean;
}

interface RightPanelProps {
  /** 不传则不展示标签类的新建/编辑/删除 */
  labelClassAcl?: LabelClassAcl;
}

// ─── LabelPanel ───────────────────────────────────────────────────────────────

function LabelPanel({ labelClassAcl }: { labelClassAcl?: LabelClassAcl }) {
  const { labelClasses, activeLabel, setActiveLabel, addLabelClass, updateLabelClass, removeLabelClass } =
    useAnnotationStore();
  const [addOpen, setAddOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [formName, setFormName] = useState('');
  const [formColor, setFormColor] = useState('#00d4ff');

  function openAdd() {
    setFormName('');
    setFormColor('#94a3b8');
    setAddOpen(true);
  }

  function submitAdd() {
    const name = formName.trim();
    if (!name) {
      message.warning('请输入标签名称');
      return;
    }
    if (labelClasses.some((c) => c.name === name)) {
      message.warning('标签名称已存在');
      return;
    }
    const hotkeys = '123456789'.split('');
    const used = new Set(labelClasses.map((c) => c.hotkey).filter(Boolean));
    const hk = hotkeys.find((h) => !used.has(h));
    addLabelClass({ id: uuid(), name, color: formColor, hotkey: hk });
    setAddOpen(false);
    message.success('已添加标签');
  }

  function openEdit(lc: LabelClass) {
    setEditId(lc.id);
    setFormName(lc.name);
    setFormColor(lc.color);
  }

  function submitEdit() {
    if (!editId) return;
    const name = formName.trim();
    if (!name) {
      message.warning('请输入标签名称');
      return;
    }
    const other = labelClasses.find((c) => c.id !== editId && c.name === name);
    if (other) {
      message.warning('标签名称已存在');
      return;
    }
    updateLabelClass(editId, { name, color: formColor });
    setEditId(null);
    message.success('已更新标签');
  }

  function confirmRemove(lc: LabelClass) {
    Modal.confirm({
      title: `删除标签「${lc.name}」？`,
      content: '该标签下的标注将迁移到列表中的第一个标签。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => {
        removeLabelClass(lc.id);
        message.success('已删除标签');
      },
    });
  }

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between px-1 mb-2">
        <div className="text-[10px] text-white/30 uppercase tracking-widest">Labels</div>
        {labelClassAcl?.canAddEdit && (
          <button
            type="button"
            onClick={openAdd}
            className="text-[10px] text-[#00d4ff]/80 hover:text-[#00d4ff] transition-colors"
          >
            + 新建
          </button>
        )}
      </div>
      {labelClasses.map((lc) => (
        <div key={lc.id} className="flex items-stretch gap-1 group/row">
          <button
            type="button"
            onClick={() => setActiveLabel(lc.name)}
            className={`
              flex-1 flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-left transition-all
              ${activeLabel === lc.name
                ? 'bg-[#1e1e2e] ring-1 text-white'
                : 'text-white/50 hover:text-white/80 hover:bg-white/5'}
            `}
            style={{
              ['--ring-color' as string]: lc.color,
              boxShadow: activeLabel === lc.name ? `0 0 0 1px ${lc.color}40` : undefined,
            }}
          >
            <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: lc.color }} />
            <span className="text-xs flex-1 truncate">{lc.name}</span>
            {lc.hotkey && (
              <kbd className="text-[10px] opacity-40 bg-white/10 px-1 py-0.5 rounded">{lc.hotkey}</kbd>
            )}
          </button>
          {labelClassAcl?.canAddEdit && (
            <div className="flex flex-col justify-center gap-0.5 opacity-0 group-hover/row:opacity-100 transition-opacity pr-0.5">
              <button
                type="button"
                title="编辑"
                onClick={() => openEdit(lc)}
                className="text-white/30 hover:text-[#00d4ff] p-1"
              >
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3 h-3">
                  <path d="M11 2H9l-6 6v3h3l6-6V2z" strokeLinejoin="round" />
                </svg>
              </button>
              {labelClassAcl.canDelete && (
                <button
                  type="button"
                  title="删除"
                  onClick={() => confirmRemove(lc)}
                  className="text-white/30 hover:text-red-400 p-1"
                >
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3 h-3">
                    <path d="M3 3l10 10M3 13L13 3" strokeLinecap="round" />
                  </svg>
                </button>
              )}
            </div>
          )}
        </div>
      ))}

      <Modal
        title="新建标签"
        open={addOpen}
        onOk={submitAdd}
        onCancel={() => setAddOpen(false)}
        okText="添加"
        destroyOnClose
      >
        <div className="space-y-3 pt-2">
          <div>
            <div className="text-xs text-white/50 mb-1">名称</div>
            <Input value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="例如 obstacle" />
          </div>
          <div>
            <div className="text-xs text-white/50 mb-1">颜色</div>
            <input
              type="color"
              value={formColor}
              onChange={(e) => setFormColor(e.target.value)}
              className="w-full h-9 rounded cursor-pointer bg-transparent border border-white/10"
            />
          </div>
        </div>
      </Modal>

      <Modal
        title="编辑标签"
        open={!!editId}
        onOk={submitEdit}
        onCancel={() => setEditId(null)}
        okText="保存"
        destroyOnClose
      >
        <div className="space-y-3 pt-2">
          <div>
            <div className="text-xs text-white/50 mb-1">名称</div>
            <Input value={formName} onChange={(e) => setFormName(e.target.value)} />
          </div>
          <div>
            <div className="text-xs text-white/50 mb-1">颜色</div>
            <input
              type="color"
              value={formColor}
              onChange={(e) => setFormColor(e.target.value)}
              className="w-full h-9 rounded cursor-pointer bg-transparent border border-white/10"
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}

// ─── AnnotationList2D ────────────────────────────────────────────────────────

function AnnotationList2D() {
  const {
    annotations2d, selectedIds2d,
    selectAnnotations2d, deleteAnnotation2d, updateAnnotation2d,
  } = useAnnotationStore();

  if (annotations2d.length === 0)
    return <div className="text-xs text-white/20 text-center py-6">暂无标注</div>
  return (
    <div className="space-y-1">
      {annotations2d.map((ann) => {
        const isSelected = selectedIds2d.includes(ann.id)
        return (
          <div
            key={ann.id}
            onClick={() => selectAnnotations2d([ann.id])}
            className={`flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-all group
              ${isSelected ? 'bg-[#1e1e2e]' : 'hover:bg-white/5'}`}
            style={{ boxShadow: isSelected ? `0 0 0 1px ${ann.color}40` : undefined }}
          >
            <span className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: ann.color }} />
            <span className="text-xs text-white/70 flex-1 truncate">{ann.label}</span>
            <span className="text-[10px] text-white/30">{ann.type}</span>
            {ann.isAI && <span className="text-[10px] text-[#00d4ff]/60">AI</span>}
            {ann.score != null && <span className="text-[10px] text-white/30">{(ann.score * 100).toFixed(0)}%</span>}
            <button
              onClick={(e) => { e.stopPropagation(); updateAnnotation2d(ann.id, { visible: !ann.visible }) }}
              className="opacity-0 group-hover:opacity-100 text-white/30 hover:text-white/70 transition-all"
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
                <path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5z"/><circle cx="8" cy="8" r="2"/>
              </svg>
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); deleteAnnotation2d([ann.id]) }}
              className="opacity-0 group-hover:opacity-100 text-white/30 hover:text-red-400 transition-all"
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
                <path d="M3 3l10 10M3 13L13 3" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        )
      })}
    </div>
  )
}

// ─── AnnotationList3D ────────────────────────────────────────────────────────

function AnnotationList3D() {
  const { boxes3d, selectedIds3d, selectBoxes3d, deleteBox3d, updateBox3d } = useAnnotationStore()
  if (boxes3d.length === 0)
    return <div className="text-xs text-white/20 text-center py-6">暂无 3D 框</div>
  return (
    <div className="space-y-1">
      {boxes3d.map((box) => {
        const isSelected = selectedIds3d.includes(box.id)
        return (
          <div
            key={box.id}
            onClick={() => selectBoxes3d([box.id])}
            className={`flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-all group
              ${isSelected ? 'bg-[#1e1e2e]' : 'hover:bg-white/5'}`}
            style={{ boxShadow: isSelected ? `0 0 0 1px ${box.color}40` : undefined }}
          >
            <span className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: box.color }} />
            <span className="text-xs text-white/70 flex-1 truncate">{box.label}</span>
            <span className="text-[10px] text-white/30">
              {box.size.x.toFixed(1)}×{box.size.y.toFixed(1)}×{box.size.z.toFixed(1)}
            </span>
            {box.isAI && <span className="text-[10px] text-[#00d4ff]/60">AI</span>}
            <button
              onClick={(e) => { e.stopPropagation(); deleteBox3d([box.id]) }}
              className="opacity-0 group-hover:opacity-100 text-white/30 hover:text-red-400 transition-all"
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-3.5 h-3.5">
                <path d="M3 3l10 10M3 13L13 3" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        )
      })}
    </div>
  );
}

// ─── PropertiesPanel ─────────────────────────────────────────────────────────

function PropertiesPanel() {
  const { mode, annotations2d, selectedIds2d, boxes3d, selectedIds3d, updateAnnotation2d, updateBox3d } = useAnnotationStore();

  if (mode === '2d') {
    if (selectedIds2d.length === 0) return null;
    const ann = annotations2d.find((a) => a.id === selectedIds2d[0]);
    if (!ann) return null;
    const [x1, y1] = [ann.points[0]?.x ?? 0, ann.points[0]?.y ?? 0];
    const [x2, y2] = ann.type === 'bbox'
      ? [ann.points[1]?.x ?? 0, ann.points[1]?.y ?? 0]
      : [ann.points[ann.points.length - 1]?.x ?? 0, ann.points[ann.points.length - 1]?.y ?? 0];

    return (
      <div className="mt-4 border-t border-[#1e1e2e] pt-4 space-y-2">
        <div className="text-[10px] text-white/30 uppercase tracking-widest mb-2">Properties</div>
        <div className="grid grid-cols-2 gap-1.5 text-xs">
          {ann.type === 'bbox' && <>
            <div className="text-white/40">X</div><div className="text-white/70 font-mono">{x1.toFixed(1)}</div>
            <div className="text-white/40">Y</div><div className="text-white/70 font-mono">{y1.toFixed(1)}</div>
            <div className="text-white/40">W</div><div className="text-white/70 font-mono">{(x2-x1).toFixed(1)}</div>
            <div className="text-white/40">H</div><div className="text-white/70 font-mono">{(y2-y1).toFixed(1)}</div>
          </>}
          <div className="text-white/40">Points</div>
          <div className="text-white/70 font-mono">{ann.points.length}</div>
          <div className="text-white/40">Locked</div>
          <div>
            <Switch
              size="small"
              checked={ann.locked}
              onChange={(v) => updateAnnotation2d(ann.id, { locked: v })}
            />
          </div>
        </div>
      </div>
    );
  } else {
    if (selectedIds3d.length === 0) return null;
    const box = boxes3d.find((b) => b.id === selectedIds3d[0]);
    if (!box) return null;
    return (
      <div className="mt-4 border-t border-[#1e1e2e] pt-4 space-y-2">
        <div className="text-[10px] text-white/30 uppercase tracking-widest mb-2">Box Properties</div>
        <div className="grid grid-cols-2 gap-1.5 text-xs">
          <div className="text-white/40">Center X</div><div className="text-white/70 font-mono">{box.center.x.toFixed(2)}</div>
          <div className="text-white/40">Center Y</div><div className="text-white/70 font-mono">{box.center.y.toFixed(2)}</div>
          <div className="text-white/40">Center Z</div><div className="text-white/70 font-mono">{box.center.z.toFixed(2)}</div>
          <div className="text-white/40">W×H×D</div>
          <div className="text-white/70 font-mono text-[10px]">
            {box.size.x.toFixed(1)}×{box.size.y.toFixed(1)}×{box.size.z.toFixed(1)}
          </div>
          <div className="text-white/40">Rot Y</div>
          <div className="text-white/70 font-mono">{(box.rotation.y * 180 / Math.PI).toFixed(1)}°</div>
          <div className="text-white/40">Locked</div>
          <div><Switch size="small" checked={box.locked} onChange={(v) => updateBox3d(box.id, { locked: v })} /></div>
        </div>
      </div>
    );
  }
}

// ─── SettingsPanel ────────────────────────────────────────────────────────────

function SettingsPanel() {
  const { showLabels, showConfidence, opacity, toggleLabels, toggleConfidence, setOpacity } = useAnnotationStore()
  return (
    <div className="space-y-3 pt-3 border-t border-[#1e1e2e]">
      <div className="text-[10px] text-white/30 uppercase tracking-widest">显示设置</div>
      <div className="flex items-center justify-between">
        <span className="text-xs text-white/50">显示标签</span>
        <Switch size="small" checked={showLabels} onChange={toggleLabels} />
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs text-white/50">显示置信度</span>
        <Switch size="small" checked={showConfidence} onChange={toggleConfidence} />
      </div>
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <span className="text-xs text-white/50">填充透明度</span>
          <span className="text-[10px] text-white/30 font-mono">{Math.round(opacity * 100)}%</span>
        </div>
        <Slider min={0} max={1} step={0.05} value={opacity} onChange={setOpacity}
          className="!m-0" tooltip={{ open: false }} />
      </div>
    </div>
  )
}

// ─── RightPanel ───────────────────────────────────────────────────────────────

export default function RightPanel({ labelClassAcl }: RightPanelProps) {
  const [activeTab, setActiveTab] = useState<'labels' | 'list' | 'settings'>('labels');
  const { mode, annotations2d, boxes3d } = useAnnotationStore();

  const TABS = [
    { key: 'labels' as const,   label: '标签' },
    { key: 'list' as const,     label: `列表(${count})` },
    { key: 'drafts' as const,   label: '草稿', badge: autoSaveMeta.isDirty },
    { key: 'settings' as const, label: '设置' },
  ]

  return (
    <div className="w-60 flex flex-col bg-[#12121a] border-l border-[#1e1e2e] overflow-hidden">
      {/* Tabs */}
      <div className="flex border-b border-[#1e1e2e]">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex-1 py-2.5 text-[11px] relative transition-all
              ${activeTab === tab.key
                ? 'text-[#00d4ff] border-b-2 border-[#00d4ff] -mb-px'
                : 'text-white/30 hover:text-white/60'}`}
          >
            {tab.label}
            {tab.badge && (
              <span className="absolute top-2 right-1 w-1.5 h-1.5 rounded-full bg-[#f59e0b]" />
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-thin scrollbar-thumb-white/10">
        {activeTab === 'labels' && (
          <>
            <LabelPanel labelClassAcl={labelClassAcl} />
            <PropertiesPanel />
          </>
        )}
        {activeTab === 'list' && (
          mode === '2d' ? <AnnotationList2D /> : <AnnotationList3D />
        )}
        {activeTab === 'settings' && <SettingsPanel />}
      </div>
    </div>
  )
}
