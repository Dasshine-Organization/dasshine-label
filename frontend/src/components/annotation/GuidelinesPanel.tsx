import { useCallback, useEffect, useState } from 'react'
import { Modal, message } from 'antd'
import { projectApi } from '../../services/api'

type GuidelinesState = {
  guidelines_md: string
  guidelines_version: number
  must_read: boolean
  needs_ack: boolean
}

/** 必读确认弹窗 + 侧栏规范正文 */
export function useProjectGuidelines(projectId?: number | string | null) {
  const pid = Number(projectId)
  const [state, setState] = useState<GuidelinesState | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!pid || Number.isNaN(pid)) {
      setState(null)
      return
    }
    setLoading(true)
    try {
      const { data } = await projectApi.getGuidelines(pid)
      setState({
        guidelines_md: data.guidelines_md || '',
        guidelines_version: data.guidelines_version || 0,
        must_read: Boolean(data.must_read),
        needs_ack: Boolean(data.needs_ack),
      })
    } catch {
      setState(null)
    } finally {
      setLoading(false)
    }
  }, [pid])

  useEffect(() => {
    void load()
  }, [load])

  const ack = useCallback(async () => {
    if (!pid || Number.isNaN(pid)) return
    try {
      await projectApi.ackGuidelines(pid)
      message.success('已确认标注规范')
      await load()
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail ?? '确认失败')
    }
  }, [pid, load])

  return { state, loading, reload: load, ack, projectId: pid }
}

export function GuidelinesAckModal({
  open,
  markdown,
  onAck,
}: {
  open: boolean
  markdown: string
  onAck: () => void
}) {
  return (
    <Modal
      open={open}
      title="请先阅读标注规范"
      okText="我已阅读并确认"
      cancelButtonProps={{ style: { display: 'none' } }}
      closable={false}
      maskClosable={false}
      onOk={onAck}
      width={640}
    >
      <div className="max-h-[50vh] overflow-y-auto text-sm text-white/70 whitespace-pre-wrap leading-relaxed">
        {markdown || '（空规范）'}
      </div>
    </Modal>
  )
}

export function GuidelinesSidePanel({ markdown }: { markdown?: string }) {
  if (!markdown?.trim()) {
    return <div className="text-[11px] text-white/30 p-2">暂无项目标注规范</div>
  }
  return (
    <div className="text-[12px] text-white/65 whitespace-pre-wrap leading-relaxed p-2 max-h-[50vh] overflow-y-auto">
      {markdown}
    </div>
  )
}
