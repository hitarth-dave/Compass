import { Suspense, lazy, Component } from "react";
import CompassSVG from "@/components/CompassSVG";

// The real WebGL compass lives in Compass3DScene. It imports three +
// @react-three/fiber + @react-three/drei. Those are optional deps: if they
// aren't installed, the dynamic import fails and we fall back to CompassSVG,
// so the app always builds and renders.
const Compass3DScene = lazy(() =>
  import("@/components/Compass3DScene").catch(() => ({ default: () => <CompassSVG /> }))
);

class WebGLBoundary extends Component {
  constructor(p) { super(p); this.state = { failed: false }; }
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    if (this.state.failed) return <CompassSVG />;
    return this.props.children;
  }
}

export default function Compass3D() {
  return (
    <WebGLBoundary>
      <Suspense fallback={<CompassSVG />}>
        <Compass3DScene />
      </Suspense>
    </WebGLBoundary>
  );
}
