// Enriched North-Indian Kundali chart with planet names, degrees & dignities.
// Dignity color codes:
//   Exalted     → emerald   (up-arrow, green)
//   Debilitated → terracotta (down-arrow, red-brown)
//   Moolatrikona → gold      (M tag)
//   Own Sign    → gold-soft  (O tag)
//   Vargottama  → indigo     (V tag)
const DIGNITY_COLOR = {
  "Exalted": "#0F5132",
  "Debilitated": "#A0522D",
  "Moolatrikona": "#B8860B",
  "Own Sign": "#DAA520",
  "Vargottama": "#3B4C99",
};

const DIGNITY_SHORT = {
  "Exalted": "↑",
  "Debilitated": "↓",
  "Moolatrikona": "MT",
  "Own Sign": "OWN",
  "Vargottama": "VG",
};

// Shortened planet name for chart legibility
const SHORT = {
  Sun: "Sun", Moon: "Moon", Mars: "Mars", Mercury: "Merc",
  Jupiter: "Jup", Venus: "Ven", Saturn: "Sat", Rahu: "Rahu", Ketu: "Ketu",
};

export default function KundaliChart({ planets, ascendantSign }) {
  const byHouse = {};
  planets.forEach((p) => {
    if (!byHouse[p.house]) byHouse[p.house] = [];
    byHouse[p.house].push(p);
  });

  // 520x520 for more room; house centers scaled proportionally
  const S = 520;
  const centers = {
    1: [S * 0.5, S * 0.24],
    2: [S * 0.25, S * 0.12],
    3: [S * 0.12, S * 0.25],
    4: [S * 0.24, S * 0.5],
    5: [S * 0.12, S * 0.75],
    6: [S * 0.25, S * 0.88],
    7: [S * 0.5, S * 0.76],
    8: [S * 0.75, S * 0.88],
    9: [S * 0.88, S * 0.75],
    10: [S * 0.76, S * 0.5],
    11: [S * 0.88, S * 0.25],
    12: [S * 0.75, S * 0.12],
  };

  const rashiOfHouse = (h) => ((ascendantSign + h - 1) % 12) + 1;

  return (
    <div className="w-full flex justify-center py-2">
      <svg viewBox={`0 0 ${S} ${S}`} className="w-full max-w-2xl" data-testid="kundali-chart">
        {/* Outer square */}
        <rect x="0" y="0" width={S} height={S} className="kundali-cell" strokeWidth="1.75" />
        <line x1="0" y1="0" x2={S} y2={S} className="kundali-cell" strokeWidth="1" />
        <line x1={S} y1="0" x2="0" y2={S} className="kundali-cell" strokeWidth="1" />
        <polygon points={`${S/2},0 ${S},${S/2} ${S/2},${S} 0,${S/2}`} className="kundali-cell" strokeWidth="1.25" />

        {Object.entries(centers).map(([h, [x, y]]) => {
          const house = parseInt(h);
          const list = byHouse[house] || [];
          const lineHeight = 18;
          const startY = y - ((list.length - 1) * lineHeight) / 2 - (house === 1 ? 6 : 0);
          return (
            <g key={h}>
              {/* Rashi number */}
              <text
                x={x - 30}
                y={y - 40}
                textAnchor="middle"
                className="kundali-house-num"
              >
                {rashiOfHouse(house)}
              </text>

              {list.map((p, i) => {
                const tags = p.dignity || [];
                const firstTag = tags[0];
                const color = firstTag ? DIGNITY_COLOR[firstTag] : "var(--jai-green-deep)";
                const yy = startY + i * lineHeight;
                return (
                  <g key={p.name}>
                    <text
                      x={x}
                      y={yy}
                      textAnchor="middle"
                      className="kundali-planet"
                      style={{ fill: color }}
                    >
                      {SHORT[p.name] || p.name}
                      {p.retrograde ? " ℞" : ""} {Math.round(p.degree_in_sign)}°
                      {tags.length > 0 && (
                        <tspan
                          className="kundali-planet-tag"
                          style={{ fill: color }}
                          dx="3"
                        >
                          {DIGNITY_SHORT[tags[0]]}
                          {tags.length > 1 ? `·${DIGNITY_SHORT[tags[1]]}` : ""}
                        </tspan>
                      )}
                    </text>
                  </g>
                );
              })}

              {house === 1 && (
                <text
                  x={x}
                  y={y + 44}
                  textAnchor="middle"
                  style={{ fill: "rgba(184,134,11,0.9)", fontSize: 10, letterSpacing: 2.5, fontWeight: 700 }}
                >
                  LAGNA
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
