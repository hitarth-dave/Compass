// North Indian Kundali chart - diamond pattern
// Houses: 1(top center), then anticlockwise
export default function KundaliChart({ planets, ascendantSign }) {
  // Group planets by house
  const byHouse = {};
  planets.forEach((p) => {
    if (!byHouse[p.house]) byHouse[p.house] = [];
    byHouse[p.house].push(p);
  });

  // House center coordinates in a 400x400 box (North Indian diamond layout)
  const centers = {
    1: [200, 100],
    2: [100, 50],
    3: [50, 100],
    4: [100, 200],
    5: [50, 300],
    6: [100, 350],
    7: [200, 300],
    8: [300, 350],
    9: [350, 300],
    10: [300, 200],
    11: [350, 100],
    12: [300, 50],
  };

  const rashiOfHouse = (h) => ((ascendantSign + h - 1) % 12) + 1; // 1..12

  return (
    <div className="w-full flex justify-center py-2">
      <svg viewBox="0 0 400 400" className="w-full max-w-md" data-testid="kundali-chart">
        {/* Outer square */}
        <rect x="0" y="0" width="400" height="400" className="kundali-cell" strokeWidth="1.5" />
        {/* Diagonals */}
        <line x1="0" y1="0" x2="400" y2="400" className="kundali-cell" strokeWidth="1" />
        <line x1="400" y1="0" x2="0" y2="400" className="kundali-cell" strokeWidth="1" />
        {/* Inner diamond */}
        <polygon points="200,0 400,200 200,400 0,200" className="kundali-cell" strokeWidth="1" />

        {/* House numbers (small, top-left of each region) */}
        {Object.entries(centers).map(([h, [x, y]]) => (
          <g key={h}>
            <text
              x={x}
              y={y - 26}
              textAnchor="middle"
              className="kundali-house-num"
              style={{ fontSize: 11, opacity: 0.7 }}
            >
              {rashiOfHouse(parseInt(h))}
            </text>
            {(byHouse[parseInt(h)] || []).map((p, i) => (
              <text
                key={p.name}
                x={x}
                y={y + i * 15 - ((byHouse[parseInt(h)].length - 1) * 15) / 2}
                textAnchor="middle"
                className="kundali-planet"
              >
                {p.symbol}{p.retrograde ? "℞" : ""} {p.degree_in_sign.toFixed(0)}°
              </text>
            ))}
            {parseInt(h) === 1 && (
              <text x={x} y={y + 42} textAnchor="middle" style={{ fill: "rgba(212,175,55,0.7)", fontSize: 10, letterSpacing: 2 }}>
                LAGNA
              </text>
            )}
          </g>
        ))}
      </svg>
    </div>
  );
}
