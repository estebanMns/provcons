"use client";

import { useEffect, useRef } from "react";

// Excavadora en 3D hecha con piezas de Three.js (sin archivos de modelo).
// Three.js se importa dentro del efecto: solo se descarga en la pantalla de
// registro y nunca en el servidor. Se puede girar arrastrando; con
// "reducir movimiento" activado en el sistema queda quieta.
export function Excavator3D() {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const mount = mountRef.current;
    // En celular el panel izquierdo está oculto: no se descarga ni se anima nada
    if (!mount || mount.getClientRects().length === 0) return;
    let disposed = false;
    let cleanup = () => {};

    import("three").then((THREE) => {
      if (disposed) return;
      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

      const scene = new THREE.Scene();
      const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
      camera.position.set(10.5, 7, 13);
      camera.lookAt(0.4, 1.3, 0);

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      mount.appendChild(renderer.domElement);

      scene.add(new THREE.HemisphereLight(0xfff4e0, 0x0d2f2a, 1.6));
      const sun = new THREE.DirectionalLight(0xffffff, 2.4);
      sun.position.set(6, 10, 7);
      sun.castShadow = true;
      sun.shadow.mapSize.set(1024, 1024);
      Object.assign(sun.shadow.camera, { left: -8, right: 8, top: 8, bottom: -8 });
      scene.add(sun);

      const geometries: InstanceType<typeof THREE.BufferGeometry>[] = [];
      const track = <T extends InstanceType<typeof THREE.BufferGeometry>>(g: T) => { geometries.push(g); return g; };
      const mat = {
        body: new THREE.MeshStandardMaterial({ color: 0xf5a524, roughness: 0.45, metalness: 0.15 }),
        dark: new THREE.MeshStandardMaterial({ color: 0x23282a, roughness: 0.8 }),
        steel: new THREE.MeshStandardMaterial({ color: 0x9aa3a6, roughness: 0.35, metalness: 0.8 }),
        glass: new THREE.MeshStandardMaterial({ color: 0x1b3a4b, roughness: 0.1, metalness: 0.6, transparent: true, opacity: 0.85 }),
        ground: new THREE.MeshStandardMaterial({ color: 0x0f4038, roughness: 1 }),
      };

      const box = (w: number, h: number, d: number, m: InstanceType<typeof THREE.Material>, x = 0, y = 0, z = 0) => {
        const mesh = new THREE.Mesh(track(new THREE.BoxGeometry(w, h, d)), m);
        mesh.position.set(x, y, z);
        mesh.castShadow = mesh.receiveShadow = true;
        return mesh;
      };
      const cylinder = (r: number, len: number, m: InstanceType<typeof THREE.Material>) => {
        const mesh = new THREE.Mesh(track(new THREE.CylinderGeometry(r, r, len, 20)), m);
        mesh.castShadow = true;
        return mesh;
      };

      const excavator = new THREE.Group();
      scene.add(excavator);

      // Suelo: un disco que recibe la sombra
      const ground = new THREE.Mesh(track(new THREE.CircleGeometry(4.8, 48)), mat.ground);
      ground.rotation.x = -Math.PI / 2;
      ground.receiveShadow = true;
      excavator.add(ground);

      // Orugas con ruedas y zapatas
      for (const z of [-1.15, 1.15]) {
        excavator.add(box(4.2, 0.75, 0.75, mat.dark, 0, 0.45, z));
        for (const x of [-1.6, -0.55, 0.55, 1.6]) {
          const wheel = cylinder(0.3, 0.8, mat.steel);
          wheel.rotation.x = Math.PI / 2;
          wheel.position.set(x, 0.45, z);
          excavator.add(wheel);
        }
        for (let x = -2; x <= 2.01; x += 0.4) excavator.add(box(0.28, 0.12, 0.8, mat.dark, x, 0.86, z));
      }
      excavator.add(box(2.2, 0.35, 1.6, mat.dark, 0, 0.95, 0));

      // Torreta: gira sobre las orugas
      const turret = new THREE.Group();
      turret.position.y = 1.15;
      excavator.add(turret);
      turret.add(box(3.4, 0.9, 2.4, mat.body, -0.2, 0.45, 0));          // chasis
      turret.add(box(1.1, 1.0, 2.3, mat.dark, -1.75, 0.55, 0));         // contrapeso
      turret.add(box(1.5, 0.35, 1.3, mat.body, -0.75, 1.07, -0.5));     // capó del motor
      const cab = new THREE.Group();
      cab.position.set(0.7, 0.9, 0.6);
      cab.add(box(1.3, 1.45, 1.05, mat.body, 0, 0.72, 0));
      cab.add(box(0.06, 1.0, 0.85, mat.glass, 0.66, 0.85, 0));          // parabrisas
      cab.add(box(1.0, 0.8, 0.06, mat.glass, -0.05, 0.9, 0.53));         // ventana lateral
      turret.add(cab);
      const exhaust = cylinder(0.07, 0.7, mat.dark);
      exhaust.position.set(-1.1, 1.55, -0.85);
      turret.add(exhaust);

      // Pluma, brazo y cuchara: cada uno gira en su articulación
      const boom = new THREE.Group();
      boom.position.set(1.05, 0.95, -0.35);
      turret.add(boom);
      const boomLength = 3.6;
      boom.add(box(boomLength, 0.48, 0.5, mat.body, boomLength / 2, 0, 0));
      const boomCylinder = cylinder(0.09, 1.9, mat.steel);
      boomCylinder.rotation.z = Math.PI / 2;
      boomCylinder.position.set(1.0, -0.42, 0);
      boom.add(boomCylinder);

      const arm = new THREE.Group();
      arm.position.set(boomLength, 0, 0);
      boom.add(arm);
      const armLength = 2.5;
      arm.add(box(armLength, 0.38, 0.42, mat.body, armLength / 2, 0, 0));
      const armCylinder = cylinder(0.08, 1.5, mat.steel);
      armCylinder.rotation.z = Math.PI / 2;
      armCylinder.position.set(0.9, 0.34, 0);
      arm.add(armCylinder);

      const bucket = new THREE.Group();
      bucket.position.set(armLength, 0, 0);
      arm.add(bucket);
      bucket.add(box(0.12, 0.95, 0.85, mat.dark, 0.05, -0.45, 0));      // fondo
      bucket.add(box(0.75, 0.1, 0.85, mat.dark, 0.38, -0.9, 0));        // base
      for (const z of [-0.43, 0.43]) bucket.add(box(0.75, 0.95, 0.06, mat.dark, 0.38, -0.45, z));
      for (const z of [-0.3, -0.1, 0.1, 0.3]) {
        const tooth = new THREE.Mesh(track(new THREE.ConeGeometry(0.06, 0.25, 8)), mat.steel);
        tooth.rotation.z = -Math.PI / 2;
        tooth.position.set(0.85, -0.9, z);
        bucket.add(tooth);
      }

      excavator.position.x = -0.6;
      excavator.rotation.y = -0.35;

      // Girar con el mouse o el dedo
      let dragX: number | null = null;
      let userYaw = 0;
      const onDown = (e: PointerEvent) => { dragX = e.clientX; renderer.domElement.setPointerCapture(e.pointerId); };
      const onMove = (e: PointerEvent) => { if (dragX === null) return; userYaw += (e.clientX - dragX) * 0.01; dragX = e.clientX; };
      const onUp = () => { dragX = null; };
      renderer.domElement.addEventListener("pointerdown", onDown);
      renderer.domElement.addEventListener("pointermove", onMove);
      renderer.domElement.addEventListener("pointerup", onUp);
      renderer.domElement.addEventListener("pointercancel", onUp);

      const resize = () => {
        const { clientWidth: w, clientHeight: h } = mount;
        if (!w || !h) return;
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      };
      const observer = new ResizeObserver(resize);
      observer.observe(mount);
      resize();

      // Ciclo de excavación: baja la pluma, recoge con la cuchara, sube y gira
      const pose = (t: number) => {
        const dig = (Math.sin(t * 0.9) + 1) / 2;
        boom.rotation.z = 0.55 - dig * 0.55;
        arm.rotation.z = -1.1 - dig * 0.5;
        bucket.rotation.z = -0.4 - (1 - dig) * 0.9;
        turret.rotation.y = Math.sin(t * 0.45) * 0.35;
      };

      let frame = 0;
      const start = performance.now();
      const render = () => {
        const t = (performance.now() - start) / 1000;
        pose(reduceMotion ? 1.2 : t);
        excavator.rotation.y = -0.35 + userYaw;
        renderer.render(scene, camera);
        frame = requestAnimationFrame(render);
      };
      render();

      cleanup = () => {
        cancelAnimationFrame(frame);
        observer.disconnect();
        renderer.domElement.removeEventListener("pointerdown", onDown);
        renderer.domElement.removeEventListener("pointermove", onMove);
        renderer.domElement.removeEventListener("pointerup", onUp);
        renderer.domElement.removeEventListener("pointercancel", onUp);
        geometries.forEach((g) => g.dispose());
        Object.values(mat).forEach((m) => m.dispose());
        renderer.dispose();
        renderer.domElement.remove();
      };
    });

    return () => { disposed = true; cleanup(); };
  }, []);

  return <div ref={mountRef} className="excavator-3d" role="img" aria-label="Excavadora en 3D. Arrastra para girarla." />;
}
