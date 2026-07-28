import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { MapPin, Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const MIN_QUERY_LENGTH = 3;
const DEBOUNCE_MS = 400;

/**
 * Type-ahead location picker. Calls the backend /geocode endpoint (Nominatim)
 * on a debounce and shows every match in a dropdown so the person can pick
 * the right "Ahmednagar" out of several candidates instead of silently
 * getting whichever one the geocoder liked best.
 *
 * Controlled: the parent owns `value` (the free-text query). This component
 * only renders the dropdown and reports back the chosen candidate.
 */
export default function LocationAutocomplete({
  value,
  onQueryChange,
  onSelect,
  placeholder = "City, Country",
  inputTestId = "location-autocomplete-input",
}) {
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errored, setErrored] = useState(false);
  const wrapRef = useRef(null);
  const debounceRef = useRef(null);
  const requestSeq = useRef(0);

  // Close the dropdown on outside click.
  useEffect(() => {
    function onDocClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  // Debounced search as the person types.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const q = (value || "").trim();

    if (q.length < MIN_QUERY_LENGTH) {
      setResults([]);
      setLoading(false);
      setErrored(false);
      return;
    }

    setLoading(true);
    setErrored(false);
    const seq = ++requestSeq.current;

    debounceRef.current = setTimeout(async () => {
      try {
        const res = await axios.get(`${API}/geocode`, { params: { q } });
        if (seq !== requestSeq.current) return; // stale response, a newer query is in flight
        setResults(res.data.results || []);
        setErrored(!!res.data.error && !(res.data.results || []).length);
        setOpen(true);
      } catch {
        if (seq !== requestSeq.current) return;
        setResults([]);
        setErrored(true);
      } finally {
        if (seq === requestSeq.current) setLoading(false);
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(debounceRef.current);
  }, [value]);

  const pick = (r) => {
    onSelect(r);
    setOpen(false);
    setResults([]);
  };

  const q = (value || "").trim();
  const showEmptyState = open && !loading && q.length >= MIN_QUERY_LENGTH && results.length === 0;

  return (
    <div ref={wrapRef} className="relative w-full">
      <div className="flex items-end gap-3 border-b border-[color:var(--jai-border)] pb-1">
        <MapPin size={16} className="text-[color:var(--jai-gold)] mb-3 shrink-0" />
        <input
          value={value}
          onChange={(e) => onQueryChange(e.target.value)}
          onFocus={() => results.length && setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              if (results[0]) pick(results[0]);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          placeholder={placeholder}
          autoComplete="off"
          className="flex-1 bg-transparent border-0 rounded-none px-0 text-lg font-serif-display placeholder:text-[color:var(--jai-text-muted)]/60 focus-visible:ring-0 focus:outline-none"
          data-testid={inputTestId}
        />
        {loading && <Loader2 size={14} className="animate-spin text-[color:var(--jai-gold)] mb-3 shrink-0" />}
      </div>

      {open && results.length > 0 && (
        <div
          className="absolute z-30 mt-1 w-full max-h-64 overflow-y-auto rounded-lg border border-[color:var(--jai-border)] bg-[color:var(--jai-surface)] shadow-lg"
          data-testid="location-autocomplete-list"
        >
          {results.map((r, i) => (
            <button
              key={`${r.lat}-${r.lon}-${i}`}
              type="button"
              onClick={() => pick(r)}
              className="w-full text-left px-4 py-2.5 text-sm text-[color:var(--jai-green-deep)] hover:bg-[color:var(--jai-surface-2)] border-b border-[color:var(--jai-border)] last:border-0 transition-colors"
              data-testid={`location-option-${i}`}
            >
              {r.place}
            </button>
          ))}
        </div>
      )}

      {showEmptyState && (
        <div
          className="absolute z-30 mt-1 w-full rounded-lg border border-[color:var(--jai-border)] bg-[color:var(--jai-surface)] shadow-lg px-4 py-2.5 text-sm text-[color:var(--jai-text-muted)]"
          data-testid="location-autocomplete-empty"
        >
          {errored ? "Search failed — try again" : "No matches — try adding country or state"}
        </div>
      )}
    </div>
  );
}
