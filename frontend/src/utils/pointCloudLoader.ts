import {
  computePointCloudBounds,
  buildHeightColors,
  type PointCloudPayload,
} from './pointCloud3d'

const MAX_POINTS = 65000

/** KITTI velodyne: x 前, y 左, z 上 → Three.js: y 上, x/z 地面 */
export function kittiToSceneCoords(x: number, y: number, z: number): [number, number, number] {
  return [x, z, -y]
}

export function parseKittiBin(buffer: ArrayBuffer, maxPoints = MAX_POINTS): Float32Array {
  const floats = new Float32Array(buffer)
  const stride = 4
  const total = Math.floor(floats.length / stride)
  const step = total > maxPoints ? Math.ceil(total / maxPoints) : 1
  const out: number[] = []

  for (let i = 0; i < total && out.length / 3 < maxPoints; i += step) {
    const o = i * stride
    const [sx, sy, sz] = kittiToSceneCoords(floats[o], floats[o + 1], floats[o + 2])
    out.push(sx, sy, sz)
  }
  return new Float32Array(out)
}

export function parsePcdAscii(text: string, maxPoints = MAX_POINTS): Float32Array {
  const lines = text.split(/\r?\n/)
  let dataStart = 0
  let fields: string[] = ['x', 'y', 'z']
  let pointsCount = 0

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (line.startsWith('FIELDS')) fields = line.slice(6).trim().split(/\s+/)
    if (line.startsWith('POINTS')) pointsCount = parseInt(line.slice(6).trim(), 10)
    if (line === 'DATA ascii') {
      dataStart = i + 1
      break
    }
  }

  const xi = fields.indexOf('x')
  const yi = fields.indexOf('y')
  const zi = fields.indexOf('z')
  if (xi < 0 || yi < 0 || zi < 0) throw new Error('PCD 缺少 x/y/z 字段')

  const out: number[] = []
  const step = pointsCount > maxPoints ? Math.ceil(pointsCount / maxPoints) : 1
  let read = 0

  for (let i = dataStart; i < lines.length && out.length / 3 < maxPoints; i++) {
    const line = lines[i].trim()
    if (!line || line.startsWith('#')) continue
    if (read % step === 0) {
      const p = line.split(/\s+/).map(Number)
      const [sx, sy, sz] = kittiToSceneCoords(p[xi], p[yi], p[zi])
      out.push(sx, sy, sz)
    }
    read++
  }
  return new Float32Array(out)
}

export async function loadPointCloudAsset(url: string): Promise<PointCloudPayload> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`点云加载失败 (${res.status}): ${url}`)

  let positions: Float32Array
  if (url.endsWith('.bin')) {
    positions = parseKittiBin(await res.arrayBuffer())
  } else {
    positions = parsePcdAscii(await res.text())
  }

  const payload = buildPayloadFromPositions(positions)
  return { ...payload, sourceLabel: url }
}

/** 将点云中心平移到原点附近，便于标注与相机适配 */
export function centerPositions(positions: Float32Array): Float32Array {
  const bounds = computePointCloudBounds(positions)
  const { center } = bounds
  const out = new Float32Array(positions.length)
  const n = positions.length / 3
  for (let i = 0; i < n; i++) {
    out[i * 3] = positions[i * 3] - center.x
    out[i * 3 + 1] = positions[i * 3 + 1] - center.y
    out[i * 3 + 2] = positions[i * 3 + 2] - center.z
  }
  return out
}

function positionsToPayload(positions: Float32Array): PointCloudPayload {
  const bounds = computePointCloudBounds(positions)
  const colors = buildHeightColors(positions, bounds)
  return { positions, colors, bounds, count: positions.length / 3 }
}

export function buildPayloadFromPositions(positions: Float32Array): PointCloudPayload {
  const centered = centerPositions(positions)
  return positionsToPayload(centered)
}
