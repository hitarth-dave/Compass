// North-Indian Kundali chart — Parashara's Light style
// Fixed house positions (1 always top-center diamond); signs rotate with Ascendant.
// Each planet shown as: 2-letter initial (+ R if retrograde) DD:MM Nakshatra-abbr
// e.g. "Ra 09:47 Swa", "MeR 20:47 Roh"

const PLANET_INITIAL = {
  Sun: "Su", Moon: "Mo", Mars: "Ma", Mercury: "Me",
  Jupiter: "Ju", Venus: "Ve", Saturn: "Sa",
  Rahu: "Ra", Ketu: "Ke",
};

const PLANET_COLOR = {
  Sun: "#B0341A",       // fiery red
  Moon: "#4A6FA5",      // silver-blue
  Mars: "#C0392B",      // red
  Mercury: "#2E7D32",   // dark green
  Jupiter: "#B8860B",   // dark gold
  Venus: "#B03060",     // magenta / maroon
  Saturn: "#3D6A8A",    // steel blue — visible on both cream and dark cards
  Rahu: "#6B3410",      // dark brown
  Ketu: "#5D6D6E",      // slate gray
};

const NAK_ABBR = {
  "Ashwini": "Ash", "Bharani": "Bha", "Krittika": "Kri", "Rohini": "Roh",
  "Mrigashira": "Mri", "Ardra": "Ard", "Punarvasu": "Pun", "Pushya": "Pus",
  "Ashlesha": "Asl", "Magha": "Mag", "Purva Phalguni": "PPh", "Uttara Phalguni": "UPh",
  "Hasta": "Has", "Chitra": "Chi", "Swati": "Swa", "Vishakha": "Vis",
  "Anuradha": "Anu", "Jyeshtha": "Jye", "Mula": "Mul", "Purva Ashadha": "PAs",
  "Uttara Ashadha": "UAs", "Shravana": "Shr", "Dhanishta": "Dha", "Shatabhisha": "Sha",
  "Purva Bhadrapada": "PBh", "Uttara Bhadrapada": "UBh", "Revati": "Rev",
};

function fmtDegMin(dec) {
  const d = Math.floor(dec);
  const m = Math.floor((dec - d) * 60);
  return `${String(d).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

const S = 560; // SVG viewBox size

// House layout: fixed positions, 1 = top-center diamond, houses go anti-clockwise.
// planet: (x, y) center of planet text stack
// num:    (x, y) small sign-number position (in outer corner of region)
const HOUSES = {
  1:  { planet: [280, 130], num: [280, 42] },     // top diamond
  2:  { planet: [155, 65],  num: [55, 20] },      // upper-left along top edge
  3:  { planet: [65, 155],  num: [20, 55] },      // left-upper along left edge
  4:  { planet: [130, 280], num: [42, 280] },     // left diamond
  5:  { planet: [65, 405],  num: [20, 505] },     // left-lower along left edge
  6:  { planet: [155, 495], num: [55, 540] },     // lower-left along bottom edge
  7:  { planet: [280, 430], num: [280, 518] },    // bottom diamond
  8:  { planet: [405, 495], num: [505, 540] },    // lower-right along bottom edge
  9:  { planet: [495, 405], num: [540, 505] },    // right-lower along right edge
  10: { planet: [430, 280], num: [518, 280] },    // right diamond
  11: { planet: [495, 155], num: [540, 55] },     // right-upper along right edge
  12: { planet: [405, 65],  num: [505, 20] },     // upper-right along top edge
};

export default function KundaliChart({ planets, ascendantSign, ascendant, showNakshatra = true, testid = "kundali-chart" }) {
  // Group planets by house
  const byHouse = {};
  planets.forEach((p) => {
    const h = p.house;
    if (!byHouse[h]) byHouse[h] = [];
    byHouse[h].push(p);
  });

  // Inject Ascendant ("As") as first entry in H1 if provided
  if (ascendant) {
    const asEntry = {
      name: "As",
      _initial: "As",
      _color: "#9C6B2E",
      degree_in_sign: ascendant.degree_in_sign,
      nakshatra: ascendant.nakshatra,
      retrograde: false,
      _isAscendant: true,
    };
    byHouse[1] = [asEntry, ...(byHouse[1] || [])];
  }

  const rashiOfHouse = (h) => ((ascendantSign + h - 1) % 12) + 1; // 1..12

  const lineHeight = 18;

  return (
    <div className="w-full flex justify-center py-2">
      <svg viewBox={`0 0 ${S} ${S}`} className="w-full max-w-2xl" data-testid={testid}>
        {/* Outer square */}
        <rect x="0" y="0" width={S} height={S} className="kundali-cell" strokeWidth="1.75" />
        {/* Two diagonals of the outer square */}
        <line x1="0" y1="0" x2={S} y2={S} className="kundali-cell" strokeWidth="1" />
        <line x1={S} y1="0" x2="0" y2={S} className="kundali-cell" strokeWidth="1" />
        {/* Inner diamond */}
        <polygon
          points={`${S / 2},0 ${S},${S / 2} ${S / 2},${S} 0,${S / 2}`}
          className="kundali-cell"
          strokeWidth="1.25"
        />

        {Object.entries(HOUSES).map(([hStr, pos]) => {
          const h = parseInt(hStr);
          const list = byHouse[h] || [];
          const [px, py] = pos.planet;
          const [nx, ny] = pos.num;
          const startY = py - ((list.length - 1) * lineHeight) / 2;

          return (
            <g key={h}>
              {/* Sign number (small, near outer edge) */}
              <text x={nx} y={ny} textAnchor="middle" className="kundali-house-num">
                {rashiOfHouse(h)}
              </text>

              {/* Planets stacked vertically at region center */}
              {list.map((p, i) => {
                const initial = p._initial || ((PLANET_INITIAL[p.name] || p.name.slice(0, 2)) + (p.retrograde ? "R" : ""));
                const color = p._color || PLANET_COLOR[p.name] || "#8B6F47";
                const yy = startY + i * lineHeight;
                const nak = showNakshatra && p.nakshatra ? (NAK_ABBR[p.nakshatra] || p.nakshatra.slice(0, 3)) : "";
                return (
                  <text
                    key={p.name}
                    x={px}
                    y={yy}
                    textAnchor="middle"
                    className="kundali-planet"
                    style={{ fill: color }}
                  >
                    <tspan style={{ fontWeight: 700 }}>{initial}</tspan>
                    <tspan dx="4">{fmtDegMin(p.degree_in_sign)}</tspan>
                    {nak && <tspan dx="4" style={{ opacity: 0.85 }}>{nak}</tspan>}
                  </text>
                );
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
