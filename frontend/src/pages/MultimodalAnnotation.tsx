import { useParams } from 'react-router-dom'
import ModalityShell from '../components/annotation/ModalityShell'
import { useModalityWorkspace } from '../hooks/useModalityWorkspace'

const DEMO_IMAGE =
  'https://images.unsplash.com/photo-1545558014-8692077e9b5c?w=960&q=80'

export default function MultimodalAnnotation() {
  const { taskId = '3001' } = useParams<{ taskId: string }>()
  const { ws, payload, updatePayload, loading, saving, useBackend, persist, submit } =
    useModalityWorkspace(taskId, 'multimodal', 'image_caption')

  const imageUrl = ws?.content.image_url || DEMO_IMAGE
  const annType = ws?.ann_type ?? 'image_caption'

  if (loading || !payload) {
    return (
      <div className="h-screen flex items-center justify-center bg-[#0a0a0f] text-white/40 text-sm">
        加载多模态工作区…
      </div>
    )
  }

  return (
    <ModalityShell
      title={`多模态标注 · ${ws?.project_name ?? taskId}`}
      subtitle={`${annType} · task #${taskId}`}
      accent="#8b5cf6"
      useBackend={useBackend}
      saving={saving}
      onSave={() => persist(payload, false)}
      onSubmit={() => submit()}
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 h-full gap-0">
        <section className="p-4 border-r border-[#1e1e2e] flex items-center justify-center bg-black/40">
          <img src={imageUrl} alt="" className="max-h-full max-w-full object-contain rounded-lg" />
        </section>
        <section className="p-4 overflow-y-auto space-y-4">
          {annType === 'vqa' ? (
            <>
              <div>
                <label className="text-xs text-white/40">问题</label>
                <input
                  className="mt-1 w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm"
                  value={payload.vqa?.question ?? ''}
                  onChange={e =>
                    updatePayload({ vqa: { ...(payload.vqa ?? { answer: '' }), question: e.target.value } })
                  }
                />
              </div>
              <div>
                <label className="text-xs text-white/40">答案</label>
                <textarea
                  rows={6}
                  className="mt-1 w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm resize-none"
                  value={payload.vqa?.answer ?? ''}
                  onChange={e =>
                    updatePayload({ vqa: { ...(payload.vqa ?? { question: '' }), answer: e.target.value } })
                  }
                />
              </div>
            </>
          ) : (
            <div>
              <label className="text-xs text-white/40">图像描述 (Caption)</label>
              <textarea
                rows={8}
                className="mt-1 w-full bg-[#0a0a0f] border border-[#1e1e2e] rounded-lg px-3 py-2 text-sm resize-none"
                value={payload.caption ?? ''}
                onChange={e => updatePayload({ caption: e.target.value })}
                placeholder="用自然语言描述图像内容…"
              />
            </div>
          )}
        </section>
      </div>
    </ModalityShell>
  )
}
