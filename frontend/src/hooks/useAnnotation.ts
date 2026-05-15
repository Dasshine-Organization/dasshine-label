import { useEffect, useRef, useCallback } from 'react'
import useAnnotationStore, { Tool2D, Tool3D } from '../store/annotationStore'

// ─── useAnnotationHotkeys ─────────────────────────────────────────────────────

export function useAnnotationHotkeys() {
  const store = useAnnotationStore()

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

      const { mode, setTool2d, setTool3d,
              undo, redo, deleteAnnotation2d, deleteBox3d,
              selectedIds2d, selectedIds3d, labelClasses, setActiveLabel } = store;

      if (e.ctrlKey || e.metaKey) {
        if (e.key === 'z') { e.preventDefault(); undo(); return }
        if (e.key === 'y') { e.preventDefault(); redo(); return }
        if (e.key === 's') { e.preventDefault(); saveDraft(); return }  // Ctrl+S manual save
      }

      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedIds2d.length > 0) deleteAnnotation2d(selectedIds2d)
        if (selectedIds3d.length > 0) deleteBox3d(selectedIds3d)
        return
      }

      if (mode === '2d' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const map: Record<string, Tool2D> = {
          v: 'select', b: 'bbox', p: 'polygon',
          l: 'polyline', k: 'keypoint', h: 'pan', e: 'eraser',
        }
        const tool = map[e.key.toLowerCase()]
        if (tool) { setTool2d(tool); return }
      }

      if (mode === '3d' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const map: Record<string, Tool3D> = {
          v: 'select', b: 'box3d', o: 'orbit', h: 'pan',
        }
        const tool = map[e.key.toLowerCase()]
        if (tool) { setTool3d(tool); return }
      }

      labelClasses.forEach((lc) => {
        if (lc.hotkey && e.key === lc.hotkey && !e.ctrlKey) setActiveLabel(lc.name)
      })
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])
}

// ─── useAutoSave ──────────────────────────────────────────────────────────────
// Saves draft every `intervalMs` when there are unsaved changes (isDirty).
// Also saves on page unload / tab close.

export function useAutoSave(taskId: string, intervalMs = 8_000) {
  const { setCurrentTask, saveDraft, autoSaveMeta } = useAnnotationStore()

  // Register task on mount
  useEffect(() => {
    setCurrentTask(taskId)
  }, [taskId])

  // Interval save — only when dirty
  useEffect(() => {
    const id = setInterval(() => {
      const { autoSaveMeta } = useAnnotationStore.getState()
      if (autoSaveMeta.isDirty) {
        useAnnotationStore.getState().saveDraft()
      }
    }, intervalMs)
    return () => clearInterval(id)
  }, [taskId, intervalMs])

  // Save on tab close / navigation away
  useEffect(() => {
    function handleBeforeUnload(e: BeforeUnloadEvent) {
      const { autoSaveMeta } = useAnnotationStore.getState()
      if (autoSaveMeta.isDirty) {
        useAnnotationStore.getState().saveDraft()
        e.preventDefault()
        e.returnValue = '你有未保存的标注，确定要离开吗？'
      }
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [])
}

// ─── useLoadSaved ─────────────────────────────────────────────────────────────
// On mount, checks if a draft exists for this task+image and loads it.
// Returns: { hasDraft, draftInfo }

export function useLoadSaved(taskId: string, imageIndex = 0) {
  const { loadDraft, setCurrentTask, setCurrentImageIndex } = useAnnotationStore()

  useEffect(() => {
    setCurrentTask(taskId, imageIndex)
    setCurrentImageIndex(imageIndex)
    loadDraft(taskId, imageIndex)
  }, [taskId, imageIndex])
}

// ─── useDraftManager ─────────────────────────────────────────────────────────
// Higher-level hook for managing drafts across images in a task.

export function useDraftManager(taskId: string) {
  const store = useAnnotationStore()

  const saveCurrentFrame = useCallback(() => {
    store.saveDraft()
  }, [])

  const switchToFrame = useCallback((imageIndex: number) => {
    // Save current frame before switching
    if (store.autoSaveMeta.isDirty) {
      store.saveDraft()
    }
    // Load new frame
    store.setCurrentImageIndex(imageIndex)
    const hasDraft = store.loadDraft(taskId, imageIndex)
    if (!hasDraft) {
      // Clear canvas for fresh frame
      useAnnotationStore.setState({
        annotations2d: [],
        boxes3d: [],
        selectedIds2d: [],
        selectedIds3d: [],
        past: [],
        future: [],
      })
    }
    return hasDraft
  }, [taskId, store])

  const hasDraftForFrame = useCallback((imageIndex: number) => {
    const key = `${taskId}:${imageIndex}`
    return !!store.drafts[key]
  }, [taskId, store.drafts])

  const getDraftCount = useCallback(() => {
    return Object.keys(store.drafts).filter(k => k.startsWith(`${taskId}:`)).length
  }, [taskId, store.drafts])

  return { saveCurrentFrame, switchToFrame, hasDraftForFrame, getDraftCount }
}
