import { Tooltip } from 'antd'
import type { View3DType } from '../../../types/annotation3d'

const VIEWS: { id: View3DType | 'fit'; label: string; short: string }[] = [
  { id: 'perspective', label: '透视 / 主视图', short: '主视' },
  { id: 'top', label: '俯视图 (Top)', short: '俯视' },
  { id: 'front', label: '正视图 (Front)', short: '正视' },
  { id: 'side', label: '侧视图 (Side)', short: '侧视' },
  { id: 'fit', label: '适配点云边界', short: '适配' },
]

interface View3DControlsProps {
  activeView: View3DType
  onSelect: (view: View3DType | 'fit') => void
}

export default function View3DControls({ activeView, onSelect }: View3DControlsProps) {
  return (
    <div className="absolute top-3 left-3 z-20 flex items-center gap-1 bg-black/55 backdrop-blur-sm border border-white/10 rounded-lg p-1 pointer-events-auto">
      {VIEWS.map((v) => {
        const isFit = v.id === 'fit'
        const active = !isFit && activeView === v.id
        return (
          <Tooltip key={v.id} title={v.label} placement="bottom">
            <button
              type="button"
              onClick={() => onSelect(v.id)}
              className={`
                h-7 px-2.5 rounded-md text-[11px] font-medium transition-all
                ${active
                  ? 'bg-[#00d4ff]/20 text-[#00d4ff] ring-1 ring-[#00d4ff]/40'
                  : 'text-white/50 hover:text-white/80 hover:bg-white/5'}
              `}
            >
              {v.short}
            </button>
          </Tooltip>
        )
      })}
    </div>
  )
}
