import { useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../services/api'
import type { ProjectSummary } from '../../types/project'

export type ProjectListItem = ProjectSummary & { type?: string }

const ANN_TYPE_TO_CATEGORY: Record<string, string> = {
  bbox_2d: 'image_2d', polygon: 'image_2d', polyline: 'image_2d',
  keypoint: 'image_2d', segmentation: 'image_2d', classification: 'image_2d',
  bbox_3d: 'pointcloud_3d', lidar_seg: 'pointcloud_3d', lane_3d: 'pointcloud_3d',
  video_tracking: 'video', video_action: 'video', video_caption: 'video',
  asr: 'audio', tts_label: 'audio', speaker_diarize: 'audio', emotion_audio: 'audio',
  ner: 'nlp', re: 'nlp', sentiment: 'nlp', text_classify: 'nlp',
  qa_pair: 'nlp', summarization: 'nlp', translation: 'nlp',
  robot_traj: 'embodied', robot_action: 'embodied', robot_grasp: 'embodied', robot_scene: 'embodied',
  ocr_text: 'ocr', ocr_layout: 'ocr', ocr_table: 'ocr',
  image_caption: 'multimodal', vqa: 'multimodal', rlhf: 'multimodal',
}

const PROJECT_TYPE_TO_CATEGORY: Record<string, string> = {
  text_classification: 'nlp',
  ner: 'nlp',
  text_summarization: 'nlp',
  image_classification: 'image_2d',
  object_detection: 'image_2d',
  image_segmentation: 'image_2d',
  ocr: 'ocr',
  audio_transcription: 'audio',
  multimodal: 'multimodal',
}

const KNOWN = new Set([
  'image_2d', 'pointcloud_3d', 'video', 'audio', 'nlp', 'embodied', 'ocr', 'multimodal',
])

export function resolveProjectCategory(p: ProjectListItem): string {
  const raw = (p.category ?? '').toString().trim().toLowerCase()
  if (raw && KNOWN.has(raw)) return raw
  const ann = (p.ann_type ?? '').toString().trim().toLowerCase()
  if (ann && ANN_TYPE_TO_CATEGORY[ann]) return ANN_TYPE_TO_CATEGORY[ann]
  const typ = (p.type ?? '').toString().trim().toLowerCase()
  if (typ && PROJECT_TYPE_TO_CATEGORY[typ]) return PROJECT_TYPE_TO_CATEGORY[typ]
  if (typ && KNOWN.has(typ)) return typ
  return raw
}

export function resolveProjectStatus(p: ProjectSummary): string {
  return (p.status ?? '').toString().trim().toLowerCase()
}

export const projectsQueryKey = ['projects', 'list'] as const

async function fetchProjectsList(): Promise<ProjectListItem[]> {
  const { data } = await api.get('/projects', { params: { skip: 0, limit: 200 } })
  const list = (Array.isArray(data) ? data : []) as ProjectListItem[]
  return list.map(p => {
    const category = resolveProjectCategory(p) || undefined
    return {
      ...p,
      category: category as ProjectSummary['category'],
      status: (resolveProjectStatus(p) || undefined) as ProjectSummary['status'],
    }
  })
}

export function useProjectsQuery(enabled = true) {
  return useQuery({
    queryKey: projectsQueryKey,
    queryFn: fetchProjectsList,
    enabled,
    staleTime: 30_000,
  })
}

export function useInvalidateProjects() {
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: projectsQueryKey })
}
