import Scene3DWorkspace from './Scene3DWorkspace'

interface Canvas3DProps {
  pointCloudUrl?: string
}

/** @deprecated 使用 Scene3DWorkspace；保留别名便于现有引用 */
export default function Canvas3D(props: Canvas3DProps) {
  return <Scene3DWorkspace {...props} />
}

export { Scene3DWorkspace }
