import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Briefcase, Rocket, Plane, Heart, GraduationCap, TrendingUp, HeartPulse,
  Loader2, CalendarClock, ChevronLeft, ChevronRight, Sparkles, AlertTriangle,
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

// Colors below use the theme's CSS custom properties rather than fixed
// hex, so they stay legible in both light and dark mode — --jai-green-deep,
// --jai-gold and --jai-terracotta all flip to lighter, higher-contrast
// values under .dark (see index.css). The tint backgrounds use dedicated
// --jai-tint-* variables (baked-in alpha per theme) rather than Tailwind's
// opacity-modifier syntax on an arbitrary var, which turned out to render
// as essentially invisible — this is the fix for that.
function scoreLabel(score) {
  if (score >= 80) return { text: "Strongly favorable", colorClass: "text-[color:var(--jai-green-deep)]" };
  if (score >= 60) return { text: "Favorable", colorClass: "text-[color:var(--jai-gold)]" };
  return { text: "Mixed", colorClass: "text-[color:var(--jai-terracotta)]" };
}

const QUALITY_STYLE = {
  good: { bgVar: "var(--jai-tint-good)", textClass: "text-[color:var(--jai-green-deep)]", label: "Good" },
  neutral: { bgVar: "var(--jai-tint-neutral)", textClass: "text-[color:var(--jai-gold)]", label: "Neutral" },
  bad: { bgVar: "var(--jai-tint-bad)", textClass: "text-[color:var(--jai-terracotta)]", label: "Avoid" },
};

/** "HH:MM" -> minutes since midnight. */
function toMinutes(hhmm) {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
}

/** Handles ranges that cross midnight (night Choghadiya segments do). */
function isNow(nowMin, start, end) {
  if (nowMin == null || nowMin < 0) return false;
  const s = toMinutes(start);
  const e = toMinutes(end);
  return e > s ? nowMin >= s && nowMin < e : nowMin >= s || nowMin < e;
}

function TimeChip({ label, start, end, colorClass, active }) {
  return (
    <div
      className={`card-surface p-4 relative ${active ? "ring-2 ring-[color:var(--jai-gold)]" : ""}`}
      data-testid={`muhurta-chip-${label.toLowerCase().replace(/\s/g, "-")}`}
    >
      {active && (
        <span className="absolute -top-2 -right-2 text-[9px] font-semibold uppercase tracking-widest px-2 py-0.5 rounded-full bg-[color:var(--jai-gold)] text-[color:var(--jai-surface)]">
          Now
        </span>
      )}
      <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">{label}</div>
      <div className={`font-serif-display text-lg mt-1 ${colorClass}`}>{start} – {end}</div>
    </div>
  );
}

function ChoghadiyaRow({ segments, nowMin }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
      {segments.map((s, i) => {
        const st = QUALITY_STYLE[s.quality];
        const active = isNow(nowMin, s.start, s.end);
        return (
          <div
            key={i}
            className={`relative rounded-lg px-3 py-2 ${active ? "ring-2 ring-[color:var(--jai-gold)]" : ""}`}
            style={{ background: st.bgVar }}
            data-testid={`choghadiya-${s.start}`}
          >
            {active && (
              <span className="absolute -top-1.5 -right-1.5 text-[8px] font-semibold uppercase tracking-widest px-1.5 py-0.5 rounded-full bg-[color:var(--jai-gold)] text-[color:var(--jai-surface)]">
                Now
              </span>
            )}
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
  // 0 = today, 1 = tomorrow — Advanced-only ("peek at tomorrow"). Basic
  // mode never leaves 0, and the arrow to change it isn't shown there.
  const [dayOffset, setDayOffset] = useState(0);

  // Current time-of-day, in minutes since midnight — used to highlight
  // whichever Rahu Kaal / Abhijit / Choghadiya slot is happening right now.
  // Assumes the browser's own clock matches the location the Panchang was
  // computed for (true for the overwhelming majority of visits — someone
  // checking today's Muhurta is checking it from where they are).
  // Re-derived every minute so the highlight moves on its own.
  const [nowMin, setNowMin] = useState(() => {
    const d = new Date();
    return d.getHours() * 60 + d.getMinutes();
  });

  // Decision-timing scanner (secondary — for planning weeks/months ahead)
  const [planOpen, setPlanOpen] = useState(false);
  const [activity, setActivity] = useState(null);
  const [loading, setLoading] = useState(false);
  const [windows, setWindows] = useState(null);

  // Basic mode can never be viewing "tomorrow" — if the user flips out of
  // Advanced while looking ahead, snap back to today.
  useEffect(() => {
    if (!isAdvanced && dayOffset !== 0) setDayOffset(0);
  }, [isAdvanced, dayOffset]);

  useEffect(() => {
    (async () => {
      setTodayLoading(true);
      try {
        const res = await axios.get(`${API}/muhurta/today`, { params: { offset_days: dayOffset } });
        setToday(res.data);
      } catch (e) {
        toast.error(e.response?.data?.detail || "Could not load the Panchang");
      } finally {
        setTodayLoading(false);
      }
    })();
  }, [dayOffset]);

  useEffect(() => {
    const id = setInterval(() => {
      const d = new Date();
      setNowMin(d.getHours() * 60 + d.getMinutes());
    }, 60000);
    return () => clearInterval(id);
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
        <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
          <div className="overline">Panchang &amp; Muhurta</div>
          {isAdvanced && (
            <div className="flex items-center gap-1" data-testid="muhurta-day-nav">
              <button
                onClick={() => setDayOffset(0)}
                disabled={dayOffset === 0}
                className="w-7 h-7 rounded-full flex items-center justify-center border border-[color:var(--jai-border)] text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)] hover:border-[color:var(--jai-gold)] disabled:opacity-30 disabled:pointer-events-none transition-colors"
                title="Today"
                data-testid="muhurta-day-today-btn"
              >
                <ChevronLeft size={14} />
              </button>
              <span className="text-xs uppercase tracking-widest text-[color:var(--jai-text-muted)] w-16 text-center">
                {dayOffset === 0 ? "Today" : "Tomorrow"}
              </span>
              <button
                onClick={() => setDayOffset(1)}
                disabled={dayOffset === 1}
                className="w-7 h-7 rounded-full flex items-center justify-center border border-[color:var(--jai-border)] text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)] hover:border-[color:var(--jai-gold)] disabled:opacity-30 disabled:pointer-events-none transition-colors"
                title="Tomorrow"
                data-testid="muhurta-day-tomorrow-btn"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          )}
        </div>
        <h1 className="font-serif-display text-4xl sm:text-5xl leading-[0.95] text-[color:var(--jai-parchment)]">
          {dayOffset === 0 ? "Today's" : "Tomorrow's"} <em className="text-[color:var(--jai-gold)]">auspicious windows</em>.
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
          <Loader2 size={16} className="animate-spin" /> Computing the Panchang…
        </div>
      )}

      {today && (
        <div className="fade-up delay-1 space-y-8">
          {/* "Now" highlighting (active={...} below) only makes sense for
              today — tomorrow hasn't happened yet, so dayOffset===0 gates
              every active check and the ChoghadiyaRow nowMin prop. */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <TimeChip label="Sunrise" start={today.sunrise} end="" colorClass="text-[color:var(--jai-gold)]" />
            <TimeChip
              label="Abhijit Muhurta" start={today.abhijit_muhurta.start} end={today.abhijit_muhurta.end}
              colorClass="text-[color:var(--jai-green-deep)]"
              active={dayOffset === 0 && isNow(nowMin, today.abhijit_muhurta.start, today.abhijit_muhurta.end)}
            />
            <TimeChip
              label="Rahu Kaal" start={today.rahu_kaal.start} end={today.rahu_kaal.end}
              colorClass="text-[color:var(--jai-terracotta)]"
              active={dayOffset === 0 && isNow(nowMin, today.rahu_kaal.start, today.rahu_kaal.end)}
            />
            <TimeChip label="Sunset" start={today.sunset} end="" colorClass="text-[color:var(--jai-gold)]" />
          </div>

          {isAdvanced && (
            <div className="grid grid-cols-2 gap-4 max-w-md">
              <TimeChip
                label="Yamaganda Kaal" start={today.yamaganda_kaal.start} end={today.yamaganda_kaal.end}
                colorClass="text-[color:var(--jai-terracotta)]"
                active={dayOffset === 0 && isNow(nowMin, today.yamaganda_kaal.start, today.yamaganda_kaal.end)}
              />
              <TimeChip
                label="Gulika Kaal" start={today.gulika_kaal.start} end={today.gulika_kaal.end}
                colorClass="text-[color:var(--jai-terracotta)]"
                active={dayOffset === 0 && isNow(nowMin, today.gulika_kaal.start, today.gulika_kaal.end)}
              />
            </div>
          )}

          {/* Choghadiya timeline */}
          <div>
            <div className="overline mb-3">Choghadiya · Day</div>
            <ChoghadiyaRow segments={today.choghadiya_day} nowMin={dayOffset === 0 ? nowMin : null} />
          </div>
          <div>
            <div className="overline mb-3">Choghadiya · Night</div>
            <ChoghadiyaRow segments={today.choghadiya_night} nowMin={dayOffset === 0 ? nowMin : null} />
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
