import toast from 'react-hot-toast'
import useAnnotationStore from '../store/annotationStore'

const TOAST_ID = 'annotation-draft-save'

/** 手动保存成功时调用，全局只弹一次提示 */
export function notifyDraftSaved() {
  toast.success('草稿已保存', { id: TOAST_ID, duration: 2000 })
}

/** 更新顶栏保存状态（仅手动保存时增加 saveCount，避免与 toast 重复触发） */
export function acknowledgeManualDraftSave() {
  const meta = useAnnotationStore.getState().autoSaveMeta
  useAnnotationStore.setState({
    autoSaveMeta: {
      ...meta,
      isDirty: false,
      lastSavedAt: new Date().toISOString(),
      saveCount: meta.saveCount + 1,
    },
  })
  notifyDraftSaved()
}
