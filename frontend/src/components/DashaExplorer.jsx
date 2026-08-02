import { useState } from "react";
import axios from "axios";
import { Loader2, ChevronRight } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LEVEL_LABELS = ["Mahadasha", "Antardasha", "Pratyantardasha", "Sookshma Dasha", "Prana Dasha"];
const LEVEL_ABBR = ["MD", "AD", "PD", "SD", "PR"];

/**
 * Renders the Vimshottari Dasha timeline as a clickable drill-down:
 * Mahadasha -> Antardasha -> Pratyantardasha -> Sookshma Dasha -> Prana Dasha.
 * Each level reuses the same /api/dasha/subdivide endpoint, since the
 * Vimshottari subdivision math is identical at every depth.
 *
 * maxDepth caps how far a caller lets the user drill — Simple mode passes
 * 1 (Mahadasha -> Antardasha only, matching what a general user needs),
 * Advanced passes the default 4 (all the way to Prana Dasha).
 * compact shrinks the type scale for the smaller Simple-mode card.
 */
export default function DashaExplorer({ mahadashas, currentMahadasha, maxDepth = 4, compact = false }) {
  // currentMahadasha is no longer read — highlighting is now pure date-range
  // math (see isCurrentRow below), which works at every depth instead of
  // only the root level. Left in the signature so existing callers don't
  // need to change.
  // path: array of {lord, start, end, years} selected at each level so far
  const [path, setPath] = useState([]);
  // childrenByLevel[i] = the list of sub-periods shown at depth i+1 (i.e. children of path[i])
  const [childrenByLevel, setChildrenByLevel] = useState([]);
  const [loadingIdx, setLoadingIdx] = useState(null); // index of the row currently being expanded

  const currentList = path.length === 0 ? mahadashas : childrenByLevel[path.length - 1] || [];
  const depth = path.length;

  /** Backend dates are "YYYY-MM-DD HH:MM:SS" civil timestamps — swap the
   * space for "T" so the browser parses them reliably. */
  function parseDashaDate(str) {
    return new Date(str.replace(" ", "T"));
  }

  // Highlights whichever row's [start, end) window actually contains this
  // moment — checked purely by date, at whatever depth is on screen. The
  // old version only ever compared depth 0 against a passed-in prop, so
  // Antardasha/Pratyantardasha/Sookshma/Prana could never highlight even
  // though those are exactly the levels someone drills down to see "today".
  const now = new Date();
  const isCurrentRow = (d) => {
    const start = parseDashaDate(d.start);
    const end = parseDashaDate(d.end);
    return now >= start && now < end;
  };

  /** Backend returns full "YYYY-MM-DD HH:MM:SS" timestamps (needed so Prana-
   * level sub-day periods stay distinct). Higher levels span months/years so
   * showing the time-of-day is just noise; only the deepest level reachable
   * here is worth showing time for. */
  function formatDashaDate(str, atDepth) {
    const [datePart, timePart] = str.split(" ");
    if (atDepth < maxDepth || !timePart) return datePart;
    return `${datePart} ${timePart.slice(0, 5)}`;
  }

  async function drillInto(node, idx) {
    if (depth >= maxDepth) return; // deepest level this instance allows — nothing further
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

  const lordSize = compact ? "text-sm" : "text-lg";
  const rowPad = compact ? "px-2.5 py-1.5" : "px-3 py-2";
  const dateSize = compact ? "text-[10px]" : "text-xs";
  const listMaxH = compact ? "max-h-[260px]" : "max-h-[480px]";

  return (
    <div data-testid="dasha-explorer">
      {/* Breadcrumb */}
      <div className={`flex items-center flex-wrap gap-1 mb-4 ${compact ? "text-[10px]" : "text-xs"}`}>
        <button
          onClick={() => jumpTo(-1)}
          className={`px-2 py-1 rounded transition-colors ${depth === 0 ? "text-[color:var(--jai-gold-soft)]" : "text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold-soft)]"}`}
        >
          Vimshottari
        </button>
        {path.map((node, i) => (
          <span key={i} className="flex items-center gap-1">
            <ChevronRight size={compact ? 10 : 12} className="text-[color:var(--jai-text-muted)]/50" />
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
        {LEVEL_LABELS[depth]}{depth < maxDepth ? " — click a period to drill deeper" : ""}
      </div>

      <div className={`space-y-1 ${listMaxH} overflow-y-auto pr-1`}>
        {currentList.map((d, i) => {
          const clickable = depth < maxDepth;
          const highlighted = isCurrentRow(d);
          return (
            <div
              key={i}
              onClick={() => clickable && drillInto(d, i)}
              className={`${rowPad} rounded flex justify-between items-baseline transition-colors ${
                highlighted ? "bg-[color:var(--jai-gold)]/10 border border-[color:var(--jai-gold)]/40" : ""
              } ${clickable ? "cursor-pointer hover:bg-[color:var(--jai-gold)]/5" : ""}`}
              data-testid={`dasha-row-${depth}-${i}`}
            >
              <div>
                <div className={`font-serif-display ${lordSize} flex items-center gap-2 ${highlighted ? "text-[color:var(--jai-gold-soft)]" : "text-[color:var(--jai-parchment)]"}`}>
                  {d.lord}
                  {loadingIdx === i && <Loader2 size={12} className="animate-spin text-[color:var(--jai-text-muted)]" />}
                  {clickable && loadingIdx !== i && <ChevronRight size={12} className="text-[color:var(--jai-text-muted)]/40" />}
                </div>
                <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">{d.years} yrs</div>
              </div>
              <div className={`${dateSize} text-[color:var(--jai-text-muted)] text-right`}>
                {formatDashaDate(d.start, depth)}<br />{formatDashaDate(d.end, depth)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
