/**
 * 生成迷你城市路口点云（ASCII PCD）
 * 结构参考 KITTI Object Detection Velodyne 道路场景（x 前 / y 左 / z 上）
 * 运行: node scripts/generate-intersection-sample.mjs
 */
import { writeFileSync, mkdirSync } from 'fs'
import { dirname, join } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const OUT = join(__dirname, '../public/samples/urban_intersection_mini.pcd')

function randn() {
  const u = Math.random()
  const v = Math.random()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

function addGround(points, rng = () => Math.random()) {
  for (let x = -22; x <= 22; x += 0.22) {
    for (let y = -22; y <= 22; y += 0.22) {
      const onEW = Math.abs(y) < 3.6 && Math.abs(x) < 20
      const onNS = Math.abs(x) < 3.6 && Math.abs(y) < 20
      if (!onEW && !onNS) continue
      const z = -1.74 + rng() * 0.025
      const intensity = 0.12 + rng() * 0.25
      points.push([x, y, z, intensity])
    }
  }
}

function addCurb(points, rng) {
  const strips = [
    { axis: 'x', fixed: 3.8, range: [-20, 20] },
    { axis: 'x', fixed: -3.8, range: [-20, 20] },
    { axis: 'y', fixed: 3.8, range: [-20, 20] },
    { axis: 'y', fixed: -3.8, range: [-20, 20] },
  ]
  for (const s of strips) {
    for (let t = s.range[0]; t <= s.range[1]; t += 0.35) {
      const x = s.axis === 'x' ? t : s.fixed
      const y = s.axis === 'y' ? t : s.fixed
      const z = -1.55 + rng() * 0.08
      points.push([x, y, z, 0.45 + rng() * 0.2])
    }
  }
}

function addBoxCluster(points, cx, cy, cz, sx, sy, sz, n, rng) {
  for (let i = 0; i < n; i++) {
    const x = cx + (rng() - 0.5) * sx
    const y = cy + (rng() - 0.5) * sy
    const z = cz + rng() * sz
    points.push([x, y, z, 0.35 + rng() * 0.4])
  }
}

function addPole(points, x, y, rng) {
  for (let z = -1.7; z < 2.5; z += 0.08) {
    points.push([x + rng() * 0.06, y + rng() * 0.06, z, 0.5 + rng() * 0.15])
  }
}

function generate() {
  const points = []
  const rng = () => Math.random()
  addGround(points, rng)
  addCurb(points, rng)

  // 路口车辆（典型 KITTI 街景尺度，单位米）
  addBoxCluster(points, 8, -1.2, -1.2, 4.2, 1.8, 1.6, 420, rng)   // 前车
  addBoxCluster(points, -6, 5.5, -1.1, 4.0, 1.7, 1.5, 380, rng)  // 左侧车
  addBoxCluster(points, 2, -9, -1.0, 3.8, 1.6, 1.4, 320, rng)     // 横向车
  addBoxCluster(points, -12, -8, -1.1, 3.5, 1.5, 1.4, 260, rng)   // 远车

  addPole(points, 5.5, 5.5, rng)
  addPole(points, -5.5, -5.5, rng)
  addPole(points, 0, 6.2, rng)

  // 路缘噪声
  for (let i = 0; i < 1200; i++) {
    const x = (rng() - 0.5) * 44
    const y = (rng() - 0.5) * 44
    const z = -1.72 + randn() * 0.04
    const onRoad = (Math.abs(y) < 4 && Math.abs(x) < 21) || (Math.abs(x) < 4 && Math.abs(y) < 21)
    if (!onRoad) continue
    points.push([x, y, z, 0.08 + rng() * 0.12])
  }

  return points
}

function toPcd(points) {
  const lines = [
    '# .PCD v0.7 - Point Cloud Data file format',
    '# Mini urban intersection (KITTI-style coordinates), generated for Dasshine Label demo',
    'VERSION 0.7',
    'FIELDS x y z intensity',
    'SIZE 4 4 4 4',
    'TYPE F F F F',
    'COUNT 1 1 1 1',
    `WIDTH ${points.length}`,
    'HEIGHT 1',
    'VIEWPOINT 0 0 0 1 0 0 0',
    `POINTS ${points.length}`,
    'DATA ascii',
  ]
  for (const [x, y, z, I] of points) {
    lines.push(`${x.toFixed(4)} ${y.toFixed(4)} ${z.toFixed(4)} ${I.toFixed(4)}`)
  }
  return lines.join('\n') + '\n'
}

mkdirSync(dirname(OUT), { recursive: true })
const pts = generate()
writeFileSync(OUT, toPcd(pts))
console.log(`Wrote ${pts.length} points -> ${OUT}`)
