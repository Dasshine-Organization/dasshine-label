import { Suspense, useMemo, useRef } from 'react'
import { Canvas } from '@react-three/fiber'
import { Grid, OrbitControls, Line } from '@react-three/drei'
import * as THREE from 'three'
import type { GraspPose, TrajectoryPoint } from '../../services/embodied'

type Props = {
  grasps: GraspPose[]
  trajectory: TrajectoryPoint[]
  frame: number
  selectedGraspId?: string | null
  onSelectGrasp?: (id: string | null) => void
  onMoveGrasp?: (id: string, position: { x: number; y: number; z: number }) => void
  onMoveTrajectory?: (frame: number, ee: TrajectoryPoint['ee']) => void
}

function rpyToEuler(roll: number, pitch: number, yaw: number) {
  return new THREE.Euler(roll, pitch, yaw, 'XYZ')
}

function GraspMarker({
  grasp,
  selected,
  onSelect,
  onMove,
}: {
  grasp: GraspPose
  selected: boolean
  onSelect: () => void
  onMove: (p: { x: number; y: number; z: number }) => void
}) {
  const dragging = useRef(false)
  const plane = useMemo(() => new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), [])
  const hit = useMemo(() => new THREE.Vector3(), [])

  return (
    <group
      position={[grasp.position.x, grasp.position.y, grasp.position.z]}
      rotation={rpyToEuler(grasp.orientation.roll, grasp.orientation.pitch, grasp.orientation.yaw)}
    >
      <mesh
        onClick={e => {
          e.stopPropagation()
          onSelect()
        }}
        onPointerDown={e => {
          e.stopPropagation()
          dragging.current = true
          ;(e.target as HTMLElement).setPointerCapture?.(e.pointerId)
          onSelect()
        }}
        onPointerUp={() => {
          dragging.current = false
        }}
        onPointerMove={e => {
          if (!dragging.current) return
          e.stopPropagation()
          const ray = e.ray
          if (ray.intersectPlane(plane, hit)) {
            onMove({ x: hit.x, y: grasp.position.y, z: hit.z })
          }
        }}
      >
        <boxGeometry args={[grasp.width || 0.08, 0.04, 0.06]} />
        <meshStandardMaterial
          color={selected ? '#f97316' : '#38bdf8'}
          transparent
          opacity={0.85}
        />
      </mesh>
      <axesHelper args={[0.12]} />
    </group>
  )
}

function TrajectoryPath({
  points,
  frame,
  onMove,
}: {
  points: TrajectoryPoint[]
  frame: number
  onMove: (frame: number, ee: TrajectoryPoint['ee']) => void
}) {
  const sorted = useMemo(
    () => [...points].sort((a, b) => a.frame - b.frame),
    [points],
  )
  const linePts = useMemo(
    () => sorted.map(p => new THREE.Vector3(p.ee.x, p.ee.y, p.ee.z)),
    [sorted],
  )
  const current = sorted.find(p => p.frame === frame) || sorted[sorted.length - 1]
  const dragging = useRef(false)
  const plane = useMemo(() => new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), [])
  const hit = useMemo(() => new THREE.Vector3(), [])

  return (
    <group>
      {linePts.length >= 2 && (
        <Line points={linePts} color="#a78bfa" lineWidth={2} />
      )}
      {sorted.map(p => (
        <mesh key={p.frame} position={[p.ee.x, p.ee.y, p.ee.z]}>
          <sphereGeometry args={[0.018, 12, 12]} />
          <meshStandardMaterial color={p.frame === frame ? '#fbbf24' : '#7c3aed'} />
        </mesh>
      ))}
      {current && (
        <mesh
          position={[current.ee.x, current.ee.y, current.ee.z]}
          onPointerDown={e => {
            e.stopPropagation()
            dragging.current = true
          }}
          onPointerUp={() => {
            dragging.current = false
          }}
          onPointerMove={e => {
            if (!dragging.current) return
            e.stopPropagation()
            if (e.ray.intersectPlane(plane, hit)) {
              onMove(current.frame, {
                ...current.ee,
                x: hit.x,
                z: hit.z,
              })
            }
          }}
        >
          <sphereGeometry args={[0.03, 16, 16]} />
          <meshStandardMaterial color="#fbbf24" wireframe />
        </mesh>
      )}
    </group>
  )
}

function SceneContent(props: Props) {
  const {
    grasps,
    trajectory,
    frame,
    selectedGraspId,
    onSelectGrasp,
    onMoveGrasp,
    onMoveTrajectory,
  } = props
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
      <TrajectoryPath
        points={trajectory}
        frame={frame}
        onMove={(f, ee) => onMoveTrajectory?.(f, ee)}
      />
      {grasps.map(g => (
        <GraspMarker
          key={g.id}
          grasp={g}
          selected={selectedGraspId === g.id}
          onSelect={() => onSelectGrasp?.(g.id)}
          onMove={pos => onMoveGrasp?.(g.id, pos)}
        />
      ))}
      <OrbitControls makeDefault enableDamping dampingFactor={0.12} />
    </>
  )
}

export default function EmbodiedPose3DViewer(props: Props) {
  return (
    <div className="w-full h-[240px] rounded-lg overflow-hidden border border-[#1e1e2e] bg-[#0a0a0f]">
      <Canvas camera={{ position: [0.8, 0.7, 0.9], fov: 45 }} onPointerMissed={() => props.onSelectGrasp?.(null)}>
        <Suspense fallback={null}>
          <SceneContent {...props} />
        </Suspense>
      </Canvas>
      <div className="px-2 py-1 text-[10px] text-white/30 border-t border-[#1e1e2e] bg-[#0a0a0f]">
        拖拽抓取块 / 当前帧轨迹点（XZ 平面）；滚轮缩放 · 右键平移
      </div>
    </div>
  )
}
