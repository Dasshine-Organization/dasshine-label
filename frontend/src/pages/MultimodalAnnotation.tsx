import { useParams, useSearchParams } from 'react-router-dom'
import ModalityShell from '../components/annotation/ModalityShell'
import ProjectExportMenu from '../components/dataset/ProjectExportMenu'
import { useModalityWorkspace } from '../hooks/useModalityWorkspace'
import { getAnnotateBackHref } from '../utils/annotationRoutes'

const DEMO_IMAGE =
  'https://images.unsplash.com/photo-1545558014-8692077e9b5c?w=960&q=80'

export default function MultimodalAnnotation() {
  const { taskId = '3001' } = useParams<{ taskId: string }>()
  const [searchParams] = useSearchParams()
  const projectIdParam = searchParams.get('projectId')
  const { ws, payload, updatePayload, loading, saving, dirty, lastSavedAt, useBackend, persist, submit, lock, lockBlocked, peers, connected } =
    useModalityWorkspace(taskId, 'multimodal', 'image_caption')

  const imageUrl = ws?.content.image_url || DEMO_IMAGE
  const annType = ws?.ann_type ?? 'image_caption'
  const backHref = getAnnotateBackHref({
    projectId: projectIdParam ?? ws?.project_id,
    category: ws?.category ?? 'multimodal',
  })

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
      dirty={dirty}
      lastSavedAt={lastSavedAt}
      onSave={() => persist(payload, false)}
      onSubmit={() => submit()}
      backHref={backHref}
      backLabel="← 返回"
      lock={lock}
      lockBlocked={lockBlocked}
      peers={peers}
      connected={connected}
      headerExtra={
        <ProjectExportMenu
          projectId={projectIdParam ?? ws?.project_id}
          projectName={ws?.project_name}
          compact
        />
      }
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
          ) : annType === 'rlhf' ? (
            <div className="space-y-3">
              <div className="text-xs text-white/40">成对回复偏好</div>
              <button
                type="button"
                className="text-xs px-3 py-1.5 rounded-lg border border-[#8b5cf6]/40 text-[#c4b5fd]"
                onClick={() =>
                  updatePayload({
                    preferences: [
                      ...(payload.preferences ?? []),
                      {
                        id: `pref_${Date.now().toString(36)}`,
                        prompt: '哪一段回复更好？',
                        response_a: '',
                        response_b: '',
                        winner: 'a',
                      },
                    ],
                  })
                }
              >
                添加偏好对
              </button>
              {(payload.preferences ?? []).map(p => (
                <div key={p.id} className="space-y-2 p-3 rounded-xl border border-[#1e1e2e] bg-[#0a0a0f]">
                  <input
                    className="w-full text-xs bg-transparent border-b border-[#1e1e2e] pb-2"
                    value={p.prompt}
                    onChange={e =>
                      updatePayload({
                        preferences: (payload.preferences ?? []).map(x =>
                          x.id === p.id ? { ...x, prompt: e.target.value } : x,
                        ),
                      })
                    }
                    placeholder="比较提示"
                  />
                  <textarea
                    rows={3}
                    className="w-full text-xs bg-[#12121a] border border-[#1e1e2e] rounded-lg px-2 py-1.5 resize-none"
                    value={p.response_a}
                    onChange={e =>
                      updatePayload({
                        preferences: (payload.preferences ?? []).map(x =>
                          x.id === p.id ? { ...x, response_a: e.target.value } : x,
                        ),
                      })
                    }
                    placeholder="回复 A"
                  />
                  <textarea
                    rows={3}
                    className="w-full text-xs bg-[#12121a] border border-[#1e1e2e] rounded-lg px-2 py-1.5 resize-none"
                    value={p.response_b}
                    onChange={e =>
                      updatePayload({
                        preferences: (payload.preferences ?? []).map(x =>
                          x.id === p.id ? { ...x, response_b: e.target.value } : x,
                        ),
                      })
                    }
                    placeholder="回复 B"
                  />
                  <div className="flex gap-2">
                    {(['a', 'b', 'tie'] as const).map(w => (
                      <button
                        key={w}
                        type="button"
                        onClick={() =>
                          updatePayload({
                            preferences: (payload.preferences ?? []).map(x =>
                              x.id === p.id ? { ...x, winner: w } : x,
                            ),
                          })
                        }
                        className={`text-xs px-2 py-1 rounded border ${
                          p.winner === w ? 'border-[#8b5cf6] text-[#c4b5fd]' : 'border-[#1e1e2e] text-white/40'
                        }`}
                      >
                        {w === 'tie' ? '平局' : `选 ${w.toUpperCase()}`}
                      </button>
                    ))}
                    <button
                      type="button"
                      className="ml-auto text-xs text-red-400/80"
                      onClick={() =>
                        updatePayload({
                          preferences: (payload.preferences ?? []).filter(x => x.id !== p.id),
                        })
                      }
                    >
                      删
                    </button>
                  </div>
                </div>
              ))}
            </div>
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
