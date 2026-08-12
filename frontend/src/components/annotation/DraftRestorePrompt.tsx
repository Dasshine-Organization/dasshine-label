import { useEffect } from 'react'
import useAnnotationStore from '../../store/annotationStore'

/**
 * 进入标注页时若有草稿，直接恢复到画布，不再弹出确认。
 * 保留组件以便兼容旧引用；无 UI。
 */
interface Props {
  taskId: string
  imageIndex: number
  onRestored?: () => void
}

export default function DraftRestorePrompt({ taskId, imageIndex, onRestored }: Props) {
  const { drafts, loadDraft } = useAnnotationStore()

  useEffect(() => {
    const key = `${taskId}:${imageIndex}`
    const found = drafts[key]
    if (found && !found.isSubmitted) {
      loadDraft(taskId, imageIndex)
      onRestored?.()
    }
  }, [taskId, imageIndex, drafts, loadDraft, onRestored])

  return null
}
