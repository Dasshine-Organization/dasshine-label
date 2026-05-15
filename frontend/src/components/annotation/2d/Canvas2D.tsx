import { useRef, useEffect, useCallback, useState } from 'react';
import { v4 as uuid } from 'uuid';
import useAnnotationStore, { Annotation2D, Point2D } from '../../../store/annotationStore';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const HANDLE_RADIUS = 5;
const MIN_BBOX_SIZE = 8;

function hexToRgba(hex: string, alpha: number) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function ptInRect(pt: Point2D, tl: Point2D, br: Point2D) {
  return pt.x >= Math.min(tl.x, br.x) && pt.x <= Math.max(tl.x, br.x) &&
         pt.y >= Math.min(tl.y, br.y) && pt.y <= Math.max(tl.y, br.y);
}

function ptInPolygon(pt: Point2D, pts: Point2D[]) {
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i].x, yi = pts[i].y, xj = pts[j].x, yj = pts[j].y;
    if (((yi > pt.y) !== (yj > pt.y)) && (pt.x < ((xj - xi) * (pt.y - yi)) / (yj - yi) + xi))
      inside = !inside;
  }
  return inside;
}

function distToSegment(pt: Point2D, a: Point2D, b: Point2D) {
  const dx = b.x - a.x, dy = b.y - a.y;
  if (dx === 0 && dy === 0) return Math.hypot(pt.x - a.x, pt.y - a.y);
  const t = Math.max(0, Math.min(1, ((pt.x - a.x) * dx + (pt.y - a.y) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(pt.x - (a.x + t * dx), pt.y - (a.y + t * dy));
}

// ─── Canvas2D ─────────────────────────────────────────────────────────────────

interface Canvas2DProps {
  imageUrl?: string;
}

export default function Canvas2D({ imageUrl }: Canvas2DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const rafRef = useRef<number>(0);

  // canvas transform state
  const [canvasSize, setCanvasSize] = useState({ w: 0, h: 0 });
  const transformRef = useRef({ offsetX: 0, offsetY: 0, scale: 1 });
  const isPanningRef = useRef(false);
  const panStartRef = useRef({ x: 0, y: 0, ox: 0, oy: 0 });

  // drawing state
  const isDrawingRef = useRef(false);
  const currentPointsRef = useRef<Point2D[]>([]);
  const mouseRef = useRef<Point2D>({ x: 0, y: 0 });
  const dragRef = useRef<{ id: string; handleIdx: number; startPts: Point2D[]; startMouse: Point2D } | null>(null);
  const moveRef = useRef<{ ids: string[]; startAnnotations: Annotation2D[]; startMouse: Point2D } | null>(null);

  const store = useAnnotationStore();
  const {
    annotations2d, activeTool2d, selectedIds2d, labelClasses,
    zoom, showLabels, showConfidence, opacity,
    addAnnotation2d, updateAnnotation2d, selectAnnotations2d, clearSelection2d,
    deleteAnnotation2d, setZoom,
  } = store;

  const getLabelColor = useCallback((name: string) => {
    return labelClasses.find((l) => l.name === name)?.color ?? '#00d4ff';
  }, [labelClasses]);

  // ── image load ──
  useEffect(() => {
    if (!imageUrl) return;
    const img = new Image();
    img.onload = () => {
      imgRef.current = img;
      fitImage();
      scheduleRender();
    };
    img.src = imageUrl;
  }, [imageUrl]);

  // ── resize observer ──
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setCanvasSize({ w: width, h: height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => { scheduleRender(); }, [annotations2d, selectedIds2d, showLabels, showConfidence, opacity, canvasSize]);

  function fitImage() {
    const img = imgRef.current;
    const container = containerRef.current;
    if (!img || !container) return;
    const { clientWidth: cw, clientHeight: ch } = container;
    const scale = Math.min(cw / img.width, ch / img.height) * 0.9;
    transformRef.current = {
      scale,
      offsetX: (cw - img.width * scale) / 2,
      offsetY: (ch - img.height * scale) / 2,
    };
    setZoom(scale);
  }

  function screenToImage(sx: number, sy: number): Point2D {
    const t = transformRef.current;
    return { x: (sx - t.offsetX) / t.scale, y: (sy - t.offsetY) / t.scale };
  }

  function imageToScreen(ix: number, iy: number): Point2D {
    const t = transformRef.current;
    return { x: ix * t.scale + t.offsetX, y: iy * t.scale + t.offsetY };
  }

  // ── render ──
  function scheduleRender() {
    cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(render);
  }

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d')!;
    const { w, h } = canvasSize;
    canvas.width = w || canvas.offsetWidth;
    canvas.height = h || canvas.offsetHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // background grid
    drawGrid(ctx, canvas.width, canvas.height);

    // image
    const img = imgRef.current;
    if (img) {
      const t = transformRef.current;
      ctx.drawImage(img, t.offsetX, t.offsetY, img.width * t.scale, img.height * t.scale);
    }

    const { annotations2d: anns, selectedIds2d: sel, showLabels: sl, showConfidence: sc, opacity: op } = useAnnotationStore.getState();

    // draw existing annotations
    anns.forEach((ann) => {
      if (!ann.visible) return;
      const isSelected = sel.includes(ann.id);
      drawAnnotation(ctx, ann, isSelected, sl, sc, op);
    });

    // draw in-progress shape
    const tool = useAnnotationStore.getState().activeTool2d;
    const pts = currentPointsRef.current;
    const mouse = mouseRef.current;
    const color = getLabelColor(useAnnotationStore.getState().activeLabel);

    if (isDrawingRef.current && pts.length > 0) {
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 3]);

      if (tool === 'bbox') {
        const s = imageToScreen(pts[0].x, pts[0].y);
        const e = mouse;
        ctx.strokeRect(s.x, s.y, e.x - s.x, e.y - s.y);
        ctx.fillStyle = hexToRgba(color, 0.15);
        ctx.fillRect(s.x, s.y, e.x - s.x, e.y - s.y);
      } else if (tool === 'polygon' || tool === 'polyline') {
        ctx.beginPath();
        pts.forEach((p, i) => {
          const sp = imageToScreen(p.x, p.y);
          i === 0 ? ctx.moveTo(sp.x, sp.y) : ctx.lineTo(sp.x, sp.y);
        });
        ctx.lineTo(mouse.x, mouse.y);
        if (tool === 'polygon') {
          const first = imageToScreen(pts[0].x, pts[0].y);
          ctx.lineTo(first.x, first.y);
          ctx.fillStyle = hexToRgba(color, 0.15);
          ctx.fill();
        }
        ctx.stroke();
        // draw vertex dots
        pts.forEach((p) => {
          const sp = imageToScreen(p.x, p.y);
          ctx.beginPath();
          ctx.arc(sp.x, sp.y, HANDLE_RADIUS, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
        });
      } else if (tool === 'keypoint') {
        drawCrosshair(ctx, mouse.x, mouse.y, color);
      }

      ctx.restore();
    }
  }, [canvasSize, getLabelColor, imageToScreen]);

  function drawGrid(ctx: CanvasRenderingContext2D, w: number, h: number) {
    ctx.save();
    ctx.strokeStyle = 'rgba(0, 212, 255, 0.04)';
    ctx.lineWidth = 0.5;
    const step = 40;
    for (let x = 0; x < w; x += step) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    }
    for (let y = 0; y < h; y += step) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }
    ctx.restore();
  }

  function drawAnnotation(
    ctx: CanvasRenderingContext2D,
    ann: Annotation2D,
    selected: boolean,
    showLbl: boolean,
    showConf: boolean,
    op: number
  ) {
    const color = ann.color;
    const pts = ann.points.map((p) => imageToScreen(p.x, p.y));
    ctx.save();
    ctx.strokeStyle = selected ? '#ffffff' : color;
    ctx.lineWidth = selected ? 2.5 : 1.5;
    if (ann.isAI) ctx.setLineDash([5, 3]);

    if (ann.type === 'bbox' && pts.length >= 2) {
      const [tl, br] = pts;
      const w = br.x - tl.x, h = br.y - tl.y;
      ctx.fillStyle = hexToRgba(color, op);
      ctx.fillRect(tl.x, tl.y, w, h);
      ctx.strokeRect(tl.x, tl.y, w, h);
      if (selected) drawHandles(ctx, tl, br, color);
      if (showLbl) drawLabel(ctx, ann, tl, showConf);
    } else if (ann.type === 'polygon' && pts.length >= 3) {
      ctx.beginPath();
      pts.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
      ctx.closePath();
      ctx.fillStyle = hexToRgba(color, op);
      ctx.fill();
      ctx.stroke();
      if (selected) pts.forEach((p) => drawHandleDot(ctx, p, color));
      if (showLbl) drawLabel(ctx, ann, pts[0], showConf);
    } else if (ann.type === 'polyline' && pts.length >= 2) {
      ctx.beginPath();
      pts.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
      ctx.stroke();
      if (selected) pts.forEach((p) => drawHandleDot(ctx, p, color));
      if (showLbl) drawLabel(ctx, ann, pts[0], showConf);
    } else if (ann.type === 'keypoint' && pts.length >= 1) {
      const p = pts[0];
      drawCrosshair(ctx, p.x, p.y, color);
      if (showLbl) drawLabel(ctx, ann, { x: p.x + 10, y: p.y - 10 }, showConf);
    }
    ctx.restore();
  }

  function drawHandles(ctx: CanvasRenderingContext2D, tl: Point2D, br: Point2D, color: string) {
    const handles = [
      tl, { x: br.x, y: tl.y }, br, { x: tl.x, y: br.y },
      { x: (tl.x + br.x) / 2, y: tl.y }, { x: (tl.x + br.x) / 2, y: br.y },
      { x: tl.x, y: (tl.y + br.y) / 2 }, { x: br.x, y: (tl.y + br.y) / 2 },
    ];
    handles.forEach((h) => {
      ctx.beginPath();
      ctx.arc(h.x, h.y, HANDLE_RADIUS, 0, Math.PI * 2);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    });
  }

  function drawHandleDot(ctx: CanvasRenderingContext2D, p: Point2D, color: string) {
    ctx.beginPath();
    ctx.arc(p.x, p.y, HANDLE_RADIUS - 1, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }

  function drawCrosshair(ctx: CanvasRenderingContext2D, x: number, y: number, color: string) {
    const R = 10;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.setLineDash([]);
    // outer circle
    ctx.beginPath(); ctx.arc(x, y, R, 0, Math.PI * 2); ctx.stroke();
    // crosshair
    ctx.beginPath(); ctx.moveTo(x - R - 4, y); ctx.lineTo(x + R + 4, y); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x, y - R - 4); ctx.lineTo(x, y + R + 4); ctx.stroke();
    // center dot
    ctx.beginPath(); ctx.arc(x, y, 2.5, 0, Math.PI * 2);
    ctx.fillStyle = color; ctx.fill();
  }

  function drawLabel(ctx: CanvasRenderingContext2D, ann: Annotation2D, pos: Point2D, showConf: boolean) {
    const text = showConf && ann.score != null
      ? `${ann.label} ${(ann.score * 100).toFixed(0)}%`
      : ann.label;
    ctx.font = '11px "DM Sans", sans-serif';
    const metrics = ctx.measureText(text);
    const pad = 4;
    const bw = metrics.width + pad * 2;
    const bh = 18;
    ctx.fillStyle = ann.color;
    ctx.beginPath();
    ctx.roundRect(pos.x, pos.y - bh, bw, bh, 3);
    ctx.fill();
    ctx.fillStyle = '#ffffff';
    ctx.fillText(text, pos.x + pad, pos.y - 5);
  }

  // ── hit testing ──
  function hitTest(sx: number, sy: number): string | null {
    const anns = useAnnotationStore.getState().annotations2d;
    for (let i = anns.length - 1; i >= 0; i--) {
      const ann = anns[i];
      if (!ann.visible || ann.locked) continue;
      const pts = ann.points;
      if (ann.type === 'bbox' && pts.length >= 2) {
        const tl = imageToScreen(pts[0].x, pts[0].y);
        const br = imageToScreen(pts[1].x, pts[1].y);
        if (ptInRect({ x: sx, y: sy }, tl, br)) return ann.id;
      } else if (ann.type === 'polygon' && pts.length >= 3) {
        const spts = pts.map((p) => imageToScreen(p.x, p.y));
        if (ptInPolygon({ x: sx, y: sy }, spts)) return ann.id;
      } else if (ann.type === 'polyline' && pts.length >= 2) {
        const spts = pts.map((p) => imageToScreen(p.x, p.y));
        for (let j = 0; j < spts.length - 1; j++) {
          if (distToSegment({ x: sx, y: sy }, spts[j], spts[j + 1]) < 6) return ann.id;
        }
      } else if (ann.type === 'keypoint' && pts.length >= 1) {
        const sp = imageToScreen(pts[0].x, pts[0].y);
        if (Math.hypot(sx - sp.x, sy - sp.y) < 12) return ann.id;
      }
    }
    return null;
  }

  function getBBoxHandle(sx: number, sy: number, ann: Annotation2D): number {
    if (ann.type !== 'bbox' || ann.points.length < 2) return -1;
    const tl = imageToScreen(ann.points[0].x, ann.points[0].y);
    const br = imageToScreen(ann.points[1].x, ann.points[1].y);
    const handles = [
      tl, { x: br.x, y: tl.y }, br, { x: tl.x, y: br.y },
      { x: (tl.x + br.x) / 2, y: tl.y }, { x: (tl.x + br.x) / 2, y: br.y },
      { x: tl.x, y: (tl.y + br.y) / 2 }, { x: br.x, y: (tl.y + br.y) / 2 },
    ];
    return handles.findIndex((h) => Math.hypot(sx - h.x, sy - h.y) < HANDLE_RADIUS + 2);
  }

  // ── mouse events ──
  function getCanvasPos(e: React.MouseEvent<HTMLCanvasElement>): Point2D {
    const rect = canvasRef.current!.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }

  function onMouseDown(e: React.MouseEvent<HTMLCanvasElement>) {
    const { activeTool2d: tool, selectedIds2d: sel, annotations2d: anns } = useAnnotationStore.getState();
    const sp = getCanvasPos(e);
    mouseRef.current = sp;
    const ip = screenToImage(sp.x, sp.y);

    if (tool === 'pan' || e.button === 1 || (e.button === 0 && e.altKey)) {
      isPanningRef.current = true;
      panStartRef.current = { x: sp.x, y: sp.y, ox: transformRef.current.offsetX, oy: transformRef.current.offsetY };
      return;
    }

    if (tool === 'select') {
      // check handle drag first
      if (sel.length === 1) {
        const ann = anns.find((a) => a.id === sel[0]);
        if (ann) {
          const hIdx = getBBoxHandle(sp.x, sp.y, ann);
          if (hIdx !== -1) {
            dragRef.current = { id: ann.id, handleIdx: hIdx, startPts: [...ann.points], startMouse: sp };
            return;
          }
        }
      }
      const hit = hitTest(sp.x, sp.y);
      if (hit) {
        const newSel = e.shiftKey ? [...sel.filter((id) => id !== hit), ...(sel.includes(hit) ? [] : [hit])] : [hit];
        selectAnnotations2d(newSel);
        // start move
        const hitAnns = anns.filter((a) => newSel.includes(a.id));
        moveRef.current = { ids: newSel, startAnnotations: JSON.parse(JSON.stringify(hitAnns)), startMouse: sp };
      } else {
        clearSelection2d();
      }
      return;
    }

    if (tool === 'eraser') {
      const hit = hitTest(sp.x, sp.y);
      if (hit) deleteAnnotation2d([hit]);
      return;
    }

    // drawing tools
    if (tool === 'bbox') {
      isDrawingRef.current = true;
      currentPointsRef.current = [ip];
    } else if (tool === 'polygon' || tool === 'polyline') {
      if (!isDrawingRef.current) {
        isDrawingRef.current = true;
        currentPointsRef.current = [ip];
      } else {
        // double click = finish
        currentPointsRef.current = [...currentPointsRef.current, ip];
      }
    } else if (tool === 'keypoint') {
      commitAnnotation([ip]);
    }
  }

  function onMouseMove(e: React.MouseEvent<HTMLCanvasElement>) {
    const sp = getCanvasPos(e);
    mouseRef.current = sp;

    if (isPanningRef.current) {
      const { x, y, ox, oy } = panStartRef.current;
      transformRef.current.offsetX = ox + sp.x - x;
      transformRef.current.offsetY = oy + sp.y - y;
      scheduleRender();
      return;
    }

    if (dragRef.current) {
      const { id, handleIdx, startPts, startMouse } = dragRef.current;
      const dx = (sp.x - startMouse.x) / transformRef.current.scale;
      const dy = (sp.y - startMouse.y) / transformRef.current.scale;
      const newPts = startPts.map((p) => ({ ...p }));
      resizeBBox(newPts, handleIdx, dx, dy);
      updateAnnotation2d(id, { points: newPts });
      scheduleRender();
      return;
    }

    if (moveRef.current) {
      const { ids, startAnnotations, startMouse } = moveRef.current;
      const dx = (sp.x - startMouse.x) / transformRef.current.scale;
      const dy = (sp.y - startMouse.y) / transformRef.current.scale;
      ids.forEach((id, i) => {
        const orig = startAnnotations[i];
        if (!orig) return;
        updateAnnotation2d(id, { points: orig.points.map((p) => ({ x: p.x + dx, y: p.y + dy })) });
      });
      scheduleRender();
      return;
    }

    scheduleRender();
  }

  function resizeBBox(pts: Point2D[], handleIdx: number, dx: number, dy: number) {
    // handles: 0=TL,1=TR,2=BR,3=BL,4=TM,5=BM,6=ML,7=MR
    switch (handleIdx) {
      case 0: pts[0].x += dx; pts[0].y += dy; break;
      case 1: pts[1].x += dx; pts[0].y += dy; break;
      case 2: pts[1].x += dx; pts[1].y += dy; break;
      case 3: pts[0].x += dx; pts[1].y += dy; break;
      case 4: pts[0].y += dy; break;
      case 5: pts[1].y += dy; break;
      case 6: pts[0].x += dx; break;
      case 7: pts[1].x += dx; break;
    }
  }

  function onMouseUp(e: React.MouseEvent<HTMLCanvasElement>) {
    const sp = getCanvasPos(e);
    const ip = screenToImage(sp.x, sp.y);
    const tool = useAnnotationStore.getState().activeTool2d;

    isPanningRef.current = false;
    dragRef.current = null;
    moveRef.current = null;

    if (tool === 'bbox' && isDrawingRef.current) {
      const start = currentPointsRef.current[0];
      if (Math.abs(ip.x - start.x) > MIN_BBOX_SIZE / transformRef.current.scale &&
          Math.abs(ip.y - start.y) > MIN_BBOX_SIZE / transformRef.current.scale) {
        commitAnnotation([
          { x: Math.min(start.x, ip.x), y: Math.min(start.y, ip.y) },
          { x: Math.max(start.x, ip.x), y: Math.max(start.y, ip.y) },
        ]);
      }
      isDrawingRef.current = false;
      currentPointsRef.current = [];
    }
  }

  function onDoubleClick(_e: React.MouseEvent<HTMLCanvasElement>) {
    const tool = useAnnotationStore.getState().activeTool2d;
    if ((tool === 'polygon' || tool === 'polyline') && isDrawingRef.current) {
      const pts = currentPointsRef.current;
      if (pts.length >= (tool === 'polygon' ? 3 : 2)) {
        commitAnnotation(pts.slice(0, -1)); // remove last duplicate point from mousedown
      }
      isDrawingRef.current = false;
      currentPointsRef.current = [];
    }
  }

  function onWheel(e: React.WheelEvent<HTMLCanvasElement>) {
    e.preventDefault();
    const sp = getCanvasPos(e as unknown as React.MouseEvent<HTMLCanvasElement>);
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    const t = transformRef.current;
    const newScale = Math.max(0.05, Math.min(20, t.scale * factor));
    t.offsetX = sp.x - (sp.x - t.offsetX) * (newScale / t.scale);
    t.offsetY = sp.y - (sp.y - t.offsetY) * (newScale / t.scale);
    t.scale = newScale;
    setZoom(newScale);
    scheduleRender();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    const state = useAnnotationStore.getState();
    if (e.key === 'Escape') {
      isDrawingRef.current = false;
      currentPointsRef.current = [];
      scheduleRender();
    }
    if (e.key === 'Delete' || e.key === 'Backspace') {
      if (state.selectedIds2d.length > 0) deleteAnnotation2d(state.selectedIds2d);
    }
    if (e.ctrlKey && e.key === 'z') state.undo();
    if (e.ctrlKey && e.key === 'y') state.redo();
    if (e.key === 'f') fitImage();
    // label hotkeys
    state.labelClasses.forEach((lc) => {
      if (lc.hotkey && e.key === lc.hotkey) state.setActiveLabel(lc.name);
    });
  }

  function commitAnnotation(points: Point2D[]) {
    const state = useAnnotationStore.getState();
    const color = getLabelColor(state.activeLabel);
    const typeMap: Record<string, Annotation2D['type']> = {
      bbox: 'bbox', polygon: 'polygon', polyline: 'polyline', keypoint: 'keypoint',
    };
    const ann: Annotation2D = {
      id: uuid(),
      type: typeMap[state.activeTool2d] ?? 'bbox',
      label: state.activeLabel,
      color,
      points,
      visible: true,
      locked: false,
    };
    addAnnotation2d(ann);
    scheduleRender();
  }

  const cursorMap: Record<string, string> = {
    select: 'default',
    bbox: 'crosshair',
    polygon: 'crosshair',
    polyline: 'crosshair',
    keypoint: 'crosshair',
    pan: 'grab',
    eraser: 'cell',
  };

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full bg-[#0a0a0f] overflow-hidden focus:outline-none"
      style={{ cursor: isPanningRef.current ? 'grabbing' : cursorMap[activeTool2d] }}
      tabIndex={0}
      onKeyDown={onKeyDown}
    >
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ cursor: 'inherit' }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onDoubleClick={onDoubleClick}
        onWheel={onWheel}
        onContextMenu={(e) => {
          e.preventDefault();
          if (isDrawingRef.current) {
            isDrawingRef.current = false;
            currentPointsRef.current = [];
            scheduleRender();
          }
        }}
      />

      {/* zoom indicator */}
      <div className="absolute bottom-3 right-3 text-xs text-[#00d4ff]/60 font-mono bg-black/40 px-2 py-1 rounded">
        {(zoom * 100).toFixed(0)}%
      </div>

      {/* keyboard hints */}
      <div className="absolute bottom-3 left-3 text-[10px] text-white/20 space-x-3">
        <span>Scroll: zoom</span>
        <span>Alt+drag: pan</span>
        <span>Dbl-click: finish</span>
        <span>Esc: cancel</span>
        <span>F: fit</span>
        <span>Del: delete</span>
      </div>
    </div>
  );
}
