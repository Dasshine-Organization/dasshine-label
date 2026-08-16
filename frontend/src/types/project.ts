export type AnnotationCategory =
  | 'image_2d' | 'pointcloud_3d' | 'video'
  | 'audio' | 'nlp' | 'embodied' | 'ocr' | 'multimodal'

export type AnnotationType =
  // 2D
  | 'bbox_2d' | 'polygon' | 'polyline' | 'keypoint' | 'segmentation' | 'classification'
  // 3D
  | 'bbox_3d' | 'lidar_seg' | 'lane_3d'
  // Video
  | 'video_tracking' | 'video_action' | 'video_caption'
  // Audio
  | 'asr' | 'tts_label' | 'speaker_diarize' | 'emotion_audio'
  // NLP
  | 'ner' | 're' | 'sentiment' | 'text_classify' | 'qa_pair' | 'summarization' | 'translation'
  // Robot
  | 'robot_traj' | 'robot_action' | 'robot_grasp' | 'robot_scene'
  // OCR
  | 'ocr_text' | 'ocr_layout' | 'ocr_table'
  // Multimodal
  | 'image_caption' | 'vqa' | 'rlhf'

export type ProjectStatus = 'draft' | 'active' | 'paused' | 'completed' | 'archived'
export type DispatchStrategy = 'smart' | 'random' | 'round_robin' | 'manual'
export type UserLevel = 'novice' | 'junior' | 'intermediate' | 'senior' | 'expert'

export interface LabelClass {
  name: string
  color: string
  hotkey?: string
  attributes?: AttributeDef[]
}

export interface AttributeDef {
  key: string
  type: 'text' | 'select' | 'number' | 'boolean'
  options?: string[]
  required?: boolean
  default?: any
}

export interface CategoryMeta {
  id: AnnotationCategory
  label: string
  icon: string
  color: string
  types: TypeMeta[]
}

export interface TypeMeta {
  id: AnnotationType
  label: string
  desc: string
}

export interface ProjectCreatePayload {
  name: string
  description: string
  cover_color: string
  category: AnnotationCategory
  ann_type: AnnotationType
  label_classes: LabelClass[]
  required_skills: string[]
  min_level: UserLevel
  dispatch_strategy: DispatchStrategy
  tasks_per_annotator: number
  cross_validate_count: number
  price_per_task: number
  bonus_rate: number
  deadline?: string
  auto_label_enabled: boolean
  auto_label_model: string
  auto_label_threshold: number
  schema_config: Record<string, any>
}

export interface ProjectSummary {
  id: number
  name: string
  cover_color?: string
  category?: AnnotationCategory
  ann_type?: AnnotationType
  /** 旧版 Project.type enum，用于类别回退 */
  type?: string
  status?: ProjectStatus
  total_tasks?: number
  total_items?: number
  completed_tasks?: number
  approved_tasks?: number
  approved_items?: number
  price_per_task?: number
  member_count?: number
  cross_validate_count?: number
  created_at?: string
}

export interface DispatchRequest {
  project_id: number
  batch_size: number
  strategy: DispatchStrategy
  target_user_ids?: number[]
}

export interface ProjectStats {
  project_id: number
  total_tasks: number
  pending: number
  in_progress: number
  submitted: number
  approved: number
  rejected: number
  completion_rate: number
  approval_rate: number
  avg_quality_score: number
  total_cost: number
  member_count: number
  dispatch_count: number
}
