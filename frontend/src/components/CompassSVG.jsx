import { useEffect, useRef } from "react";

// Lightweight themed SVG compass. Cursor parallax + gentle needle sway.
// Used as a graceful fallback when the WebGL compass can't load.
export default function CompassSVG({ size = 460 }) {
  const wrapRef = useRef(null);
  const needleRef = useRef(null);

  useEffect(() => {
    let raf, mx = 0, my = 0, cx = 0, cy = 0;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const onMove = (e) => {
      mx = (e.clientX / window.innerWidth - 0.5) * 2;
      my = (e.clientY / window.innerHeight - 0.5) * 2;
    };
    window.addEventListener("mousemove", onMove);
    const loop = () => {
      cx += (mx - cx) * 0.05;
      cy += (my - cy) * 0.05;
      if (wrapRef.current) {
        wrapRef.current.style.transform =
          `perspective(1200px) rotateX(${(-cy * 6).toFixed(2)}deg) rotateY(${(cx * 8).toFixed(2)}deg)`;
      }
      if (needleRef.current) {
        const a = cx * 6 + (reduce ? 0 : Math.sin(Date.now() / 1600) * 2.2);
        needleRef.current.setAttribute("transform", `rotate(${a} 200 200)`);
      }
      raf = requestAnimationFrame(loop);
    };
    loop();
    return () => { window.removeEventListener("mousemove", onMove); cancelAnimationFrame(raf); };
  }, []);

  const zodiac = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"];
  const pt = (r, deg) => {
    const a = (deg - 90) * Math.PI / 180;
    return [200 + r * Math.cos(a), 200 + r * Math.sin(a)];
  };

  return (
    <div ref={wrapRef} style={{ width: size, maxWidth: "86vw", aspectRatio: "1/1" }}>
      <svg viewBox="0 0 400 400" width="100%" height="100%" style={{ filter: "drop-shadow(0 30px 44px rgba(120,86,30,.35))" }}>
        <defs>
          <radialGradient id="cbody" cx="40%" cy="34%" r="72%">
            <stop offset="0%" stopColor="#F6E7BE"/><stop offset="42%" stopColor="#D3AC63"/>
            <stop offset="78%" stopColor="#A07C39"/><stop offset="100%" stopColor="#6E4F22"/>
          </radialGradient>
          <linearGradient id="crim" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#F7E9C2"/><stop offset="45%" stopColor="#B98F52"/><stop offset="100%" stopColor="#5C3F1E"/>
          </linearGradient>
          <radialGradient id="cdial" cx="50%" cy="42%" r="62%">
            <stop offset="0%" stopColor="#FBF3DE"/><stop offset="70%" stopColor="#F0E3C2"/><stop offset="100%" stopColor="#E2CE9E"/>
          </radialGradient>
          <linearGradient id="cndl" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#A0522D"/><stop offset="49%" stopColor="#7C241A"/>
            <stop offset="51%" stopColor="#123528"/><stop offset="100%" stopColor="#0A2E23"/>
          </linearGradient>
        </defs>
        <circle cx="200" cy="200" r="186" fill="url(#cbody)"/>
        <circle cx="200" cy="200" r="186" fill="none" stroke="url(#crim)" strokeWidth="12"/>
        <circle cx="200" cy="200" r="162" fill="url(#cdial)"/>
        {Array.from({ length: 180 }).map((_, i) => {
          const d = i * 2;
          const [ax, ay] = pt(150, d);
          const [bx, by] = pt(d % 15 === 0 ? 140 : 145, d);
          return <line key={i} x1={ax} y1={ay} x2={bx} y2={by} stroke="#8A6522" strokeWidth={d % 30 === 0 ? 1.2 : 0.5} opacity="0.6"/>;
        })}
        {zodiac.map((z, i) => {
          const [lx, ly] = pt(118, i * 30 + 15);
          return <text key={i} x={lx} y={ly + 6} textAnchor="middle" fontSize="17" fill="#0A2E23" fontFamily="'Cormorant Garamond', serif">{z}</text>;
        })}
        {Array.from({ length: 16 }).map((_, i) => {
          const d = i * 22.5, long = i % 4 === 0, med = i % 2 === 0;
          const [ax, ay] = pt(long ? 95 : med ? 72 : 52, d);
          const [bx, by] = pt(10, d - 7);
          const [ux, uy] = pt(10, d + 7);
          return <path key={i} d={`M${ax} ${ay} L${bx} ${by} L${ux} ${uy} Z`} fill={long ? "#0A2E23" : med ? "#2E5D4A" : "#9C7A3C"} opacity={long ? 0.9 : med ? 0.7 : 0.5}/>;
        })}
        {[["N",0],["E",90],["S",180],["W",270]].map(([l, d]) => {
          const [lx, ly] = pt(104, d);
          return <text key={l} x={lx} y={ly + 7} textAnchor="middle" fontFamily="'Cormorant Garamond', serif" fontWeight="700" fontSize="22" fill="#0A2E23">{l}</text>;
        })}
        <g ref={needleRef}>
          <path d="M200 88 L210 200 L200 210 L190 200 Z" fill="url(#cndl)"/>
          <path d="M200 312 L210 200 L190 200 Z" fill="#0A2E23"/>
          <circle cx="200" cy="200" r="13" fill="#B8860B" stroke="#6E4F22" strokeWidth="1.5"/>
          <circle cx="200" cy="200" r="5" fill="#4A360F"/>
        </g>
      </svg>
    </div>
  );
}
