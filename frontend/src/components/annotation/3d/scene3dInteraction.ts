import * as THREE from 'three'
import type { Box3D } from '../../../store/annotationStore'
import {
  axisWorldDirection,
  handleWorldPosition,
  moveBox,
  parseHandleId,
  projectDeltaOnAxis,
  rayPlaneIntersect,
  resizeBoxOnAxis,
  type BoxAxis,
} from '../../../utils/box3dEdit'

export type PickHit =
  | { kind: 'handle'; boxId: string; handleId: string }
  | { kind: 'box'; boxId: string }
  | null

export type EditDrag =
  | {
      kind: 'resize'
      boxId: string
      handleId: string
      axis: BoxAxis
      sign: 1 | -1
      startBox: Box3D
      startHit: THREE.Vector3
      axisDir: THREE.Vector3
      planePoint: THREE.Vector3
    }
  | {
      kind: 'move'
      boxId: string
      startBox: Box3D
      startHit: THREE.Vector3
    }

const HANDLE_COLORS: Record<string, number> = {
  'x+': 0xff6b6b,
  'x-': 0xff6b6b,
  'y+': 0x69db7c,
  'y-': 0x69db7c,
  'z+': 0x74c0fc,
  'z-': 0x74c0fc,
}

export function createHandleMesh(handleId: string, radius: number): THREE.Mesh {
  const geo = new THREE.SphereGeometry(radius, 10, 10)
  const mat = new THREE.MeshBasicMaterial({
    color: HANDLE_COLORS[handleId] ?? 0xffffff,
    depthTest: false,
  })
  const mesh = new THREE.Mesh(geo, mat)
  mesh.userData = { type: 'handle', handleId }
  mesh.renderOrder = 10
  return mesh
}

export function syncHandleGroup(
  group: THREE.Group,
  box: Box3D,
  radius: number,
  existing: Map<string, THREE.Mesh>,
) {
  const ids = ['x+', 'x-', 'y+', 'y-', 'z+', 'z-'] as const
  for (const hid of ids) {
    const parsed = parseHandleId(hid)!
    const pos = handleWorldPosition(box, parsed.axis, parsed.sign)
    let mesh = existing.get(hid)
    if (!mesh) {
      mesh = createHandleMesh(hid, radius)
      group.add(mesh)
      existing.set(hid, mesh)
    }
    mesh.position.copy(pos)
    mesh.scale.setScalar(1)
  }
}

export function raycastScene(
  camera: THREE.Camera,
  clientX: number,
  clientY: number,
  rect: DOMRect,
  handleMeshes: THREE.Object3D[],
  boxGroups: THREE.Object3D[],
): PickHit {
  const ndc = new THREE.Vector2(
    ((clientX - rect.left) / rect.width) * 2 - 1,
    -((clientY - rect.top) / rect.height) * 2 + 1,
  )
  const raycaster = new THREE.Raycaster()
  raycaster.setFromCamera(ndc, camera)

  const hHits = raycaster.intersectObjects(handleMeshes, false)
  if (hHits[0]?.object.userData.type === 'handle') {
    const handleId = hHits[0].object.userData.handleId as string
    const boxId = hHits[0].object.parent?.userData.boxId as string
    if (boxId) return { kind: 'handle', boxId, handleId }
  }

  const bHits = raycaster.intersectObjects(boxGroups, true)
  for (const hit of bHits) {
    let obj: THREE.Object3D | null = hit.object
    while (obj) {
      if (obj.userData.type === 'box' && obj.userData.boxId) {
        return { kind: 'box', boxId: obj.userData.boxId as string }
      }
      obj = obj.parent
    }
  }
  return null
}

export function applyEditDrag(
  drag: EditDrag,
  box: Box3D,
  ray: THREE.Ray,
  hit: THREE.Vector3,
): Partial<Box3D> | null {
  if (drag.kind === 'move') {
    const delta = hit.clone().sub(drag.startHit)
    return moveBox(drag.startBox, delta)
  }
  const current = rayPlaneIntersect(ray, drag.planePoint, drag.axisDir)
  if (!current) return null
  const worldDelta = current.clone().sub(drag.startHit)
  const deltaLocal = projectDeltaOnAxis(worldDelta, drag.axisDir) * drag.sign
  return resizeBoxOnAxis(drag.startBox, drag.axis, drag.sign, deltaLocal)
}

export function makeRay(
  camera: THREE.Camera,
  clientX: number,
  clientY: number,
  rect: DOMRect,
): THREE.Ray {
  const ndc = new THREE.Vector2(
    ((clientX - rect.left) / rect.width) * 2 - 1,
    -((clientY - rect.top) / rect.height) * 2 + 1,
  )
  const raycaster = new THREE.Raycaster()
  raycaster.setFromCamera(ndc, camera)
  return raycaster.ray
}

/** 绘制中的预览框（虚线线框 + 半透明填充） */
export function createDrawPreviewGroup(colorHex: string): THREE.Group {
  const color = parseInt(colorHex.replace('#', ''), 16)
  const group = new THREE.Group()
  group.userData = { type: 'drawPreview' }

  const wire = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1)),
    new THREE.LineDashedMaterial({
      color,
      dashSize: 0.35,
      gapSize: 0.2,
      transparent: true,
      opacity: 1,
      depthTest: false,
    }),
  )
  wire.computeLineDistances()
  wire.renderOrder = 20
  group.add(wire)

  const fill = new THREE.Mesh(
    new THREE.BoxGeometry(1, 1, 1),
    new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.15,
      side: THREE.DoubleSide,
      depthWrite: false,
    }),
  )
  fill.renderOrder = 19
  group.add(fill)

  const cornerGeo = new THREE.SphereGeometry(0.15, 8, 8)
  const corner = new THREE.Mesh(
    cornerGeo,
    new THREE.MeshBasicMaterial({ color, depthTest: false }),
  )
  corner.userData = { type: 'drawStartMarker' }
  corner.renderOrder = 21
  group.add(corner)

  return group
}

export function applyBoxToPreviewGroup(group: THREE.Group, box: Box3D, start: { x: number; z: number }) {
  group.position.set(box.center.x, box.center.y, box.center.z)
  group.scale.set(box.size.x, box.size.y, box.size.z)
  group.rotation.set(box.rotation.x, box.rotation.y, box.rotation.z)

  const marker = group.children.find((c) => c.userData.type === 'drawStartMarker') as THREE.Mesh | undefined
  if (marker) {
    const m = 0.22
    marker.position.set(
      (start.x - box.center.x) / box.size.x,
      -0.5 + 0.04 / box.size.y,
      (start.z - box.center.z) / box.size.z,
    )
    marker.scale.set(m / box.size.x, m / box.size.y, m / box.size.z)
  }

  const color = parseInt(box.color.replace('#', ''), 16)
  group.traverse((child) => {
    if (child instanceof THREE.LineSegments && child.material instanceof THREE.LineDashedMaterial) {
      child.material.color.setHex(color)
      child.computeLineDistances()
    }
    if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshBasicMaterial) {
      child.material.color.setHex(color)
    }
  })
}

export function disposeDrawPreviewGroup(group: THREE.Group) {
  group.traverse((c) => {
    if (c instanceof THREE.Mesh || c instanceof THREE.LineSegments) {
      c.geometry?.dispose()
      const m = c.material
      if (Array.isArray(m)) m.forEach((mat) => mat.dispose())
      else m?.dispose()
    }
  })
}

export function groundHitFromRay(ray: THREE.Ray, groundY: number): THREE.Vector3 | null {
  const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -groundY)
  const t = ray.distanceToPlane(plane)
  if (t === null) return null
  return ray.origin.clone().add(ray.direction.clone().multiplyScalar(t))
}
