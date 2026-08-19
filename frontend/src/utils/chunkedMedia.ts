/**
 * 大视频 / 大点云：优先走后端 Range / 分片 API。
 */

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) || 'http://localhost:8000/api/v1'

/** /uploads/… → 相对 UPLOAD_DIR 路径 */
export function uploadsRelativePath(url: string): string | null {
  try {
    const path = url.startsWith('http') ? new URL(url).pathname : url
    const m = path.match(/\/uploads\/(.+)$/)
    return m ? decodeURIComponent(m[1]) : null
  } catch {
    return null
  }
}

/** 浏览器原生 <video> 可用的 Range 友好 URL（同源 /uploads 或 media 代理） */
export function toRangedMediaUrl(url: string): string {
  if (!url) return url
  const rel = uploadsRelativePath(url)
  if (!rel) return url
  // 已在 /uploads 下时，依赖 StaticFiles + Nginx Range；也可走显式 media 代理
  if (url.includes('/uploads/')) return url
  return `${API_BASE}/media/file/${rel.split('/').map(encodeURIComponent).join('/')}`
}

export function pointcloudChunkUrl(relPath: string, chunk: number, pointsPerChunk = 20000): string {
  const q = new URLSearchParams({
    path: relPath,
    chunk: String(chunk),
    points_per_chunk: String(pointsPerChunk),
  })
  return `${API_BASE}/media/pointcloud?${q.toString()}`
}
