import type { Box3D } from '../store/annotationStore'

export interface PointCloudBounds {
  min: { x: number; y: number; z: number }
  max: { x: number; y: number; z: number }
  center: { x: number; y: number; z: number }
  size: { x: number; y: number; z: number }
  radius: number
}

export interface PointCloudPayload {
  positions: Float32Array
  colors: Float32Array
  bounds: PointCloudBounds
  count: number
  sourceLabel?: string
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace('#', '')
  const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16)
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]
}

/** 从点坐标数组计算轴对齐包围盒 */
export function computePointCloudBounds(positions: Float32Array): PointCloudBounds {
  const n = positions.length / 3
  if (n === 0) {
    return {
      min: { x: -1, y: -1, z: -1 },
      max: { x: 1, y: 1, z: 1 },
      center: { x: 0, y: 0, z: 0 },
      size: { x: 2, y: 2, z: 2 },
      radius: 1,
    }
  }

  let minX = Infinity, minY = Infinity, minZ = Infinity
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity

  for (let i = 0; i < n; i++) {
    const x = positions[i * 3]
    const y = positions[i * 3 + 1]
    const z = positions[i * 3 + 2]
    if (x < minX) minX = x
    if (y < minY) minY = y
    if (z < minZ) minZ = z
    if (x > maxX) maxX = x
    if (y > maxY) maxY = y
    if (z > maxZ) maxZ = z
  }

  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  const cz = (minZ + maxZ) / 2
  const sx = maxX - minX
  const sy = maxY - minY
  const sz = maxZ - minZ

  return {
    min: { x: minX, y: minY, z: minZ },
    max: { x: maxX, y: maxY, z: maxZ },
    center: { x: cx, y: cy, z: cz },
    size: { x: sx, y: sy, z: sz },
    radius: Math.sqrt(sx * sx + sy * sy + sz * sz) / 2,
  }
}

/** 高度着色（未标注区域） */
export function buildHeightColors(positions: Float32Array, bounds: PointCloudBounds): Float32Array {
  const n = positions.length / 3
  const colors = new Float32Array(n * 3)
  const yRange = Math.max(bounds.size.y, 0.01)

  for (let i = 0; i < n; i++) {
    const y = positions[i * 3 + 1]
    const t = (y - bounds.min.y) / yRange
    colors[i * 3] = 0.15 + t * 0.25
    colors[i * 3 + 1] = 0.35 + t * 0.45
    colors[i * 3 + 2] = 0.75 - t * 0.35
  }
  return colors
}

function pointInBox3D(
  px: number, py: number, pz: number,
  box: Box3D,
): boolean {
  const dx = px - box.center.x
  const dy = py - box.center.y
  const dz = pz - box.center.z
  const { x: rx, y: ry, z: rz } = box.rotation

  const cosY = Math.cos(-ry)
  const sinY = Math.sin(-ry)
  let lx = dx * cosY - dz * sinY
  let ly = dy
  let lz = dx * sinY + dz * cosY

  const cosX = Math.cos(-rx)
  const sinX = Math.sin(-rx)
  const ly2 = ly * cosX - lz * sinX
  const lz2 = ly * sinX + lz * cosX
  ly = ly2
  lz = lz2

  const cosZ = Math.cos(-rz)
  const sinZ = Math.sin(-rz)
  const lx2 = lx * cosZ - ly * sinZ
  const ly3 = lx * sinZ + ly * cosZ
  lx = lx2
  ly = ly3

  const hx = box.size.x / 2
  const hy = box.size.y / 2
  const hz = box.size.z / 2
  return Math.abs(lx) <= hx && Math.abs(ly) <= hy && Math.abs(lz) <= hz
}

const HIGHLIGHT_STRENGTH = 0.92
const HIGHLIGHT_BRIGHTEN = 1.35
const OUTSIDE_DIM = 0.42

/** 将 3D 框内点着色为标签颜色（高亮），框外点云略微压暗以便对比 */
export function applyAnnotationColors(
  positions: Float32Array,
  baseColors: Float32Array,
  boxes: Box3D[],
): Float32Array {
  const n = positions.length / 3
  const colors = new Float32Array(baseColors.length)
  colors.set(baseColors)

  const visible = boxes.filter((b) => b.visible)
  if (visible.length === 0) return colors

  const insideMask = new Uint8Array(n)

  for (let i = 0; i < n; i++) {
    const px = positions[i * 3]
    const py = positions[i * 3 + 1]
    const pz = positions[i * 3 + 2]

    for (let j = visible.length - 1; j >= 0; j--) {
      const box = visible[j]
      if (pointInBox3D(px, py, pz, box)) {
        insideMask[i] = 1
        const [r, g, b] = hexToRgb(box.color)
        const bi = i * 3
        const br = baseColors[bi]
        const bg = baseColors[bi + 1]
        const bb = baseColors[bi + 2]
        colors[bi] = Math.min(1, (r * HIGHLIGHT_STRENGTH + br * (1 - HIGHLIGHT_STRENGTH)) * HIGHLIGHT_BRIGHTEN)
        colors[bi + 1] = Math.min(1, (g * HIGHLIGHT_STRENGTH + bg * (1 - HIGHLIGHT_STRENGTH)) * HIGHLIGHT_BRIGHTEN)
        colors[bi + 2] = Math.min(1, (b * HIGHLIGHT_STRENGTH + bb * (1 - HIGHLIGHT_STRENGTH)) * HIGHLIGHT_BRIGHTEN)
        break
      }
    }
  }

  for (let i = 0; i < n; i++) {
    if (!insideMask[i]) {
      const bi = i * 3
      colors[bi] *= OUTSIDE_DIM
      colors[bi + 1] *= OUTSIDE_DIM
      colors[bi + 2] *= OUTSIDE_DIM
    }
  }

  return colors
}

/** 模拟道路场景点云（开发/演示） */
export function generateDemoPointCloud(count = 18000): PointCloudPayload {
  const positions = new Float32Array(count * 3)

  for (let i = 0; i < count; i++) {
    const lane = Math.random() < 0.7
    const x = lane
      ? (Math.random() - 0.5) * 36
      : (Math.random() < 0.5 ? -1 : 1) * (18 + Math.random() * 8)
    const z = (Math.random() - 0.5) * 50
    const ground = Math.exp(-((x * x) / 80 + (z * z) / 200)) * 0.4
    const y = (Math.random() - 0.5) * 0.15 + ground + (Math.random() < 0.02 ? Math.random() * 2.5 : 0)

    positions[i * 3] = x
    positions[i * 3 + 1] = y
    positions[i * 3 + 2] = z
  }

  // 几簇“物体”点
  const clusters = [
    { x: 5, z: 3, spread: 2, h: 1.2 },
    { x: -3, z: 6, spread: 0.8, h: 1.6 },
    { x: 10, z: -5, spread: 3, h: 2.2 },
  ]
  for (let c = 0; c < 800; c++) {
    const cl = clusters[c % clusters.length]
    const i = count - 800 + c
    positions[i * 3] = cl.x + (Math.random() - 0.5) * cl.spread
    positions[i * 3 + 1] = Math.random() * cl.h
    positions[i * 3 + 2] = cl.z + (Math.random() - 0.5) * cl.spread
  }

  const bounds = computePointCloudBounds(positions)
  const colors = buildHeightColors(positions, bounds)
  return { positions, colors, bounds, count }
}
