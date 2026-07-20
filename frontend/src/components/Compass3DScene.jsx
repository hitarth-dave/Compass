import { useRef, useMemo, Suspense } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Environment } from "@react-three/drei";
import * as THREE from "three";

// A dimensional brass pocket compass. Beige/wood body, engraved dial, a
// zodiac tick ring, red/steel needle, and a domed glass. It never free-spins:
// it floats gently and tilts toward the pointer.

function Body() {
  const brass = useMemo(() => new THREE.MeshStandardMaterial({
    color: "#C7A24E", metalness: 0.85, roughness: 0.32,
  }), []);
  const darkBrass = useMemo(() => new THREE.MeshStandardMaterial({
    color: "#8A6522", metalness: 0.9, roughness: 0.4,
  }), []);
  const dial = useMemo(() => new THREE.MeshStandardMaterial({
    color: "#F2E6C6", metalness: 0.1, roughness: 0.7,
  }), []);

  return (
    <group>
      {/* outer case */}
      <mesh material={brass} position={[0, 0, -0.18]}>
        <cylinderGeometry args={[2.05, 2.05, 0.42, 96]} />
      </mesh>
      {/* bezel ring */}
      <mesh material={darkBrass} position={[0, 0, 0.04]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[2.0, 0.12, 24, 96]} />
      </mesh>
      {/* dial face */}
      <mesh material={dial} position={[0, 0, 0.06]}>
        <cylinderGeometry args={[1.86, 1.86, 0.06, 96]} />
      </mesh>
      {/* pocket ring on top */}
      <mesh material={brass} position={[0, 2.2, 0]} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.22, 0.07, 16, 48]} />
      </mesh>
    </group>
  );
}

function Ticks() {
  const dark = useMemo(() => new THREE.MeshStandardMaterial({ color: "#0A2E23", roughness: 0.6 }), []);
  const gold = useMemo(() => new THREE.MeshStandardMaterial({ color: "#B8860B", metalness: 0.6, roughness: 0.4 }), []);
  const items = [];
  for (let i = 0; i < 72; i++) {
    const a = (i / 72) * Math.PI * 2;
    const major = i % 6 === 0;
    const r = 1.66;
    items.push(
      <mesh key={i} material={major ? gold : dark}
        position={[Math.cos(a) * r, Math.sin(a) * r, 0.1]} rotation={[0, 0, a]}>
        <boxGeometry args={[major ? 0.14 : 0.07, 0.02, 0.02]} />
      </mesh>
    );
  }
  // 8-point rose
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    const long = i % 2 === 0;
    const len = long ? 1.3 : 0.9;
    items.push(
      <mesh key={`r${i}`} material={long ? dark : gold}
        position={[Math.cos(a) * len / 2, Math.sin(a) * len / 2, 0.1]} rotation={[0, 0, a]}>
        <boxGeometry args={[len, 0.09, 0.015]} />
      </mesh>
    );
  }
  return <group>{items}</group>;
}

function Needle() {
  const red = useMemo(() => new THREE.MeshStandardMaterial({ color: "#A0522D", metalness: 0.3, roughness: 0.5 }), []);
  const steel = useMemo(() => new THREE.MeshStandardMaterial({ color: "#123528", metalness: 0.4, roughness: 0.5 }), []);
  const cap = useMemo(() => new THREE.MeshStandardMaterial({ color: "#B8860B", metalness: 0.8, roughness: 0.3 }), []);
  const ref = useRef();
  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.z = Math.sin(state.clock.elapsedTime * 0.6) * 0.06;
    }
  });
  return (
    <group ref={ref} position={[0, 0, 0.16]}>
      <mesh material={red} position={[0, 0.72, 0]}>
        <coneGeometry args={[0.12, 1.5, 4]} />
      </mesh>
      <mesh material={steel} position={[0, -0.72, 0]} rotation={[0, 0, Math.PI]}>
        <coneGeometry args={[0.12, 1.5, 4]} />
      </mesh>
      <mesh material={cap}>
        <cylinderGeometry args={[0.16, 0.16, 0.22, 24]} />
      </mesh>
    </group>
  );
}

function Glass() {
  const glass = useMemo(() => new THREE.MeshPhysicalMaterial({
    color: "#ffffff", metalness: 0, roughness: 0.05,
    transmission: 0.92, transparent: true, opacity: 0.35, thickness: 0.4,
    clearcoat: 1, clearcoatRoughness: 0.1,
  }), []);
  return (
    <mesh material={glass} position={[0, 0, 0.28]}>
      <sphereGeometry args={[1.9, 48, 48, 0, Math.PI * 2, 0, Math.PI * 0.28]} />
    </mesh>
  );
}

function Rig() {
  const group = useRef();
  useFrame((state) => {
    if (!group.current) return;
    const { x, y } = state.pointer; // -1..1
    // ease toward pointer tilt; never a full spin
    group.current.rotation.y += (x * 0.5 - group.current.rotation.y) * 0.05;
    group.current.rotation.x += (-y * 0.4 - group.current.rotation.x) * 0.05;
  });
  return (
    <group ref={group}>
      <Float speed={1.2} rotationIntensity={0.15} floatIntensity={0.5}>
        <group rotation={[-0.35, 0, 0]}>
          <Body />
          <Ticks />
          <Needle />
          <Glass />
        </group>
      </Float>
    </group>
  );
}

export default function Compass3DScene() {
  return (
    <div style={{ width: "100%", height: "min(560px, 86vw)", maxWidth: 560, margin: "0 auto" }}>
      <Canvas camera={{ position: [0, 0, 7], fov: 40 }} dpr={[1, 2]} gl={{ antialias: true, alpha: true }}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[4, 6, 5]} intensity={1.4} color="#FFF3D6" />
        <directionalLight position={[-5, -2, 3]} intensity={0.5} color="#B8860B" />
        <Suspense fallback={null}>
          <Environment preset="sunset" />
        </Suspense>
        <Rig />
      </Canvas>
    </div>
  );
}
