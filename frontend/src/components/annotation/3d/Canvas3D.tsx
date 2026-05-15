import { useRef, useEffect, useState } from 'react';
import { v4 as uuid } from 'uuid';
import useAnnotationStore, { Box3D } from '../../../store/annotationStore';

// We load Three.js from CDN at runtime to avoid bundler issues in the existing project.
// In production you'd do: import * as THREE from 'three'
declare global { interface Window { THREE: any; } }

const THREE_CDN = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function hexToThreeColor(hex: string) {
  return parseInt(hex.replace('#', '0x'), 16);
}

function generateDemoPointCloud(n = 8000) {
  const positions = new Float32Array(n * 3);
  const colors = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const x = (Math.random() - 0.5) * 40;
    const y = (Math.random() - 0.5) * 2 + Math.random() * 0.5;
    const z = (Math.random() - 0.5) * 40;
    positions[i * 3]     = x;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = z;
    // height-based color
    const t = (y + 1.5) / 3;
    colors[i * 3]     = t * 0.2 + 0.1;
    colors[i * 3 + 1] = t * 0.6 + 0.2;
    colors[i * 3 + 2] = 1 - t * 0.4;
  }
  return { positions, colors };
}

// ─── Canvas3D ─────────────────────────────────────────────────────────────────

interface Canvas3DProps {
  pointCloudUrl?: string;
}

export default function Canvas3D({ pointCloudUrl: _pointCloudUrl }: Canvas3DProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<any>(null);
  const sceneRef = useRef<any>(null);
  const cameraRef = useRef<any>(null);
  const boxMeshesRef = useRef<Map<string, any>>(new Map());
  const rafRef = useRef<number>(0);
  const [threeLoaded, setThreeLoaded] = useState(false);
  const [isDrawing3D, setIsDrawing3D] = useState(false);
  const [drawStart, setDrawStart] = useState<{ x: number; z: number } | null>(null);

  // orbit controls state
  const orbitRef = useRef({
    spherical: { r: 30, theta: Math.PI / 4, phi: Math.PI / 3 },
    target: { x: 0, y: 0, z: 0 },
    isDragging: false,
    lastPos: { x: 0, y: 0 },
    isPanning: false,
  });

  const store = useAnnotationStore();
  const { boxes3d, activeTool3d, selectedIds3d } = store;

  // ── load Three.js ──
  useEffect(() => {
    if (window.THREE) { setThreeLoaded(true); return; }
    const script = document.createElement('script');
    script.src = THREE_CDN;
    script.onload = () => setThreeLoaded(true);
    document.head.appendChild(script);
  }, []);

  // ── init scene ──
  useEffect(() => {
    if (!threeLoaded || !containerRef.current) return;
    const THREE = window.THREE;
    const container = containerRef.current;
    const W = container.clientWidth, H = container.clientHeight;

    // renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(W, H);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x0a0a0f, 1);
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // camera
    const camera = new THREE.PerspectiveCamera(60, W / H, 0.1, 1000);
    updateCameraFromSpherical(camera);
    cameraRef.current = camera;

    // grid
    const grid = new THREE.GridHelper(80, 80, 0x1e3a5f, 0x0d1f33);
    scene.add(grid);

    // axes
    const axesHelper = new THREE.AxesHelper(3);
    scene.add(axesHelper);

    // ambient + directional light
    scene.add(new THREE.AmbientLight(0xffffff, 0.4));
    const dirLight = new THREE.DirectionalLight(0x00d4ff, 0.6);
    dirLight.position.set(10, 20, 10);
    scene.add(dirLight);

    // point cloud
    const { positions, colors } = generateDemoPointCloud(12000);
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    const mat = new THREE.PointsMaterial({ size: 0.08, vertexColors: true, sizeAttenuation: true });
    const points = new THREE.Points(geo, mat);
    scene.add(points);

    // resize observer
    const ro = new ResizeObserver(() => {
      const w = container.clientWidth, h = container.clientHeight;
      renderer.setSize(w, h);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    });
    ro.observe(container);

    // render loop
    const animate = () => {
      rafRef.current = requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      renderer.dispose();
      if (container.contains(renderer.domElement)) container.removeChild(renderer.domElement);
    };
  }, [threeLoaded]);

  // ── sync boxes ──
  useEffect(() => {
    if (!sceneRef.current || !threeLoaded) return;
    const THREE = window.THREE;
    const scene = sceneRef.current;

    // remove stale
    boxMeshesRef.current.forEach((mesh, id) => {
      if (!boxes3d.find((b) => b.id === id)) {
        scene.remove(mesh);
        boxMeshesRef.current.delete(id);
      }
    });

    // add / update
    boxes3d.forEach((box) => {
      if (!box.visible) return;
      const isSelected = selectedIds3d.includes(box.id);
      const color = hexToThreeColor(box.color);

      if (boxMeshesRef.current.has(box.id)) {
        const group = boxMeshesRef.current.get(box.id);
        // update transform
        group.position.set(box.center.x, box.center.y, box.center.z);
        group.scale.set(box.size.x, box.size.y, box.size.z);
        group.rotation.set(box.rotation.x, box.rotation.y, box.rotation.z);
        // update color
        group.children.forEach((child: any) => {
          if (child.material?.color) child.material.color.setHex(color);
        });
      } else {
        const group = new THREE.Group();

        // wireframe box
        const geo = new THREE.BoxGeometry(1, 1, 1);
        const edges = new THREE.EdgesGeometry(geo);
        const lineMat = new THREE.LineBasicMaterial({
          color,
          linewidth: isSelected ? 3 : 1.5,
          transparent: true,
          opacity: isSelected ? 1 : 0.85,
        });
        const wireframe = new THREE.LineSegments(edges, lineMat);
        group.add(wireframe);

        // semi-transparent fill
        const fillMat = new THREE.MeshBasicMaterial({
          color,
          transparent: true,
          opacity: 0.08,
          side: THREE.DoubleSide,
        });
        const fillMesh = new THREE.Mesh(geo, fillMat);
        group.add(fillMesh);

        // corner handles
        const corners = [
          [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [-0.5, 0.5, -0.5], [0.5, 0.5, -0.5],
          [-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [-0.5, 0.5, 0.5], [0.5, 0.5, 0.5],
        ];
        const cornerGeo = new THREE.SphereGeometry(0.04, 6, 6);
        const cornerMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
        corners.forEach(([cx, cy, cz]) => {
          const sphere = new THREE.Mesh(cornerGeo, cornerMat);
          sphere.position.set(cx, cy, cz);
          group.add(sphere);
        });

        group.position.set(box.center.x, box.center.y, box.center.z);
        group.scale.set(box.size.x, box.size.y, box.size.z);
        group.rotation.set(box.rotation.x, box.rotation.y, box.rotation.z);
        scene.add(group);
        boxMeshesRef.current.set(box.id, group);
      }
    });
  }, [boxes3d, selectedIds3d, threeLoaded]);

  // ── camera helpers ──
  function updateCameraFromSpherical(camera?: any) {
    const cam = camera || cameraRef.current;
    if (!cam) return;
    const { r, theta, phi } = orbitRef.current.spherical;
    const { x: tx, y: ty, z: tz } = orbitRef.current.target;
    cam.position.set(
      tx + r * Math.sin(phi) * Math.sin(theta),
      ty + r * Math.cos(phi),
      tz + r * Math.sin(phi) * Math.cos(theta)
    );
    cam.lookAt(tx, ty, tz);
  }

  // ── mouse events ──
  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    const tool = useAnnotationStore.getState().activeTool3d;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    orbitRef.current.lastPos = { x: e.clientX, y: e.clientY };

    if (tool === 'orbit' || e.button === 1) {
      orbitRef.current.isDragging = true;
    } else if (tool === 'pan') {
      orbitRef.current.isPanning = true;
    } else if (tool === 'box3d') {
      // project mouse to ground plane (y=0)
      const pt = groundIntersect(e);
      if (pt) {
        setIsDrawing3D(true);
        setDrawStart({ x: pt.x, z: pt.z });
      }
    }
  }

  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const dx = e.clientX - orbitRef.current.lastPos.x;
    const dy = e.clientY - orbitRef.current.lastPos.y;
    orbitRef.current.lastPos = { x: e.clientX, y: e.clientY };

    if (orbitRef.current.isDragging) {
      orbitRef.current.spherical.theta -= dx * 0.01;
      orbitRef.current.spherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, orbitRef.current.spherical.phi + dy * 0.01));
      updateCameraFromSpherical();
    }
    if (orbitRef.current.isPanning) {
      const cam = cameraRef.current;
      if (!cam) return;
      const right = new window.THREE.Vector3();
      const up = new window.THREE.Vector3();
      cam.getWorldDirection(right);
      right.cross(cam.up).normalize();
      up.copy(cam.up);
      const scale = orbitRef.current.spherical.r * 0.002;
      orbitRef.current.target.x -= right.x * dx * scale - up.x * dy * scale;
      orbitRef.current.target.y -= right.y * dx * scale - up.y * dy * scale;
      orbitRef.current.target.z -= right.z * dx * scale - up.z * dy * scale;
      updateCameraFromSpherical();
    }
  }

  function onPointerUp(e: React.PointerEvent<HTMLDivElement>) {
    orbitRef.current.isDragging = false;
    orbitRef.current.isPanning = false;

    if (isDrawing3D && drawStart) {
      const pt = groundIntersect(e);
      if (pt) {
        const cx = (drawStart.x + pt.x) / 2;
        const cz = (drawStart.z + pt.z) / 2;
        const sx = Math.abs(pt.x - drawStart.x);
        const sz = Math.abs(pt.z - drawStart.z);
        if (sx > 0.3 && sz > 0.3) {
          const state = useAnnotationStore.getState();
          const color = state.labelClasses.find((l) => l.name === state.activeLabel)?.color ?? '#00d4ff';
          const box: Box3D = {
            id: uuid(),
            label: state.activeLabel,
            color,
            center: { x: cx, y: 0.75, z: cz },
            size: { x: sx, y: 1.5, z: sz },
            rotation: { x: 0, y: 0, z: 0 },
            visible: true,
            locked: false,
          };
          store.addBox3d(box);
        }
      }
      setIsDrawing3D(false);
      setDrawStart(null);
    }
  }

  function onWheel(e: React.WheelEvent<HTMLDivElement>) {
    e.preventDefault();
    orbitRef.current.spherical.r = Math.max(2, Math.min(200, orbitRef.current.spherical.r * (e.deltaY > 0 ? 1.1 : 0.9)));
    updateCameraFromSpherical();
  }

  function groundIntersect(e: React.PointerEvent<HTMLDivElement>): { x: number; z: number } | null {
    const cam = cameraRef.current;
    const container = containerRef.current;
    if (!cam || !container) return null;
    const THREE = window.THREE;
    const rect = container.getBoundingClientRect();
    const ndc = new THREE.Vector2(
      ((e.clientX - rect.left) / rect.width) * 2 - 1,
      -((e.clientY - rect.top) / rect.height) * 2 + 1
    );
    const raycaster = new THREE.Raycaster();
    raycaster.setFromCamera(ndc, cam);
    const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
    const target = new THREE.Vector3();
    raycaster.ray.intersectPlane(plane, target);
    if (!target) return null;
    return { x: target.x, z: target.z };
  }

  const cursorMap: Record<string, string> = {
    select: 'default',
    box3d: 'crosshair',
    orbit: orbitRef.current.isDragging ? 'grabbing' : 'grab',
    pan: orbitRef.current.isPanning ? 'grabbing' : 'all-scroll',
  };

  return (
    <div className="relative w-full h-full bg-[#0a0a0f] overflow-hidden" style={{ cursor: cursorMap[activeTool3d] }}>
      <div
        ref={containerRef}
        className="w-full h-full"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onWheel={onWheel}
      />

      {!threeLoaded && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-[#00d4ff] text-sm animate-pulse">Loading 3D engine...</div>
        </div>
      )}

      {isDrawing3D && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 bg-[#00d4ff]/10 border border-[#00d4ff]/30 text-[#00d4ff] text-xs px-3 py-1 rounded">
          Release to place 3D bounding box
        </div>
      )}

      {/* stats overlay */}
      <div className="absolute top-3 right-3 text-[10px] text-white/30 font-mono space-y-0.5 text-right">
        <div>{boxes3d.filter(b => b.visible).length} boxes</div>
        <div>~12k pts</div>
      </div>

      {/* controls hint */}
      <div className="absolute bottom-3 left-3 text-[10px] text-white/20 space-x-3">
        <span>Drag: orbit</span>
        <span>Scroll: zoom</span>
        <span>Pan tool: pan</span>
        <span>Box tool: draw box</span>
      </div>
    </div>
  );
}
