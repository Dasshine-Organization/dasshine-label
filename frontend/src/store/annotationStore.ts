import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import { persist, subscribeWithSelector } from 'zustand/middleware'

// ─── Types ────────────────────────────────────────────────────────────────────

export type AnnotationType = 'bbox' | 'polygon' | 'polyline' | 'keypoint' | 'box3d'
export type AnnotationMode = '2d' | '3d'

export interface Point2D { x: number; y: number }
export interface Point3D { x: number; y: number; z: number }

export interface Annotation2D {
  id: string
  type: AnnotationType
  label: string
  color: string
  points: Point2D[]
  visible: boolean
  locked: boolean
  score?: number
  isAI?: boolean
  attributes?: Record<string, string | number | boolean>
}

export interface Box3D {
  id: string
  label: string
  color: string
  center: Point3D
  size: Point3D
  rotation: Point3D
  visible: boolean
  locked: boolean
  score?: number
  isAI?: boolean
  attributes?: Record<string, string | number | boolean>
}

export interface LabelClass {
  id: string
  name: string
  color: string
  hotkey?: string
}

export type Tool2D = 'select' | 'bbox' | 'polygon' | 'polyline' | 'keypoint' | 'pan' | 'eraser'
export type Tool3D = 'select' | 'box3d' | 'orbit' | 'pan'

// ── Draft = one frame's saved state ──────────────────────────────────────────

export interface AnnotationDraft {
  taskId: string
  imageIndex: number
  annotations2d: Annotation2D[]
  boxes3d: Box3D[]
  savedAt: string        // ISO timestamp
  isSubmitted: boolean
}

// ── Auto-save metadata ────────────────────────────────────────────────────────

export interface AutoSaveMeta {
  lastSavedAt: string | null  // ISO
  isDirty: boolean            // unsaved changes exist
  saveCount: number
  error: string | null
}

// ─── Store state ──────────────────────────────────────────────────────────────

interface AnnotationState {
  // Mode
  mode: AnnotationMode

  // 2D
  annotations2d: Annotation2D[]
  activeTool2d: Tool2D
  selectedIds2d: string[]

  // 3D
  boxes3d: Box3D[]
  activeTool3d: Tool3D
  selectedIds3d: string[]

  // Shared
  labelClasses: LabelClass[];
  activeLabel: string;
  zoom: number;
  showLabels: boolean;
  showConfidence: boolean;
  opacity: number;

  // History
  past: { annotations2d: Annotation2D[]; boxes3d: Box3D[] }[];
  future: { annotations2d: Annotation2D[]; boxes3d: Box3D[] }[];

  // Draft / auto-save
  currentTaskId: string | null;
  currentImageIndex: number;
  drafts: Record<string, AnnotationDraft>;
  autoSaveMeta: AutoSaveMeta;

  // Actions – 2D
  setMode: (mode: AnnotationMode) => void;
  setTool2d: (tool: Tool2D) => void;
  addAnnotation2d: (ann: Annotation2D) => void;
  updateAnnotation2d: (id: string, patch: Partial<Annotation2D>) => void;
  deleteAnnotation2d: (ids: string[]) => void;
  selectAnnotations2d: (ids: string[]) => void;
  clearSelection2d: () => void;

  // Actions – 3D
  setTool3d: (tool: Tool3D) => void;
  addBox3d: (box: Box3D) => void;
  updateBox3d: (id: string, patch: Partial<Box3D>) => void;
  deleteBox3d: (ids: string[]) => void;
  selectBoxes3d: (ids: string[]) => void;
  clearSelection3d: () => void;

  // Shared
  setActiveLabel: (label: string) => void;
  setZoom: (zoom: number) => void;
  toggleLabels: () => void;
  toggleConfidence: () => void;
  setOpacity: (v: number) => void;
  setLabelClasses: (classes: LabelClass[]) => void;
  addLabelClass: (lc: LabelClass) => void;
  updateLabelClass: (id: string, patch: Partial<LabelClass>) => void;
  removeLabelClass: (id: string) => void;

  // History
  pushHistory: () => void;
  undo: () => void;
  redo: () => void;

  // Draft / auto-save
  markDirty: () => void;
  /** @returns 是否成功写入草稿 */
  saveDraft: () => boolean;
  loadDraft: (taskId: string, imageIndex: number) => boolean;
  deleteDraft: (taskId: string, imageIndex: number) => void;
  clearAllDrafts: (taskId?: string) => void;
  getDraftList: () => AnnotationDraft[];
  setCurrentTask: (taskId: string, imageIndex?: number) => void;
  setCurrentImageIndex: (imageIndex: number) => void;
}

// ─── Default label classes ────────────────────────────────────────────────────

const DEFAULT_LABELS: LabelClass[] = [
  { id: '1', name: 'car',          color: '#00d4ff', hotkey: '1' },
  { id: '2', name: 'person',       color: '#7c3aed', hotkey: '2' },
  { id: '3', name: 'truck',        color: '#10b981', hotkey: '3' },
  { id: '4', name: 'bicycle',      color: '#f59e0b', hotkey: '4' },
  { id: '5', name: 'motorcycle',   color: '#ef4444', hotkey: '5' },
  { id: '6', name: 'traffic_sign', color: '#ec4899', hotkey: '6' },
  { id: '7', name: 'pedestrian',   color: '#a78bfa', hotkey: '7' },
  { id: '8', name: 'bus',          color: '#34d399', hotkey: '8' },
]

function draftKey(taskId: string, imageIndex: number) {
  return `${taskId}:${imageIndex}`
}

// ─── Store ────────────────────────────────────────────────────────────────────

const useAnnotationStore = create<AnnotationState>()(
  subscribeWithSelector(
    persist(
      immer((set, get) => ({
    mode: '2d',
    annotations2d: [],
    activeTool2d: 'bbox',
    selectedIds2d: [],
    boxes3d: [],
    activeTool3d: 'box3d',
    selectedIds3d: [],
    labelClasses: DEFAULT_LABELS,
    activeLabel: 'car',
    zoom: 1,
    showLabels: true,
    showConfidence: true,
    opacity: 0.3,
    past: [],
    future: [],
    currentTaskId: null,
    currentImageIndex: 0,
    drafts: {},
    autoSaveMeta: {
      lastSavedAt: null,
      isDirty: false,
      saveCount: 0,
      error: null,
    },

    markDirty: () => set((s) => { s.autoSaveMeta.isDirty = true }),

    setCurrentTask: (taskId, imageIndex = 0) => set((s) => {
      s.currentTaskId = taskId;
      s.currentImageIndex = imageIndex;
    }),

    setCurrentImageIndex: (imageIndex) => set((s) => { s.currentImageIndex = imageIndex }),

    saveDraft: () => {
      const state = get();
      const taskId = state.currentTaskId;
      if (!taskId) return false;
      const key = draftKey(taskId, state.currentImageIndex);
      const savedAt = new Date().toISOString();
      const draft: AnnotationDraft = {
        taskId,
        imageIndex: state.currentImageIndex,
        annotations2d: JSON.parse(JSON.stringify(state.annotations2d)),
        boxes3d: JSON.parse(JSON.stringify(state.boxes3d)),
        savedAt,
        isSubmitted: false,
      };
      set((s) => {
        s.drafts[key] = draft;
        s.autoSaveMeta.isDirty = false;
        s.autoSaveMeta.lastSavedAt = savedAt;
        s.autoSaveMeta.saveCount += 1;
        s.autoSaveMeta.error = null;
      });
      return true;
    },

    loadDraft: (taskId, imageIndex) => {
      const draft = get().drafts[draftKey(taskId, imageIndex)];
      if (!draft) return false;
      set((s) => {
        s.annotations2d = JSON.parse(JSON.stringify(draft.annotations2d));
        s.boxes3d = JSON.parse(JSON.stringify(draft.boxes3d));
        s.selectedIds2d = [];
        s.selectedIds3d = [];
        s.past = [];
        s.future = [];
        s.currentTaskId = taskId;
        s.currentImageIndex = imageIndex;
        s.autoSaveMeta.isDirty = false;
      });
      return true;
    },

    deleteDraft: (taskId, imageIndex) => set((s) => {
      delete s.drafts[draftKey(taskId, imageIndex)];
    }),

    clearAllDrafts: (taskId) => set((s) => {
      if (!taskId) {
        s.drafts = {};
        return;
      }
      for (const k of Object.keys(s.drafts)) {
        if (k.startsWith(`${taskId}:`)) delete s.drafts[k];
      }
    }),

    getDraftList: () =>
      Object.values(get().drafts).sort(
        (a, b) => new Date(b.savedAt).getTime() - new Date(a.savedAt).getTime(),
      ),

    setMode: (mode) => set((s) => { s.mode = mode; }),
    setTool2d: (tool) => set((s) => { s.activeTool2d = tool; }),

    addAnnotation2d: (ann) => set((s) => {
      get().pushHistory();
      s.annotations2d.push(ann);
      s.autoSaveMeta.isDirty = true;
    }),

    updateAnnotation2d: (id, patch) => set((s) => {
      const idx = s.annotations2d.findIndex((a) => a.id === id);
      if (idx !== -1) Object.assign(s.annotations2d[idx], patch);
      s.autoSaveMeta.isDirty = true;
    }),

    deleteAnnotation2d: (ids) => set((s) => {
      get().pushHistory();
      s.annotations2d = s.annotations2d.filter((a) => !ids.includes(a.id));
      s.selectedIds2d = s.selectedIds2d.filter((id) => !ids.includes(id));
      s.autoSaveMeta.isDirty = true;
    }),

    selectAnnotations2d: (ids) => set((s) => { s.selectedIds2d = ids; }),
    clearSelection2d: () => set((s) => { s.selectedIds2d = []; }),

    setTool3d: (tool) => set((s) => { s.activeTool3d = tool; }),

    addBox3d: (box) => set((s) => {
      get().pushHistory();
      s.boxes3d.push(box);
      s.autoSaveMeta.isDirty = true;
    }),

    updateBox3d: (id, patch) => set((s) => {
      const idx = s.boxes3d.findIndex((b) => b.id === id);
      if (idx !== -1) Object.assign(s.boxes3d[idx], patch);
      s.autoSaveMeta.isDirty = true;
    }),

    deleteBox3d: (ids) => set((s) => {
      get().pushHistory();
      s.boxes3d = s.boxes3d.filter((b) => !ids.includes(b.id));
      s.selectedIds3d = s.selectedIds3d.filter((id) => !ids.includes(id));
      s.autoSaveMeta.isDirty = true;
    }),

    selectBoxes3d: (ids) => set((s) => { s.selectedIds3d = ids; }),
    clearSelection3d: () => set((s) => { s.selectedIds3d = []; }),

    setActiveLabel: (label) => set((s) => { s.activeLabel = label; }),
    setZoom: (zoom) => set((s) => { s.zoom = Math.max(0.1, Math.min(10, zoom)); }),
    toggleLabels: () => set((s) => { s.showLabels = !s.showLabels; }),
    toggleConfidence: () => set((s) => { s.showConfidence = !s.showConfidence; }),
    setOpacity: (v) => set((s) => { s.opacity = v; }),
    setLabelClasses: (classes) => set((s) => { s.labelClasses = classes; }),
    addLabelClass: (lc) => set((s) => {
      s.labelClasses.push(lc);
      s.activeLabel = lc.name;
    }),
    updateLabelClass: (id, patch) => set((s) => {
      const idx = s.labelClasses.findIndex((x) => x.id === id);
      if (idx === -1) return;
      const old = s.labelClasses[idx];
      Object.assign(s.labelClasses[idx], patch);
      const newName = patch.name ?? old.name;
      const newColor = patch.color ?? old.color;
      if (patch.name != null && patch.name !== old.name) {
        for (const a of s.annotations2d) {
          if (a.label === old.name) {
            a.label = newName;
            a.color = newColor;
          }
        }
        for (const b of s.boxes3d) {
          if (b.label === old.name) {
            b.label = newName;
            b.color = newColor;
          }
        }
        if (s.activeLabel === old.name) s.activeLabel = newName;
      } else if (patch.color != null) {
        for (const a of s.annotations2d) {
          if (a.label === old.name) a.color = newColor;
        }
        for (const b of s.boxes3d) {
          if (b.label === old.name) b.color = newColor;
        }
      }
    }),
    removeLabelClass: (id) => set((s) => {
      const rm = s.labelClasses.find((x) => x.id === id);
      if (!rm || s.labelClasses.length <= 1) return;
      s.labelClasses = s.labelClasses.filter((x) => x.id !== id);
      const fb = s.labelClasses[0];
      for (const a of s.annotations2d) {
        if (a.label === rm.name) {
          a.label = fb.name;
          a.color = fb.color;
        }
      }
      for (const b of s.boxes3d) {
        if (b.label === rm.name) {
          b.label = fb.name;
          b.color = fb.color;
        }
      }
      if (s.activeLabel === rm.name) s.activeLabel = fb.name;
    }),

    pushHistory: () => {
      const { annotations2d, boxes3d, past } = get();
      set((s) => {
        s.past = [...past.slice(-49), { annotations2d: JSON.parse(JSON.stringify(annotations2d)), boxes3d: JSON.parse(JSON.stringify(boxes3d)) }];
        s.future = [];
      });
    },

    undo: () => set((s) => {
      if (s.past.length === 0) return;
      const prev = s.past[s.past.length - 1];
      s.future.unshift({ annotations2d: JSON.parse(JSON.stringify(s.annotations2d)), boxes3d: JSON.parse(JSON.stringify(s.boxes3d)) });
      s.past.pop();
      s.annotations2d = prev.annotations2d;
      s.boxes3d = prev.boxes3d;
      s.autoSaveMeta.isDirty = true;
    }),

    redo: () => set((s) => {
      if (s.future.length === 0) return;
      const next = s.future[0];
      s.past.push({ annotations2d: JSON.parse(JSON.stringify(s.annotations2d)), boxes3d: JSON.parse(JSON.stringify(s.boxes3d)) });
      s.future.shift();
      s.annotations2d = next.annotations2d;
      s.boxes3d = next.boxes3d;
      s.autoSaveMeta.isDirty = true;
    }),
      })),
      {
        name: 'dasshine-annotation-drafts',
        partialize: (state) => ({ drafts: state.drafts }),
      },
    ),
  ),
);

export default useAnnotationStore;
