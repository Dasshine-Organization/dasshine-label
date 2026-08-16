import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { Grid, OrbitControls, Line, TransformControls } from '@react-three/drei'
import * as THREE from 'three'
import type { GraspPose, TrajectoryPoint } from '../../services/embodied'

type Props = {
  grasps: GraspPose[]
  trajectory: TrajectoryPoint[]
  frame: number
  selectedGraspId?: string | null
  onSelectGrasp?: (id: string | null) => void
  onMoveGrasp?: (
    id: string,
    position: { x: number; y: number; z: number },
    orientation?: { roll: number; pitch: number; yaw: number },
  ) => void
  onMoveTrajectory?: (frame: number, ee: TrajectoryPoint['ee']) => void
}

function eulerToRpy(e: THREE.Euler) {
  return { roll: e.x, pitch: e.y, yaw: e.z }
}

function EditableObject({
  selected,
  mode,
  position,
  rotation,
  onSelect,
  onChange,
  children,
}: {
  selected: boolean
  mode: 'translate' | 'rotate'
  position: [number, number, number]
  rotation: [number, number, number]
  onSelect: () => void
  onChange: (pos: THREE.Vector3, rot: THREE.Euler) => void
  children: React.ReactNode
}) {
  const ref = useRef<THREE.Group>(null)
  const [, bump] = useState(0)

  useEffect(() => {
    if (!ref.current) return
    ref.current.position.set(...position)
    ref.current.rotation.set(...rotation, 'XYZ')
  }, [position, rotation])

  useEffect(() => {
    if (selected) bump(n => n + 1)
  }, [selected])

  return (
    <>
      <group
        ref={ref}
        onClick={e => {
          e.stopPropagation()
          onSelect()
        }}
      >
        {children}
      </group>
      {selected && ref.current && (
        <TransformControls
          object={ref.current}
          mode={mode}
          size={0.55}
          onObjectChange={() => {
            const g = ref.current
            if (!g) return
            onChange(g.position.clone(), g.rotation.clone())
          }}
        />
      )}
    </>
  )
}

function SceneContent(
  props: Props & {
    mode: 'translate' | 'rotate'
    selectTarget: 'grasp' | 'traj' | null
    onSelectTarget: (t: 'grasp' | 'traj' | null) => void
  },
) {
  const {
    grasps,
    trajectory,
    frame,
    selectedGraspId,
    onSelectGrasp,
    onMoveGrasp,
    onMoveTrajectory,
    mode,
    selectTarget,
    onSelectTarget,
  } = props

  const sorted = useMemo(
    () => [...trajectory].sort((a, b) => a.frame - b.frame),
    [trajectory],
  )
  const linePts = useMemo(
    () => sorted.map(p => new THREE.Vector3(p.ee.x, p.ee.y, p.ee.z)),
    [sorted],
  )
  const current = sorted.find(p => p.frame === frame)

  return (
    <>
      <ambientLight intensity={0.55} />
      <directionalLight position={[2, 4, 2]} intensity={0.85} />
      <Grid
        args={[4, 4]}
        cellSize={0.1}
        sectionSize={0.5}
        fadeDistance={6}
        cellColor="#333"
        sectionColor="#555"
      />
      <axesHelper args={[0.4]} />
      {linePts.length >= 2 && <Line points={linePts} color="#a78bfa" lineWidth={2} />}
      {sorted.map(p => (
        <mesh key={p.frame} position={[p.ee.x, p.ee.y, p.ee.z]}>
          <sphereGeometry args={[0.018, 12, 12]} />
          <meshStandardMaterial color={p.frame === frame ? '#fbbf24' : '#7c3aed'} />
        </mesh>
      ))}
      {current && (
        <EditableObject
          selected={selectTarget === 'traj'}
          mode={mode}
          position={[current.ee.x, current.ee.y, current.ee.z]}
          rotation={[current.ee.roll, current.ee.pitch, current.ee.yaw]}
          onSelect={() => {
            onSelectTarget('traj')
            onSelectGrasp?.(null)
          }}
          onChange={(pos, rot) => {
            const rpy = eulerToRpy(rot)
            onMoveTrajectory?.(current.frame, {
              x: pos.x,
              y: pos.y,
              z: pos.z,
              roll: rpy.roll,
              pitch: rpy.pitch,
              yaw: rpy.yaw,
            })
          }}
        >
          <mesh>
            <sphereGeometry args={[0.032, 16, 16]} />
            <meshStandardMaterial
              color="#fbbf24"
              wireframe={selectTarget !== 'traj'}
            />
          </mesh>
        </EditableObject>
      )}
      {grasps.map(g => (
        <EditableObject
          key={g.id}
          selected={selectTarget === 'grasp' && selectedGraspId === g.id}
          mode={mode}
          position={[g.position.x, g.position.y, g.position.z]}
          rotation={[g.orientation.roll, g.orientation.pitch, g.orientation.yaw]}
          onSelect={() => {
            onSelectTarget('grasp')
            onSelectGrasp?.(g.id)
          }}
          onChange={(pos, rot) => {
            onMoveGrasp?.(
              g.id,
              { x: pos.x, y: pos.y, z: pos.z },
              eulerToRpy(rot),
            )
          }}
        >
          <mesh>
            <boxGeometry args={[g.width || 0.08, 0.04, 0.06]} />
            <meshStandardMaterial
              color={
                selectTarget === 'grasp' && selectedGraspId === g.id ? '#f97316' : '#38bdf8'
              }
              transparent
              opacity={0.85}
            />
          </mesh>
          <axesHelper args={[0.12]} />
        </EditableObject>
      ))}
      <OrbitControls makeDefault enableDamping dampingFactor={0.12} />
    </>
  )
}

export default function EmbodiedPose3DViewer(props: Props) {
  const [mode, setMode] = useState<'translate' | 'rotate'>('translate')
  const [selectTarget, setSelectTarget] = useState<'grasp' | 'traj' | null>(null)

  return (
    <div className="w-full rounded-lg overflow-hidden border border-[#1e1e2e] bg-[#0a0a0f]">
      <div className="flex items-center gap-2 px-2 py-1 border-b border-[#1e1e2e] text-[10px]">
        <button
          type="button"
          onClick={() => setMode('translate')}
          className={`px-2 py-0.5 rounded border ${
            mode === 'translate'
              ? 'border-[#f97316]/50 text-[#f97316]'
              : 'border-[#1e1e2e] text-white/40'
          }`}
        >
          平移
        </button>
        <button
          type="button"
          onClick={() => setMode('rotate')}
          className={`px-2 py-0.5 rounded border ${
            mode === 'rotate'
              ? 'border-[#f97316]/50 text-[#f97316]'
              : 'border-[#1e1e2e] text-white/40'
          }`}
        >
          旋转
        </button>
        <span className="text-white/25 ml-auto">6DoF · TransformControls</span>
      </div>
      <div className="w-full h-[240px]">
        <Canvas
          camera={{ position: [0.8, 0.7, 0.9], fov: 45 }}
          onPointerMissed={() => {
            setSelectTarget(null)
            props.onSelectGrasp?.(null)
          }}
        >
          <Suspense fallback={null}>
            <SceneContent
              {...props}
              mode={mode}
              selectTarget={selectTarget}
              onSelectTarget={setSelectTarget}
            />
          </Suspense>
        </Canvas>
      </div>
      <div className="px-2 py-1 text-[10px] text-white/30 border-t border-[#1e1e2e]">
        选中抓取或当前帧轨迹点后拖动手柄；与数值字段双向同步
      </div>
    </div>
  )
}
