/**
 * 点云加载：优先 /media/pointcloud 分片；大 .bin 再走 HTTP Range 抽样。
 * 坐标统一 KITTI → Three.js 后平移到包围盒中心。
 */
import {
  computePointCloudBounds,
  buildHeightColors,
  type PointCloudPayload,
} from './pointCloud3d'
import { pointcloudChunkUrl, uploadsRelativePath } from './chunkedMedia'

const MAX_POINTS = 65000
const LARGE_BYTES = 2 * 1024 * 1024
const RANGE_CHUNK = 1024 * 1024

export type LoadPointCloudOptions = {
  onProgress?: (ratio: number) => void
  maxPoints?: number
}

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

async function loadViaBackendChunks(
  rel: string,
  opts?: LoadPointCloudOptions,
): Promise<PointCloudPayload | null> {
  const maxPoints = opts?.maxPoints ?? MAX_POINTS
  const positions: number[] = []
  let chunk = 0
  let totalChunks = 1
  let sourceLabel = rel

  while (chunk < totalChunks && positions.length / 3 < maxPoints) {
    const res = await fetch(pointcloudChunkUrl(rel, chunk))
    if (!res.ok) return null
    const data = (await res.json()) as {
      positions?: number[]
      total_chunks?: number
      total_points?: number
      source?: string
    }
    totalChunks = Math.max(1, data.total_chunks ?? 1)
    if (data.source) sourceLabel = data.source
    if (Array.isArray(data.positions)) positions.push(...data.positions)
    opts?.onProgress?.(Math.min(1, (chunk + 1) / totalChunks))
    chunk += 1
    if (!data.positions?.length) break
  }

  if (!positions.length) return null
  const payload = buildPayloadFromPositions(new Float32Array(positions))
  return { ...payload, sourceLabel }
}

async function loadBinWithRange(
  url: string,
  size: number,
  opts?: LoadPointCloudOptions,
): Promise<Float32Array> {
  const maxPoints = opts?.maxPoints ?? MAX_POINTS
  const total = Math.floor(size / 16)
  const step = total > maxPoints ? Math.ceil(total / maxPoints) : 1
  const out: number[] = []
  let offset = 0
  while (offset < size && out.length / 3 < maxPoints) {
    const end = Math.min(size - 1, offset + RANGE_CHUNK - 1)
    const res = await fetch(url, { headers: { Range: `bytes=${offset}-${end}` } })
    if (!(res.ok || res.status === 206)) {
      throw new Error(`点云 Range 失败 (${res.status})`)
    }
    const buf = await res.arrayBuffer()
    const floats = new Float32Array(buf)
    const baseIndex = Math.floor(offset / 16)
    const count = Math.floor(floats.length / 4)
    for (let i = 0; i < count && out.length / 3 < maxPoints; i++) {
      const global = baseIndex + i
      if (global % step !== 0) continue
      const o = i * 4
      const [sx, sy, sz] = kittiToSceneCoords(floats[o], floats[o + 1], floats[o + 2])
      out.push(sx, sy, sz)
    }
    offset = end + 1
    opts?.onProgress?.(Math.min(1, offset / size))
  }
  return new Float32Array(out)
}

async function loadFull(url: string, maxPoints: number): Promise<Float32Array> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`点云加载失败 (${res.status}): ${url}`)
  if (url.endsWith('.bin')) {
    return parseKittiBin(await res.arrayBuffer(), maxPoints)
  }
  return parsePcdAscii(await res.text(), maxPoints)
}

export async function loadPointCloudAsset(
  url: string,
  opts?: LoadPointCloudOptions,
): Promise<PointCloudPayload> {
  const maxPoints = opts?.maxPoints ?? MAX_POINTS
  const rel = uploadsRelativePath(url)
  if (rel) {
    const viaApi = await loadViaBackendChunks(rel, opts)
    if (viaApi) return viaApi
  }

  let size = 0
  try {
    const head = await fetch(url, { method: 'HEAD' })
    size = Number(head.headers.get('content-length') || 0)
  } catch {
    size = 0
  }

  let positions: Float32Array
  if (url.endsWith('.bin') && size > LARGE_BYTES) {
    positions = await loadBinWithRange(url, size, opts)
  } else {
    opts?.onProgress?.(0.2)
    positions = await loadFull(url, maxPoints)
    opts?.onProgress?.(1)
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
