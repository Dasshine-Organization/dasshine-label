import { InputNumber, Switch } from 'antd'
import useAnnotationStore, { type Box3D } from '../../../store/annotationStore'

type Props = {
  box: Box3D
  updateBox3d: (id: string, patch: Partial<Box3D>) => void
}

export default function Box3DPropertyEditor({ box, updateBox3d }: Props) {
  const commit = (patch: Partial<Box3D>) => {
    if (box.locked) return
    updateBox3d(box.id, patch)
  }

  const num = (
    label: string,
    value: number,
    onChange: (v: number) => void,
    step = 0.1,
    min = 0.25,
  ) => (
    <>
      <div className="text-white/40">{label}</div>
      <InputNumber
        size="small"
        className="w-full !bg-[#0a0a0f] !border-[#1e1e2e]"
        value={value}
        step={step}
        min={min}
        disabled={box.locked}
        onFocus={() => useAnnotationStore.getState().pushHistory()}
        onChange={(v) => v != null && onChange(v)}
      />
    </>
  )

  return (
    <div className="grid grid-cols-2 gap-1.5 text-xs items-center">
      {num('中心 X', box.center.x, (v) => commit({ center: { ...box.center, x: v } }))}
      {num('中心 Y', box.center.y, (v) => commit({ center: { ...box.center, y: v } }))}
      {num('中心 Z', box.center.z, (v) => commit({ center: { ...box.center, z: v } }))}
      {num('宽度 X', box.size.x, (v) => commit({ size: { ...box.size, x: v } }), 0.1, 0.25)}
      {num('高度 Y', box.size.y, (v) => commit({ size: { ...box.size, y: v } }), 0.1, 0.25)}
      {num('深度 Z', box.size.z, (v) => commit({ size: { ...box.size, z: v } }), 0.1, 0.25)}
      {num(
        '旋转 Y°',
        (box.rotation.y * 180) / Math.PI,
        (deg) => commit({ rotation: { ...box.rotation, y: (deg * Math.PI) / 180 } }),
        1,
        -180,
      )}
      <div className="text-white/40">锁定</div>
      <div>
        <Switch
          size="small"
          checked={box.locked}
          onChange={(v) => {
            useAnnotationStore.getState().pushHistory()
            updateBox3d(box.id, { locked: v })
          }}
        />
      </div>
    </div>
  )
}
