import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Briefcase, Rocket, Plane, Heart, GraduationCap, TrendingUp, HeartPulse,
  Loader2, CalendarClock, ChevronLeft,
} from "lucide-react";
import { useDisplayMode } from "@/context/DisplayModeContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Keys must match ACTIVITY_HOUSES in backend/muhurta.py exactly — the
// endpoint 400s on anything else.
const ACTIVITIES = [
  { key: "career_change", label: "Career change", Icon: Briefcase },
  { key: "start_business", label: "Starting a business", Icon: Rocket },
  { key: "relocation_travel", label: "Relocation or travel", Icon: Plane },
  { key: "marriage", label: "Marriage", Icon: Heart },
  { key: "education", label: "Education", Icon: GraduationCap },
  { key: "financial_investment", label: "Financial investment", Icon: TrendingUp },
  { key: "health_decision", label: "Health decision", Icon: HeartPulse },
];

function scoreLabel(score) {
  if (score >= 80) return { text: "Strongly favorable", color: "#0F5132" };
  if (score >= 60) return { text: "Favorable", color: "#B8860B" };
  return { text: "Mixed", color: "#A0522D" };
}

export default function Muhurta() {
  const { isAdvanced } = useDisplayMode();
  const [activity, setActivity] = useState(null);
  const [loading, setLoading] = useState(false);
  const [windows, setWindows] = useState(null);

  const choose = async (key) => {
    setActivity(key);
    setLoading(true);
    setWindows(null);
    try {
      const res = await axios.get(`${API}/decision-timing/${key}`);
      setWindows(res.data.windows || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not compute timing windows");
      setActivity(null);
    } finally {
      setLoading(false);
    }
  };

  const back = () => {
    setActivity(null);
    setWindows(null);
  };

  const activityMeta = ACTIVITIES.find((a) => a.key === activity);

  return (
    <div className="max-w-5xl mx-auto px-6 lg:px-12 py-12" data-testid="muhurta-page">
      <div className="mb-10 fade-up">
        <div className="overline mb-3">Muhurta</div>
        <h1 className="font-serif-display text-4xl sm:text-5xl leading-[0.95] text-[color:var(--jai-parchment)]">
          When is a <em className="text-[color:var(--jai-gold)]">good time</em> to act?
        </h1>
        <p className="mt-4 text-[color:var(--jai-text-muted)] max-w-2xl">
          Pick what you're deciding on, and Compass Astro scans the next six months of your chart —
          Dasha, transits{isAdvanced ? " and Panchang" : ""} — for the windows most supportive of it.
        </p>
      </div>

      {!activity && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 fade-up delay-1">
          {ACTIVITIES.map(({ key, label, Icon }) => (
            <button
              key={key}
              onClick={() => choose(key)}
              className="card-surface p-6 text-left hover:border-[color:var(--jai-gold)] transition-colors"
              data-testid={`muhurta-activity-${key}`}
            >
              <Icon size={20} className="text-[color:var(--jai-gold)] mb-4" />
              <div className="font-serif-display text-lg text-[color:var(--jai-green-deep)]">{label}</div>
            </button>
          ))}
        </div>
      )}

      {activity && (
        <div className="fade-up delay-1">
          <button
            onClick={back}
            className="mb-6 inline-flex items-center gap-1.5 text-xs uppercase tracking-widest text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)]"
            data-testid="muhurta-back-btn"
          >
            <ChevronLeft size={14} /> Choose a different decision
          </button>

          <div className="flex items-center gap-3 mb-8">
            {activityMeta && <activityMeta.Icon size={22} className="text-[color:var(--jai-gold)]" />}
            <div className="font-serif-display text-2xl text-[color:var(--jai-parchment)]">{activityMeta?.label}</div>
          </div>

          {loading && (
            <div className="flex items-center gap-2 text-[color:var(--jai-text-muted)]" data-testid="muhurta-loading">
              <Loader2 size={16} className="animate-spin" /> Scanning the next six months…
            </div>
          )}

          {!loading && windows && windows.length === 0 && (
            <div className="card-surface p-8 text-center" data-testid="muhurta-empty">
              <CalendarClock size={22} className="text-[color:var(--jai-gold)] mx-auto mb-3" />
              <p className="text-[color:var(--jai-text-muted)]">
                No strongly favorable window in the next six months — timing here isn't clear-cut.
                Ask Compass Astro directly in Chat for a more nuanced read.
              </p>
            </div>
          )}

          {!loading && windows && windows.length > 0 && (
            <div className="space-y-5" data-testid="muhurta-windows">
              {windows.map((w, i) => {
                const sl = scoreLabel(w.avg_score);
                return (
                  <div key={i} className="card-surface p-6 sm:p-8" data-testid={`muhurta-window-${i}`}>
                    <div className="flex items-start justify-between flex-wrap gap-4">
                      <div>
                        <div className="overline mb-2">Window {i + 1}</div>
                        <div className="font-serif-display text-2xl text-[color:var(--jai-parchment)]">
                          {w.start_date} → {w.end_date}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">
                          {isAdvanced ? "Score" : ""}
                        </div>
                        <div className="font-serif-display text-xl" style={{ color: sl.color }}>
                          {sl.text}{isAdvanced ? ` · ${w.avg_score}/100` : ""}
                        </div>
                      </div>
                    </div>

                    {isAdvanced && (
                      <>
                        {w.panchang_at_start && (
                          <div className="mt-5 text-xs text-[color:var(--jai-text-muted)] flex flex-wrap gap-x-4 gap-y-1">
                            <span>Tithi: <span className="text-[color:var(--jai-green-deep)]">{w.panchang_at_start.tithi} ({w.panchang_at_start.paksha})</span></span>
                            <span>Karana: <span className="text-[color:var(--jai-green-deep)]">{w.panchang_at_start.karana}</span></span>
                            <span>Yoga: <span className="text-[color:var(--jai-green-deep)]">{w.panchang_at_start.yoga}</span></span>
                            <span>Vara: <span className="text-[color:var(--jai-green-deep)]">{w.panchang_at_start.vara}</span></span>
                          </div>
                        )}
                        {w.reasons?.length > 0 && (
                          <ul className="mt-5 space-y-1.5">
                            {w.reasons.map((r, j) => (
                              <li key={j} className="text-sm text-[color:var(--jai-text-muted)] flex gap-2">
                                <span className="text-[color:var(--jai-gold)]">·</span> {r}
                              </li>
                            ))}
                          </ul>
                        )}
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
