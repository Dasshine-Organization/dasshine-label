import * as THREE from 'three'
import type { PerspectiveCamera, OrthographicCamera } from 'three'
import type { PointCloudBounds } from '../../../utils/pointCloud3d'
import type { View3DType } from '../../../types/annotation3d'

export interface OrbitState {
  spherical: { r: number; theta: number; phi: number }
  target: { x: number; y: number; z: number }
}

export function getDefaultOrbitRadius(bounds: PointCloudBounds): number {
  return Math.max(bounds.radius * 2.2, 8)
}

export function createDefaultOrbit(bounds: PointCloudBounds): OrbitState {
  const r = getDefaultOrbitRadius(bounds)
  return {
    spherical: { r, theta: Math.PI / 4, phi: Math.PI / 3 },
    target: { ...bounds.center },
  }
}

export function updatePerspectiveFromOrbit(
  camera: PerspectiveCamera,
  orbit: OrbitState,
): void {
  const { r, theta, phi } = orbit.spherical
  const { x: tx, y: ty, z: tz } = orbit.target
  camera.position.set(
    tx + r * Math.sin(phi) * Math.sin(theta),
    ty + r * Math.cos(phi),
    tz + r * Math.sin(phi) * Math.cos(theta),
  )
  camera.lookAt(tx, ty, tz)
}

export function setViewPreset(
  orbit: OrbitState,
  view: View3DType,
  bounds: PointCloudBounds,
): OrbitState {
  const r = Math.max(bounds.radius * 2.2, 8)
  const t = { ...bounds.center }
  const next = { ...orbit, target: t, spherical: { ...orbit.spherical, r } }

  switch (view) {
    case 'top':
      next.spherical = { r, theta: 0, phi: 0.12 }
      break
    case 'front':
      next.spherical = { r, theta: 0, phi: Math.PI / 2 }
      break
    case 'side':
      next.spherical = { r, theta: Math.PI / 2, phi: Math.PI / 2 }
      break
    case 'perspective':
    default:
      next.spherical = { r, theta: Math.PI / 4, phi: Math.PI / 3 }
      break
  }
  return next
}

/** 正交副视图：随主视 orbit 的缩放/平移同步 */
export function fitOrthographicCamera(
  camera: OrthographicCamera,
  view: 'top' | 'front' | 'side',
  bounds: PointCloudBounds,
  aspect: number,
  orbit?: OrbitState,
  defaultOrbitR?: number,
): void {
  const { center, size } = bounds
  const pad = 1.25
  const baseHalf = Math.max(size.x, size.y, size.z) * pad * 0.55

  const refR = defaultOrbitR ?? getDefaultOrbitRadius(bounds)
  const curR = orbit?.spherical.r ?? refR
  const zoomScale = curR / refR
  const half = baseHalf * zoomScale

  let halfW = half
  let halfH = half
  if (aspect > 1) halfW = half * aspect
  else halfH = half / aspect

  camera.left = -halfW
  camera.right = halfW
  camera.top = halfH
  camera.bottom = -halfH
  camera.near = 0.1
  camera.far = Math.max(size.x, size.y, size.z) * 20 + 100
  camera.updateProjectionMatrix()

  const target = orbit?.target ?? center
  const dist = Math.max(bounds.radius * 3, 20) * zoomScale
  switch (view) {
    case 'top':
      camera.position.set(target.x, target.y + dist, target.z)
      camera.up.set(0, 0, -1)
      break
    case 'front':
      camera.position.set(target.x, target.y, target.z + dist)
      camera.up.set(0, 1, 0)
      break
    case 'side':
      camera.position.set(target.x + dist, target.y, target.z)
      camera.up.set(0, 1, 0)
      break
  }
  camera.lookAt(target.x, target.y, target.z)
}

export function panOrbitTarget(
  orbit: OrbitState,
  camera: PerspectiveCamera,
  dx: number,
  dy: number,
): void {
  const right = new THREE.Vector3()
  const up = new THREE.Vector3()
  camera.getWorldDirection(right)
  right.cross(camera.up).normalize()
  up.copy(camera.up)
  const scale = orbit.spherical.r * 0.002
  orbit.target.x -= right.x * dx * scale - up.x * dy * scale
  orbit.target.y -= right.y * dx * scale - up.y * dy * scale
  orbit.target.z -= right.z * dx * scale - up.z * dy * scale
}

export function zoomOrbit(orbit: OrbitState, delta: number, bounds: PointCloudBounds): void {
  const minR = Math.max(bounds.radius * 0.15, 1)
  const maxR = Math.max(bounds.radius * 12, 200)
  const factor = delta > 0 ? 1.1 : 0.9
  orbit.spherical.r = Math.max(minR, Math.min(maxR, orbit.spherical.r * factor))
}

export function rotateOrbit(orbit: OrbitState, dx: number, dy: number): void {
  orbit.spherical.theta -= dx * 0.01
  orbit.spherical.phi = Math.max(0.08, Math.min(Math.PI - 0.08, orbit.spherical.phi + dy * 0.01))
}

export function groundPlaneIntersect(
  camera: PerspectiveCamera,
  clientX: number,
  clientY: number,
  rect: DOMRect,
  planeY = 0,
): { x: number; z: number } | null {
  const ndc = new THREE.Vector2(
    ((clientX - rect.left) / rect.width) * 2 - 1,
    -((clientY - rect.top) / rect.height) * 2 + 1,
  )
  const raycaster = new THREE.Raycaster()
  raycaster.setFromCamera(ndc, camera)
  const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -planeY)
  const target = new THREE.Vector3()
  const hit = raycaster.ray.intersectPlane(plane, target)
  if (!hit) return null
  return { x: target.x, z: target.z }
}
