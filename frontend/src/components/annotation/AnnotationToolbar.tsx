import { Tooltip } from 'antd';
import useAnnotationStore, { Tool2D, Tool3D } from '../../store/annotationStore';

// ─── Icons ────────────────────────────────────────────────────────────────────

const icons: Record<string, JSX.Element> = {
  select: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <path d="M4 3l12 7-7 1.5L7 18 4 3z" strokeLinejoin="round"/>
    </svg>
  ),
  bbox: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <rect x="3" y="3" width="14" height="14" rx="1" strokeDasharray="3 2"/>
      <circle cx="3" cy="3" r="1.5" fill="currentColor"/>
      <circle cx="17" cy="3" r="1.5" fill="currentColor"/>
      <circle cx="3" cy="17" r="1.5" fill="currentColor"/>
      <circle cx="17" cy="17" r="1.5" fill="currentColor"/>
    </svg>
  ),
  polygon: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <polygon points="10,2 18,8 15,17 5,17 2,8" strokeLinejoin="round"/>
    </svg>
  ),
  polyline: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <polyline points="2,15 7,6 13,11 18,4" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="2" cy="15" r="1.5" fill="currentColor"/>
      <circle cx="7" cy="6" r="1.5" fill="currentColor"/>
      <circle cx="13" cy="11" r="1.5" fill="currentColor"/>
      <circle cx="18" cy="4" r="1.5" fill="currentColor"/>
    </svg>
  ),
  keypoint: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <circle cx="10" cy="10" r="3"/>
      <line x1="10" y1="2" x2="10" y2="6" strokeLinecap="round"/>
      <line x1="10" y1="14" x2="10" y2="18" strokeLinecap="round"/>
      <line x1="2" y1="10" x2="6" y2="10" strokeLinecap="round"/>
      <line x1="14" y1="10" x2="18" y2="10" strokeLinecap="round"/>
    </svg>
  ),
  pan: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <path d="M10 2v4M10 14v4M2 10h4M14 10h4" strokeLinecap="round"/>
      <circle cx="10" cy="10" r="3"/>
    </svg>
  ),
  eraser: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <path d="M3 16l4-4L15 4l1 1-8 8-1 4H3z" strokeLinejoin="round"/>
      <line x1="8" y1="16" x2="17" y2="16" strokeLinecap="round"/>
    </svg>
  ),
  brush: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <path d="M4 16c2-1 3-3 3-5 0-2 2-4 5-4l2 2c0 3-2 5-4 5-2 0-4 1-6 2z" strokeLinejoin="round"/>
      <path d="M12 7l3-3 2 2-3 3" strokeLinejoin="round"/>
    </svg>
  ),
  point: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <circle cx="10" cy="10" r="2" fill="currentColor"/>
      <circle cx="10" cy="10" r="6"/>
    </svg>
  ),
  orbit: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <ellipse cx="10" cy="10" rx="8" ry="4" transform="rotate(-20 10 10)"/>
      <circle cx="10" cy="10" r="2" fill="currentColor"/>
    </svg>
  ),
  box3d: (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
      <path d="M10 2l8 4v8l-8 4-8-4V6l8-4z" strokeLinejoin="round"/>
      <line x1="10" y1="2" x2="10" y2="10" strokeDasharray="2 1"/>
      <line x1="2" y1="6" x2="10" y2="10" strokeDasharray="2 1"/>
      <line x1="18" y1="6" x2="10" y2="10" strokeDasharray="2 1"/>
    </svg>
  ),
};

// ─── Tool groups ──────────────────────────────────────────────────────────────

const TOOLS_2D: { id: Tool2D; label: string; hotkey?: string }[] = [
  { id: 'select',   label: 'Select / Move',   hotkey: 'V' },
  { id: 'bbox',     label: 'Bounding Box',     hotkey: 'B' },
  { id: 'polygon',  label: 'Polygon',          hotkey: 'P' },
  { id: 'polyline', label: 'Polyline',         hotkey: 'L' },
  { id: 'keypoint', label: 'Keypoint',         hotkey: 'K' },
  { id: 'brush',    label: 'Pixel Brush',      hotkey: 'G' },
  { id: 'pan',      label: 'Pan (Alt+drag)',   hotkey: 'H' },
  { id: 'eraser',   label: 'Eraser',           hotkey: 'E' },
];

const TOOLS_3D: { id: Tool3D; label: string; hotkey?: string }[] = [
  { id: 'select', label: 'Select',        hotkey: 'V' },
  { id: 'box3d',  label: '3D Box',        hotkey: 'B' },
  { id: 'point',  label: 'Point Label',   hotkey: 'G' },
  { id: 'orbit',  label: 'Orbit Camera',  hotkey: 'O' },
  { id: 'pan',    label: 'Pan Camera',    hotkey: 'H' },
];

// ─── AnnotationToolbar ────────────────────────────────────────────────────────

export default function AnnotationToolbar() {
  const { mode, activeTool2d, activeTool3d, setTool2d, setTool3d, undo, redo, past, future } = useAnnotationStore();

  const tools = mode === '2d' ? TOOLS_2D : TOOLS_3D;
  const activeTool = mode === '2d' ? activeTool2d : activeTool3d;
  const setTool = mode === '2d'
    ? (id: string) => setTool2d(id as Tool2D)
    : (id: string) => setTool3d(id as Tool3D);

  return (
    <div className="flex flex-col items-center gap-1 w-12 py-3 bg-[#12121a] border-r border-[#1e1e2e]">
      {/* drawing tools */}
      {tools.map((t) => (
        <Tooltip key={t.id} title={<span>{t.label}{t.hotkey && <kbd className="ml-2 text-[10px] opacity-60">{t.hotkey}</kbd>}</span>} placement="right">
          <button
            onClick={() => setTool(t.id)}
            className={`
              w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-150
              ${activeTool === t.id
                ? 'bg-[#00d4ff]/15 text-[#00d4ff] ring-1 ring-[#00d4ff]/40'
                : 'text-white/40 hover:text-white/70 hover:bg-white/5'}
            `}
          >
            {icons[t.id]}
          </button>
        </Tooltip>
      ))}

      <div className="w-6 h-px bg-[#1e1e2e] my-1" />

      {/* undo / redo */}
      <Tooltip title="Undo (Ctrl+Z)" placement="right">
        <button
          onClick={undo}
          disabled={past.length === 0}
          className="w-9 h-9 rounded-lg flex items-center justify-center text-white/40 hover:text-white/70 hover:bg-white/5 disabled:opacity-20 transition-all"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
            <path d="M4 8H13a4 4 0 010 8H8" strokeLinecap="round"/>
            <path d="M4 8l3-3M4 8l3 3" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </Tooltip>

      <Tooltip title="Redo (Ctrl+Y)" placement="right">
        <button
          onClick={redo}
          disabled={future.length === 0}
          className="w-9 h-9 rounded-lg flex items-center justify-center text-white/40 hover:text-white/70 hover:bg-white/5 disabled:opacity-20 transition-all"
        >
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
            <path d="M16 8H7a4 4 0 000 8h5" strokeLinecap="round"/>
            <path d="M16 8l-3-3M16 8l-3 3" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </Tooltip>
    </div>
  );
}
