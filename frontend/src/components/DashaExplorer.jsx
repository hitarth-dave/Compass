import { useState } from "react";
import axios from "axios";
import { Loader2, ChevronRight } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LEVEL_LABELS = ["Mahadasha", "Antardasha", "Pratyantardasha", "Sookshma Dasha", "Prana Dasha"];
const LEVEL_ABBR = ["MD", "AD", "PD", "SD", "PR"];
const MAX_DEPTH = 4; // 0=Maha, 1=Antar, 2=Pratyantar, 3=Sookshma, 4=Prana (leaf, not clickable further)

/**
 * Renders the Vimshottari Dasha timeline as a clickable drill-down:
 * Mahadasha -> Antardasha -> Pratyantardasha -> Sookshma Dasha.
 * Each level reuses the same /api/dasha/subdivide endpoint, since the
 * Vimshottari subdivision math is identical at every depth.
 */
export default function DashaExplorer({ mahadashas, currentMahadasha }) {
  // path: array of {lord, start, end, years} selected at each level so far
  const [path, setPath] = useState([]);
  // childrenByLevel[i] = the list of sub-periods shown at depth i+1 (i.e. children of path[i])
  const [childrenByLevel, setChildrenByLevel] = useState([]);
  const [loadingIdx, setLoadingIdx] = useState(null); // index of the row currently being expanded

  const currentList = path.length === 0 ? mahadashas : childrenByLevel[path.length - 1] || [];
  const depth = path.length;

  const isCurrentRow = (d) => {
    if (depth !== 0 || !currentMahadasha) return false;
    return d.lord === currentMahadasha.lord && d.start === currentMahadasha.start;
  };

  async function drillInto(node, idx) {
    if (depth >= MAX_DEPTH) return; // Prana is the deepest level, nothing further
    setLoadingIdx(idx);
    try {
      const res = await axios.post(`${API}/dasha/subdivide`, {
        lord: node.lord,
        start: node.start,
        years: node.years,
      });
      const newPath = [...path, node];
      const newChildren = [...childrenByLevel.slice(0, path.length), res.data.subs];
      setPath(newPath);
      setChildrenByLevel(newChildren);
    } catch (e) {
      // Silently keep the user where they were rather than breaking the view
      console.error("Failed to load dasha subdivision", e);
    } finally {
      setLoadingIdx(null);
    }
  }

  function jumpTo(levelIdx) {
    // levelIdx = -1 means back to the root Mahadasha list
    if (levelIdx < 0) {
      setPath([]);
      setChildrenByLevel([]);
    } else {
      setPath(path.slice(0, levelIdx + 1));
      setChildrenByLevel(childrenByLevel.slice(0, levelIdx + 1));
    }
  }

  return (
    <div data-testid="dasha-explorer">
      {/* Breadcrumb */}
      <div className="flex items-center flex-wrap gap-1 mb-4 text-xs">
        <button
          onClick={() => jumpTo(-1)}
          className={`px-2 py-1 rounded transition-colors ${depth === 0 ? "text-[color:var(--jai-gold-soft)]" : "text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold-soft)]"}`}
        >
          Vimshottari
        </button>
        {path.map((node, i) => (
          <span key={i} className="flex items-center gap-1">
            <ChevronRight size={12} className="text-[color:var(--jai-text-muted)]/50" />
            <button
              onClick={() => jumpTo(i)}
              className={`px-2 py-1 rounded transition-colors ${i === path.length - 1 ? "text-[color:var(--jai-gold-soft)]" : "text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold-soft)]"}`}
            >
              {node.lord} <span className="opacity-60">({LEVEL_ABBR[i]})</span>
            </button>
          </span>
        ))}
      </div>

      <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]/70 mb-2">
        {LEVEL_LABELS[depth]}{depth < MAX_DEPTH ? " — click a period to drill deeper" : ""}
      </div>

      <div className="space-y-1 max-h-80 overflow-y-auto pr-1">
        {currentList.map((d, i) => {
          const clickable = depth < MAX_DEPTH;
          const highlighted = isCurrentRow(d);
          return (
            <div
              key={i}
              onClick={() => clickable && drillInto(d, i)}
              className={`px-3 py-2 rounded flex justify-between items-baseline transition-colors ${
                highlighted ? "bg-[color:var(--jai-gold)]/10 border border-[color:var(--jai-gold)]/40" : ""
              } ${clickable ? "cursor-pointer hover:bg-[color:var(--jai-gold)]/5" : ""}`}
              data-testid={`dasha-row-${depth}-${i}`}
            >
              <div>
                <div className={`font-serif-display text-lg flex items-center gap-2 ${highlighted ? "text-[color:var(--jai-gold-soft)]" : "text-[color:var(--jai-parchment)]"}`}>
                  {d.lord}
                  {loadingIdx === i && <Loader2 size={12} className="animate-spin text-[color:var(--jai-text-muted)]" />}
                  {clickable && loadingIdx !== i && <ChevronRight size={12} className="text-[color:var(--jai-text-muted)]/40" />}
                </div>
                <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">{d.years} yrs</div>
              </div>
              <div className="text-xs text-[color:var(--jai-text-muted)] text-right">
                {d.start}<br />{d.end}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
