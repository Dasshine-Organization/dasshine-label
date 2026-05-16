import * as THREE from 'three'
import type { Box3D } from '../store/annotationStore'
import type { PointCloudBounds } from './pointCloud3d'

export type BoxAxis = 'x' | 'y' | 'z'
export type BoxHandleId = `${BoxAxis}${'+' | '-'}`

const MIN_SIZE = 0.25

export function parseHandleId(id: string): { axis: BoxAxis; sign: 1 | -1 } | null {
  if (id === 'x+' || id === 'x-') return { axis: 'x', sign: id === 'x+' ? 1 : -1 }
  if (id === 'y+' || id === 'y-') return { axis: 'y', sign: id === 'y+' ? 1 : -1 }
  if (id === 'z+' || id === 'z-') return { axis: 'z', sign: id === 'z+' ? 1 : -1 }
  return null
}

export function boxEuler(box: Box3D): THREE.Euler {
  return new THREE.Euler(box.rotation.x, box.rotation.y, box.rotation.z, 'XYZ')
}

/** 局部轴端点 → 世界坐标 */
export function handleWorldPosition(box: Box3D, axis: BoxAxis, sign: 1 | -1): THREE.Vector3 {
  const local = new THREE.Vector3()
  local[axis] = sign * box.size[axis] * 0.5
  local.applyEuler(boxEuler(box))
  return local.add(new THREE.Vector3(box.center.x, box.center.y, box.center.z))
}

export const BOX_HANDLE_IDS: BoxHandleId[] = ['x+', 'x-', 'y+', 'y-', 'z+', 'z-']

/** 沿局部轴拉伸一面，更新 size 与 center */
export function resizeBoxOnAxis(
  box: Box3D,
  axis: BoxAxis,
  sign: 1 | -1,
  deltaLocal: number,
): Pick<Box3D, 'size' | 'center'> {
  const nextSize = { ...box.size }
  nextSize[axis] = Math.max(MIN_SIZE, box.size[axis] + deltaLocal)
  const applied = nextSize[axis] - box.size[axis]
  if (applied === 0) return { size: box.size, center: box.center }

  const shift = new THREE.Vector3()
  shift[axis] = sign * applied * 0.5
  shift.applyEuler(boxEuler(box))

  return {
    size: nextSize,
    center: {
      x: box.center.x + shift.x,
      y: box.center.y + shift.y,
      z: box.center.z + shift.z,
    },
  }
}

/** 世界空间平移 */
export function moveBox(box: Box3D, delta: THREE.Vector3): Pick<Box3D, 'center'> {
  return {
    center: {
      x: box.center.x + delta.x,
      y: box.center.y + delta.y,
      z: box.center.z + delta.z,
    },
  }
}

/** 射线与垂直于局部轴的平面求交，用于拖拽 */
export function rayPlaneIntersect(
  ray: THREE.Ray,
  planePoint: THREE.Vector3,
  planeNormal: THREE.Vector3,
): THREE.Vector3 | null {
  const denom = planeNormal.dot(ray.direction)
  if (Math.abs(denom) < 1e-8) return null
  const t = planePoint.clone().sub(ray.origin).dot(planeNormal) / denom
  if (t < 0) return null
  return ray.origin.clone().add(ray.direction.clone().multiplyScalar(t))
}

/** 局部轴在世界空间的方向 */
export function axisWorldDirection(box: Box3D, axis: BoxAxis): THREE.Vector3 {
  const dir = new THREE.Vector3()
  dir[axis] = 1
  dir.applyEuler(boxEuler(box))
  return dir.normalize()
}

/** 将世界位移投影到局部轴，得到标量 delta */
export function projectDeltaOnAxis(
  worldDelta: THREE.Vector3,
  axisDir: THREE.Vector3,
): number {
  return worldDelta.dot(axisDir)
}

export function defaultBoxHeight(bounds: { min: { y: number }; size: { y: number } }): number {
  return Math.max(1.0, Math.min(3.5, bounds.size.y * 0.12))
}

/** 绘制 3D 框时射线与地面的交平面高度 */
export function drawGroundY(bounds: PointCloudBounds): number {
  return bounds.min.y + Math.max(0.05, bounds.size.y * 0.02)
}

const MIN_DRAW_SIZE = 0.08

/** 由地面矩形对角点计算 3D 框（绘制预览与最终提交共用） */
export function boxFromGroundDrag(
  start: { x: number; z: number },
  end: { x: number; z: number },
  bounds: PointCloudBounds,
  label: string,
  color: string,
  id?: string,
): Box3D {
  const sx = Math.max(Math.abs(end.x - start.x), MIN_DRAW_SIZE)
  const sz = Math.max(Math.abs(end.z - start.z), MIN_DRAW_SIZE)
  const cx = (start.x + end.x) / 2
  const cz = (start.z + end.z) / 2
  const hy = defaultBoxHeight(bounds)
  return {
    id: id ?? '__preview__',
    label,
    color,
    center: { x: cx, y: bounds.min.y + hy / 2, z: cz },
    size: { x: sx, y: hy, z: sz },
    rotation: { x: 0, y: 0, z: 0 },
    visible: true,
    locked: false,
  }
}
