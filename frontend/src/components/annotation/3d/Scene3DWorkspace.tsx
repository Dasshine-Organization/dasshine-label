import { useRef, useEffect, useState, useCallback } from 'react'
import * as THREE from 'three'
import { v4 as uuid } from 'uuid'
import useAnnotationStore, { Box3D } from '../../../store/annotationStore'
import type { View3DType } from '../../../types/annotation3d'
import {
  generateDemoPointCloud,
  applyAnnotationColors,
  type PointCloudBounds,
  type PointCloudPayload,
} from '../../../utils/pointCloud3d'
import { loadPointCloudAsset } from '../../../utils/pointCloudLoader'
import { getTaskPointCloudUrl } from '../../../utils/annotationRoutes'
import {
  createDefaultOrbit,
  getDefaultOrbitRadius,
  updatePerspectiveFromOrbit,
  setViewPreset,
  fitOrthographicCamera,
  panOrbitTarget,
  zoomOrbit,
  rotateOrbit,
  groundPlaneIntersect,
  type OrbitState,
} from './orbitCamera'
import View3DControls from './View3DControls'

function hexToThreeColor(hex: string) {
  return parseInt(hex.replace('#', ''), 16)
}

type OrthoView = 'top' | 'front' | 'side'

const ORTHO_VIEWS: OrthoView[] = ['top', 'front', 'side']

interface OrthoViewportSlot {
  id: string
  label: string
  kind: OrthoView
}

const SIDE_VIEWPORTS: OrthoViewportSlot[] = [
  { id: 'top', label: '俯视图', kind: 'top' },
  { id: 'front', label: '正视图', kind: 'front' },
  { id: 'side', label: '侧视图', kind: 'side' },
]

interface Scene3DWorkspaceProps {
  taskId?: string
  pointCloudUrl?: string
}

export default function Scene3DWorkspace({ taskId, pointCloudUrl }: Scene3DWorkspaceProps) {
  const mainRef = useRef<HTMLDivElement>(null)
  const orthoRefs = useRef<Record<OrthoView, HTMLDivElement | null>>({ top: null, front: null, side: null })

  const sceneRef = useRef<THREE.Scene | null>(null)
  const pointsRef = useRef<THREE.Points | null>(null)
  const boundsBoxRef = useRef<THREE.LineSegments | null>(null)
  const boxMeshesRef = useRef<Map<string, THREE.Group>>(new Map())
  const mainRendererRef = useRef<THREE.WebGLRenderer | null>(null)
  const orthoRenderersRef = useRef<Partial<Record<OrthoView, THREE.WebGLRenderer>>>({})
  const mainCameraRef = useRef<THREE.PerspectiveCamera | null>(null)
  const orthoCamerasRef = useRef<Partial<Record<OrthoView, THREE.OrthographicCamera>>>({})
  const orbitRef = useRef<OrbitState | null>(null)
  const defaultOrbitRRef = useRef(0)
  const rafRef = useRef(0)

  const [cloud, setCloud] = useState<PointCloudPayload | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadingCloud, setLoadingCloud] = useState(true)
  const [activeView, setActiveView] = useState<View3DType>('perspective')
  const [isDrawing3D, setIsDrawing3D] = useState(false)
  const [drawStart, setDrawStart] = useState<{ x: number; z: number } | null>(null)
  const [pointSize, setPointSize] = useState(0.12)

  const store = useAnnotationStore()
  const { boxes3d, activeTool3d, selectedIds3d } = store

  const bounds = cloud?.bounds ?? null
  const baseColorsRef = useRef<Float32Array | null>(null)

  const interactionRef = useRef({
    isDragging: false,
    isPanning: false,
    lastPos: { x: 0, y: 0 },
  })

  const syncAllCameras = useCallback(() => {
    if (!bounds || !orbitRef.current) return
    const orbit = orbitRef.current
    const refR = defaultOrbitRRef.current || getDefaultOrbitRadius(bounds)

    if (mainCameraRef.current) {
      updatePerspectiveFromOrbit(mainCameraRef.current, orbit)
    }
    ORTHO_VIEWS.forEach((kind) => {
      const cam = orthoCamerasRef.current[kind]
      const el = orthoRefs.current[kind]
      if (cam && el) {
        fitOrthographicCamera(cam, kind, bounds, el.clientWidth / el.clientHeight, orbit, refR)
      }
    })
  }, [bounds])

  // ── load point cloud ──
  useEffect(() => {
    let cancelled = false
    const assetUrl = pointCloudUrl ?? (taskId ? getTaskPointCloudUrl(taskId) : undefined)

    async function load() {
      setLoadingCloud(true)
      setLoadError(null)
      try {
        const data = assetUrl
          ? await loadPointCloudAsset(assetUrl)
          : generateDemoPointCloud(20000)
        if (cancelled) return
        baseColorsRef.current = data.colors
        setCloud(data)
        orbitRef.current = createDefaultOrbit(data.bounds)
        defaultOrbitRRef.current = orbitRef.current.spherical.r
        const maxDim = Math.max(data.bounds.size.x, data.bounds.size.y, data.bounds.size.z)
        setPointSize(Math.max(0.05, Math.min(0.18, maxDim / 140)))
      } catch (e) {
        if (cancelled) return
        console.error(e)
        setLoadError(e instanceof Error ? e.message : '点云加载失败')
        const fallback = generateDemoPointCloud(20000)
        baseColorsRef.current = fallback.colors
        setCloud(fallback)
        orbitRef.current = createDefaultOrbit(fallback.bounds)
        defaultOrbitRRef.current = orbitRef.current!.spherical.r
      } finally {
        if (!cancelled) setLoadingCloud(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [taskId, pointCloudUrl])

  // ── build shared scene ──
  useEffect(() => {
    if (!cloud) return

    const scene = new THREE.Scene()
    sceneRef.current = scene

    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.BufferAttribute(cloud.positions, 3))
    geo.setAttribute('color', new THREE.BufferAttribute(cloud.colors.slice(), 3))
    const mat = new THREE.PointsMaterial({
      size: pointSize,
      vertexColors: true,
      sizeAttenuation: true,
    })
    const points = new THREE.Points(geo, mat)
    pointsRef.current = points
    scene.add(points)

    const { bounds: b } = cloud
    const boxGeo = new THREE.BoxGeometry(b.size.x, b.size.y, b.size.z)
    const edges = new THREE.EdgesGeometry(boxGeo)
    const boundsLine = new THREE.LineSegments(
      edges,
      new THREE.LineBasicMaterial({ color: 0x00d4ff, transparent: true, opacity: 0.35 }),
    )
    boundsLine.position.set(b.center.x, b.center.y, b.center.z)
    boundsBoxRef.current = boundsLine
    scene.add(boundsLine)

    const gridSize = Math.max(b.size.x, b.size.z) * 1.4
    const divisions = Math.min(80, Math.max(20, Math.round(gridSize / 2)))
    scene.add(new THREE.GridHelper(gridSize, divisions, 0x1e3a5f, 0x0d1f33))
    scene.add(new THREE.AxesHelper(Math.max(b.radius * 0.15, 1.5)))

    scene.add(new THREE.AmbientLight(0xffffff, 0.45))
    const dir = new THREE.DirectionalLight(0x00d4ff, 0.5)
    dir.position.set(b.center.x + 10, b.center.y + 20, b.center.z + 10)
    scene.add(dir)

    return () => {
      geo.dispose()
      mat.dispose()
      boxGeo.dispose()
      edges.dispose()
      scene.clear()
      sceneRef.current = null
      pointsRef.current = null
    }
  }, [cloud])

  useEffect(() => {
    if (pointsRef.current?.material) {
      ;(pointsRef.current.material as THREE.PointsMaterial).size = pointSize
    }
  }, [pointSize])

  // ── main + ortho renderers ──
  useEffect(() => {
    if (!cloud || !sceneRef.current || !mainRef.current) return
    const scene = sceneRef.current
    const b = cloud.bounds

    const mainEl = mainRef.current
    const w = mainEl.clientWidth
    const h = mainEl.clientHeight

    const mainRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    mainRenderer.setSize(w, h)
    mainRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    mainRenderer.setClearColor(0x0a0a0f, 1)
    mainEl.appendChild(mainRenderer.domElement)
    mainRendererRef.current = mainRenderer

    const mainCam = new THREE.PerspectiveCamera(55, w / h, 0.05, 2000)
    if (!orbitRef.current) orbitRef.current = createDefaultOrbit(b)
    updatePerspectiveFromOrbit(mainCam, orbitRef.current)
    mainCameraRef.current = mainCam

    ORTHO_VIEWS.forEach((kind) => {
      const el = orthoRefs.current[kind]
      if (!el) return
      const ow = el.clientWidth
      const oh = el.clientHeight
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
      renderer.setSize(ow, oh)
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      renderer.setClearColor(0x0a0a0f, 1)
      el.appendChild(renderer.domElement)
      orthoRenderersRef.current[kind] = renderer

      const cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 2000)
      const orbit = orbitRef.current!
      fitOrthographicCamera(cam, kind, b, ow / oh, orbit, defaultOrbitRRef.current)
      orthoCamerasRef.current[kind] = cam
    })

    const renderAll = () => {
      rafRef.current = requestAnimationFrame(renderAll)
      if (mainRendererRef.current && mainCameraRef.current) {
        mainRendererRef.current.render(scene, mainCameraRef.current)
      }
      ORTHO_VIEWS.forEach((kind) => {
        const r = orthoRenderersRef.current[kind]
        const c = orthoCamerasRef.current[kind]
        if (r && c) r.render(scene, c)
      })
    }
    renderAll()

    const roMain = new ResizeObserver(() => {
      const mw = mainEl.clientWidth
      const mh = mainEl.clientHeight
      mainRenderer.setSize(mw, mh)
      mainCam.aspect = mw / mh
      mainCam.updateProjectionMatrix()
    })
    roMain.observe(mainEl)

    const roOrthos: ResizeObserver[] = []
    ORTHO_VIEWS.forEach((kind) => {
      const el = orthoRefs.current[kind]
      if (!el) return
      const ro = new ResizeObserver(() => {
        const ow = el.clientWidth
        const oh = el.clientHeight
        const r = orthoRenderersRef.current[kind]
        const c = orthoCamerasRef.current[kind]
        if (r && c && orbitRef.current) {
          r.setSize(ow, oh)
          fitOrthographicCamera(
            c, kind, b, ow / oh, orbitRef.current, defaultOrbitRRef.current,
          )
        }
      })
      ro.observe(el)
      roOrthos.push(ro)
    })

    return () => {
      cancelAnimationFrame(rafRef.current)
      roMain.disconnect()
      roOrthos.forEach((ro) => ro.disconnect())
      mainRenderer.dispose()
      if (mainEl.contains(mainRenderer.domElement)) mainEl.removeChild(mainRenderer.domElement)
      ORTHO_VIEWS.forEach((kind) => {
        const r = orthoRenderersRef.current[kind]
        const el = orthoRefs.current[kind]
        if (r && el?.contains(r.domElement)) el.removeChild(r.domElement)
        r?.dispose()
      })
      mainRendererRef.current = null
      orthoRenderersRef.current = {}
      orthoCamerasRef.current = {}
    }
  }, [cloud])

  // ── recolor points by annotations ──
  useEffect(() => {
    if (!pointsRef.current || !cloud || !baseColorsRef.current) return
    const colored = applyAnnotationColors(cloud.positions, baseColorsRef.current, boxes3d)
    const attr = pointsRef.current.geometry.getAttribute('color') as THREE.BufferAttribute
    attr.array = colored
    attr.needsUpdate = true
  }, [boxes3d, cloud])

  // ── sync 3D boxes ──
  useEffect(() => {
    const scene = sceneRef.current
    if (!scene) return

    boxMeshesRef.current.forEach((mesh, id) => {
      if (!boxes3d.find((box) => box.id === id)) {
        scene.remove(mesh)
        boxMeshesRef.current.delete(id)
      }
    })

    boxes3d.forEach((box) => {
      if (!box.visible) return
      const isSelected = selectedIds3d.includes(box.id)
      const color = hexToThreeColor(box.color)

      if (boxMeshesRef.current.has(box.id)) {
        const group = boxMeshesRef.current.get(box.id)!
        group.position.set(box.center.x, box.center.y, box.center.z)
        group.scale.set(box.size.x, box.size.y, box.size.z)
        group.rotation.set(box.rotation.x, box.rotation.y, box.rotation.z)
        group.children.forEach((child) => {
          if (child instanceof THREE.LineSegments && child.material instanceof THREE.LineBasicMaterial) {
            child.material.color.setHex(color)
            child.material.opacity = isSelected ? 1 : 0.85
          }
        })
      } else {
        const group = new THREE.Group()
        const geo = new THREE.BoxGeometry(1, 1, 1)
        const wire = new THREE.LineSegments(
          new THREE.EdgesGeometry(geo),
          new THREE.LineBasicMaterial({ color, transparent: true, opacity: isSelected ? 1 : 0.85 }),
        )
        group.add(wire)
        const fill = new THREE.Mesh(
          geo,
          new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.1, side: THREE.DoubleSide }),
        )
        group.add(fill)
        group.position.set(box.center.x, box.center.y, box.center.z)
        group.scale.set(box.size.x, box.size.y, box.size.z)
        group.rotation.set(box.rotation.x, box.rotation.y, box.rotation.z)
        scene.add(group)
        boxMeshesRef.current.set(box.id, group)
      }
    })
  }, [boxes3d, selectedIds3d])

  const applyView = useCallback((view: View3DType | 'fit') => {
    if (!bounds || !orbitRef.current) return
    if (view === 'fit') {
      orbitRef.current = createDefaultOrbit(bounds)
      defaultOrbitRRef.current = orbitRef.current.spherical.r
      setActiveView('perspective')
    } else {
      orbitRef.current = setViewPreset(orbitRef.current, view, bounds)
      setActiveView(view)
    }
    syncAllCameras()
  }, [bounds, syncAllCameras])

  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    const tool = useAnnotationStore.getState().activeTool3d
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
    interactionRef.current.lastPos = { x: e.clientX, y: e.clientY }

    if (tool === 'orbit' || tool === 'select' || e.button === 1) {
      interactionRef.current.isDragging = true
    } else if (tool === 'pan' || e.altKey) {
      interactionRef.current.isPanning = true
    } else if (tool === 'box3d') {
      const cam = mainCameraRef.current
      const el = mainRef.current
      if (!cam || !el) return
      const pt = groundPlaneIntersect(cam, e.clientX, e.clientY, el.getBoundingClientRect(), bounds?.center.y ?? 0)
      if (pt) {
        setIsDrawing3D(true)
        setDrawStart(pt)
      }
    }
  }

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!orbitRef.current || !bounds) return
    const dx = e.clientX - interactionRef.current.lastPos.x
    const dy = e.clientY - interactionRef.current.lastPos.y
    interactionRef.current.lastPos = { x: e.clientX, y: e.clientY }

    if (interactionRef.current.isDragging) {
      rotateOrbit(orbitRef.current, dx, dy)
      if (mainCameraRef.current) updatePerspectiveFromOrbit(mainCameraRef.current, orbitRef.current)
      setActiveView('perspective')
    }
    if (interactionRef.current.isPanning && mainCameraRef.current) {
      panOrbitTarget(orbitRef.current, mainCameraRef.current, dx, dy)
      syncAllCameras()
    }
  }

  function onPointerUp(e: React.PointerEvent<HTMLDivElement>) {
    interactionRef.current.isDragging = false
    interactionRef.current.isPanning = false

    if (isDrawing3D && drawStart) {
      const cam = mainCameraRef.current
      const el = mainRef.current
      if (cam && el) {
        const pt = groundPlaneIntersect(cam, e.clientX, e.clientY, el.getBoundingClientRect(), bounds?.center.y ?? 0)
        if (pt) {
          const cx = (drawStart.x + pt.x) / 2
          const cz = (drawStart.z + pt.z) / 2
          const sx = Math.abs(pt.x - drawStart.x)
          const sz = Math.abs(pt.z - drawStart.z)
          if (sx > 0.3 && sz > 0.3) {
            const state = useAnnotationStore.getState()
            const color = state.labelClasses.find((l) => l.name === state.activeLabel)?.color ?? '#00d4ff'
            const box: Box3D = {
              id: uuid(),
              label: state.activeLabel,
              color,
              center: { x: cx, y: (bounds?.center.y ?? 0) + 0.75, z: cz },
              size: { x: sx, y: 1.5, z: sz },
              rotation: { x: 0, y: 0, z: 0 },
              visible: true,
              locked: false,
            }
            store.addBox3d(box)
          }
        }
      }
      setIsDrawing3D(false)
      setDrawStart(null)
    }
  }

  function onWheel(e: React.WheelEvent<HTMLDivElement>) {
    e.preventDefault()
    if (!orbitRef.current || !bounds) return
    zoomOrbit(orbitRef.current, e.deltaY, bounds)
    syncAllCameras()
  }

  const cursorMap: Record<string, string> = {
    select: 'default',
    box3d: 'crosshair',
    orbit: interactionRef.current.isDragging ? 'grabbing' : 'grab',
    pan: interactionRef.current.isPanning ? 'grabbing' : 'all-scroll',
  }

  if (!cloud || loadingCloud) {
    return (
      <div className="w-full h-full flex flex-col items-center justify-center bg-[#0a0a0f] gap-2">
        <div className="text-[#00d4ff] text-sm animate-pulse">正在加载路口点云场景…</div>
        {taskId === '1002' && <div className="text-[10px] text-white/30">urban_intersection_mini.pcd</div>}
        {loadError && <div className="text-[10px] text-amber-400/80 max-w-xs text-center">{loadError}（已回退演示点云）</div>}
      </div>
    )
  }

  return (
    <div className="w-full h-full flex bg-[#0a0a0f] overflow-hidden">
      {/* 主透视视口 */}
      <div
        className="flex-1 relative min-w-0"
        style={{ cursor: cursorMap[activeTool3d] }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onWheel={onWheel}
      >
        <div ref={mainRef} className="absolute inset-0" />

        <View3DControls activeView={activeView} onSelect={applyView} />

        {isDrawing3D && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 bg-[#00d4ff]/10 border border-[#00d4ff]/30 text-[#00d4ff] text-xs px-3 py-1 rounded pointer-events-none">
            松开鼠标完成 3D 框绘制
          </div>
        )}

        <BoundsOverlay
          bounds={cloud.bounds}
          pointCount={cloud.count}
          boxCount={boxes3d.filter((b) => b.visible).length}
          sceneName={cloud.sourceLabel?.includes('intersection') ? '城市路口' : undefined}
        />

        <div className="absolute bottom-3 left-3 text-[10px] text-white/25 space-y-0.5 pointer-events-none">
          <div>左键拖拽：旋转 · 滚轮：缩放 · Pan 工具 / Alt+拖拽：平移</div>
          <div>框内点云按标签颜色高亮显示</div>
        </div>

        <div className="absolute bottom-3 right-3 flex items-center gap-2 pointer-events-auto">
          <label className="text-[10px] text-white/40">点大小</label>
          <input
            type="range"
            min={0.04}
            max={0.35}
            step={0.01}
            value={pointSize}
            onChange={(e) => setPointSize(Number(e.target.value))}
            className="w-20 accent-[#00d4ff]"
          />
        </div>
      </div>

      {/* 正交副视图 */}
      <div className="w-[260px] shrink-0 flex flex-col border-l border-[#1e1e2e]">
        {SIDE_VIEWPORTS.map((vp) => (
          <div key={vp.id} className="flex-1 relative min-h-0 border-b border-[#1e1e2e] last:border-b-0">
            <div
              ref={(el) => { orthoRefs.current[vp.kind] = el }}
              className="absolute inset-0"
            />
            <div className="absolute top-1.5 left-2 text-[10px] font-medium text-[#00d4ff]/70 bg-black/40 px-1.5 py-0.5 rounded pointer-events-none">
              {vp.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function BoundsOverlay({
  bounds,
  pointCount,
  boxCount,
  sceneName,
}: {
  bounds: PointCloudBounds
  pointCount: number
  boxCount: number
  sceneName?: string
}) {
  return (
    <div className="absolute top-3 right-3 text-[10px] text-white/35 font-mono space-y-0.5 text-right pointer-events-none">
      {sceneName && <div className="text-[#a78bfa]/80">{sceneName}</div>}
      <div>{boxCount} 个 3D 框</div>
      <div>{(pointCount / 1000).toFixed(1)}k 点</div>
      <div className="text-[#00d4ff]/50">
        边界 [{bounds.min.x.toFixed(1)}, {bounds.min.y.toFixed(1)}, {bounds.min.z.toFixed(1)}]
        → [{bounds.max.x.toFixed(1)}, {bounds.max.y.toFixed(1)}, {bounds.max.z.toFixed(1)}]
      </div>
    </div>
  )
}
