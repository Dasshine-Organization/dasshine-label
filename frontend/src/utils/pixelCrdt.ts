/** 稀疏像素 CRDT：key = "x,y" → label。与 backend pixel_crdt 对齐。 */

export const PIXEL_CAP = 200_000

export function pixelKey(x: number, y: number): string {
  return `${Math.round(x)},${Math.round(y)}`
}

export function parsePixelKey(key: string): [number, number] {
  const [a, b] = key.split(',')
  return [Number(a), Number(b)]
}

export function paintDisk(
  pixels: Record<string, string>,
  cx: number,
  cy: number,
  radius: number,
  label: string,
  erase = false,
  cap = PIXEL_CAP,
): Record<string, string> {
  const next = { ...pixels }
  const r = Math.max(1, Math.round(radius))
  const r2 = r * r
  const x0 = Math.round(cx)
  const y0 = Math.round(cy)
  for (let dy = -r; dy <= r; dy++) {
    for (let dx = -r; dx <= r; dx++) {
      if (dx * dx + dy * dy > r2) continue
      const k = pixelKey(x0 + dx, y0 + dy)
      if (erase) delete next[k]
      else if (next[k] !== undefined || Object.keys(next).length < cap) next[k] = label
    }
  }
  return next
}
