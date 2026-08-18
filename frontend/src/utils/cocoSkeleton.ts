/** COCO-17 人体关键点模板（图像坐标，相对宽高的比例）。 */

export const COCO17_JOINTS = [
  'nose',
  'left_eye',
  'right_eye',
  'left_ear',
  'right_ear',
  'left_shoulder',
  'right_shoulder',
  'left_elbow',
  'right_elbow',
  'left_wrist',
  'right_wrist',
  'left_hip',
  'right_hip',
  'left_knee',
  'right_knee',
  'left_ankle',
  'right_ankle',
] as const

export type Coco17Joint = (typeof COCO17_JOINTS)[number]

/** 边：关节下标对 */
export const COCO17_EDGES: Array<[number, number]> = [
  [0, 1],
  [0, 2],
  [1, 3],
  [2, 4],
  [5, 6],
  [5, 7],
  [7, 9],
  [6, 8],
  [8, 10],
  [5, 11],
  [6, 12],
  [11, 12],
  [11, 13],
  [13, 15],
  [12, 14],
  [14, 16],
]

/** 相对画布中心的站立姿态（0–1 归一化） */
const TEMPLATE: Array<[number, number]> = [
  [0.5, 0.18],
  [0.47, 0.16],
  [0.53, 0.16],
  [0.44, 0.18],
  [0.56, 0.18],
  [0.4, 0.32],
  [0.6, 0.32],
  [0.36, 0.48],
  [0.64, 0.48],
  [0.34, 0.62],
  [0.66, 0.62],
  [0.43, 0.58],
  [0.57, 0.58],
  [0.43, 0.74],
  [0.57, 0.74],
  [0.42, 0.9],
  [0.58, 0.9],
]

export function coco17Points(imageWidth: number, imageHeight: number): Array<{ x: number; y: number }> {
  const w = Math.max(1, imageWidth)
  const h = Math.max(1, imageHeight)
  return TEMPLATE.map(([nx, ny]) => ({ x: nx * w, y: ny * h }))
}
