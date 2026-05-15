// AnnotationWorkspace — 通用标注入口，根据任务类型跳转到对应标注页
import { useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { isEmbodiedTaskId } from '../mocks/embodiedDemoData'

export default function AnnotationWorkspace() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()

  useEffect(() => {
    if (!taskId) return
    // Mock：具身任务 ID 与 /annotate-embodied 路由一致；接入 API 后改为按任务类型分流
    if (isEmbodiedTaskId(taskId)) {
      navigate(`/annotate-embodied/${taskId}`, { replace: true })
      return
    }
    navigate(`/annotate-image/${taskId}`, { replace: true })
  }, [taskId, navigate])

  return (
    <div className="h-screen bg-[#0a0a0f] flex items-center justify-center">
      <div className="text-white/30 text-sm animate-pulse">正在加载标注工作台…</div>
    </div>
  )
}
