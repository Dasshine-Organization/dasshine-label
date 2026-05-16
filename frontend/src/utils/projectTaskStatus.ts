/** 项目任务列表与标注页之间的任务状态同步 */

export type ProjectTaskStatusEventDetail = {
  projectId: number
  taskId: number
  status: string
}

const EVENT_NAME = 'project-task-status'

export function emitProjectTaskStatus(detail: ProjectTaskStatusEventDetail) {
  window.dispatchEvent(new CustomEvent<ProjectTaskStatusEventDetail>(EVENT_NAME, { detail }))
}

export function onProjectTaskStatus(
  handler: (detail: ProjectTaskStatusEventDetail) => void,
): () => void {
  const listener = (e: Event) => {
    const ev = e as CustomEvent<ProjectTaskStatusEventDetail>
    if (ev.detail) handler(ev.detail)
  }
  window.addEventListener(EVENT_NAME, listener)
  return () => window.removeEventListener(EVENT_NAME, listener)
}
