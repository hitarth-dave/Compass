import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Briefcase, Rocket, Plane, Heart, GraduationCap, TrendingUp, HeartPulse,
  Loader2, CalendarClock, ChevronLeft, Sparkles, AlertTriangle,
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

// Colors below use the theme's CSS custom properties (via Tailwind's
// arbitrary-value + opacity-modifier syntax, e.g. text-[color:var(--x)]/40)
// rather than fixed hex, so they stay legible in both light and dark mode —
// --jai-green-deep, --jai-gold and --jai-terracotta all flip to lighter,
// higher-contrast values under .dark (see index.css).
function scoreLabel(score) {
  if (score >= 80) return { text: "Strongly favorable", colorClass: "text-[color:var(--jai-green-deep)]" };
  if (score >= 60) return { text: "Favorable", colorClass: "text-[color:var(--jai-gold)]" };
  return { text: "Mixed", colorClass: "text-[color:var(--jai-terracotta)]" };
}

const QUALITY_STYLE = {
  good: { bgClass: "bg-[color:var(--jai-green-deep)]/10", textClass: "text-[color:var(--jai-green-deep)]", label: "Good" },
  neutral: { bgClass: "bg-[color:var(--jai-gold)]/10", textClass: "text-[color:var(--jai-gold)]", label: "Neutral" },
  bad: { bgClass: "bg-[color:var(--jai-terracotta)]/10", textClass: "text-[color:var(--jai-terracotta)]", label: "Avoid" },
};

function TimeChip({ label, start, end, colorClass }) {
  return (
    <div className="card-surface p-4" data-testid={`muhurta-chip-${label.toLowerCase().replace(/\s/g, "-")}`}>
      <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">{label}</div>
      <div className={`font-serif-display text-lg mt-1 ${colorClass}`}>{start} – {end}</div>
    </div>
  );
}

function ChoghadiyaRow({ segments }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {segments.map((s, i) => {
        const st = QUALITY_STYLE[s.quality];
        return (
          <div key={i} className={`rounded-lg px-3 py-2 ${st.bgClass}`} data-testid={`choghadiya-${s.start}`}>
            <div className={`text-[9px] uppercase tracking-widest ${st.textClass}`}>{st.label}</div>
            <div className={`font-serif-display text-sm mt-0.5 ${st.textClass}`}>{s.name}</div>
            <div className="text-[10px] text-[color:var(--jai-text-muted)] mt-0.5">{s.start} – {s.end}</div>
          </div>
        );
      })}
    </div>
  );
}

export default function Muhurta() {
  const { isAdvanced } = useDisplayMode();

  // Today's Panchang / daily muhurta
  const [today, setToday] = useState(null);
  const [todayLoading, setTodayLoading] = useState(true);

  // Decision-timing scanner (secondary — for planning weeks/months ahead)
  const [planOpen, setPlanOpen] = useState(false);
  const [activity, setActivity] = useState(null);
  const [loading, setLoading] = useState(false);
  const [windows, setWindows] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get(`${API}/muhurta/today`);
        setToday(res.data);
      } catch (e) {
        toast.error(e.response?.data?.detail || "Could not load today's Panchang");
      } finally {
        setTodayLoading(false);
      }
    })();
  }, []);

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

  const backToActivities = () => {
    setActivity(null);
    setWindows(null);
  };

  const activityMeta = ACTIVITIES.find((a) => a.key === activity);

  return (
    <div className="max-w-5xl mx-auto px-6 lg:px-12 py-12" data-testid="muhurta-page">
      <div className="mb-10 fade-up">
        <div className="overline mb-3">Panchang &amp; Muhurta</div>
        <h1 className="font-serif-display text-4xl sm:text-5xl leading-[0.95] text-[color:var(--jai-parchment)]">
          Today's <em className="text-[color:var(--jai-gold)]">auspicious windows</em>.
        </h1>
        {today && (
          <p className="mt-4 text-[color:var(--jai-text-muted)]">
            {today.date} · {today.panchang.vara} · {today.panchang.tithi} ({today.panchang.paksha} Paksha)
            {isAdvanced && <> · {today.panchang.karana} Karana · {today.panchang.yoga} Yoga</>}
          </p>
        )}
      </div>

      {todayLoading && (
        <div className="flex items-center gap-2 text-[color:var(--jai-text-muted)] fade-up" data-testid="muhurta-today-loading">
          <Loader2 size={16} className="animate-spin" /> Computing today's Panchang…
        </div>
      )}

      {today && (
        <div className="fade-up delay-1 space-y-8">
          {/* Sunrise / sunset + Abhijit */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <TimeChip label="Sunrise" start={today.sunrise} end="" colorClass="text-[color:var(--jai-gold)]" />
            <TimeChip label="Abhijit Muhurta" start={today.abhijit_muhurta.start} end={today.abhijit_muhurta.end} colorClass="text-[color:var(--jai-green-deep)]" />
            <TimeChip label="Rahu Kaal" start={today.rahu_kaal.start} end={today.rahu_kaal.end} colorClass="text-[color:var(--jai-terracotta)]" />
            <TimeChip label="Sunset" start={today.sunset} end="" colorClass="text-[color:var(--jai-gold)]" />
          </div>

          {isAdvanced && (
            <div className="grid grid-cols-2 gap-4 max-w-md">
              <TimeChip label="Yamaganda Kaal" start={today.yamaganda_kaal.start} end={today.yamaganda_kaal.end} colorClass="text-[color:var(--jai-terracotta)]" />
              <TimeChip label="Gulika Kaal" start={today.gulika_kaal.start} end={today.gulika_kaal.end} colorClass="text-[color:var(--jai-terracotta)]" />
            </div>
          )}

          {/* Choghadiya timeline */}
          <div>
            <div className="overline mb-3">Choghadiya · Day</div>
            <ChoghadiyaRow segments={today.choghadiya_day} />
          </div>
          <div>
            <div className="overline mb-3">Choghadiya · Night</div>
            <ChoghadiyaRow segments={today.choghadiya_night} />
          </div>

          {today.panchang.cautions?.length > 0 && (
            <div className="card-surface p-5 flex gap-3 items-start" data-testid="panchang-cautions">
              <AlertTriangle size={16} className="text-[color:var(--jai-terracotta)] shrink-0 mt-0.5" />
              <div className="text-sm text-[color:var(--jai-text-muted)] space-y-1">
                {today.panchang.cautions.map((c, i) => <div key={i}>{c}</div>)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Secondary: plan a bigger decision weeks/months ahead */}
      <div className="mt-16 pt-10 border-t border-[color:var(--jai-border)] fade-up delay-2">
        <button
          onClick={() => setPlanOpen((v) => !v)}
          className="flex items-center gap-2 text-sm text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)]"
          data-testid="muhurta-plan-toggle"
        >
          <Sparkles size={14} className="text-[color:var(--jai-gold)]" />
          Planning something bigger? Scan the next 6 months for the best window.
        </button>

        {planOpen && (
          <div className="mt-6">
            {!activity && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
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
              <div>
                <button
                  onClick={backToActivities}
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
                              <div className={`font-serif-display text-xl ${sl.colorClass}`}>
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
        )}
      </div>
    </div>
  );
}
