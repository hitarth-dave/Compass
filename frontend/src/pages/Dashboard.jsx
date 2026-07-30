import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, MoveRight, ChevronDown, Info, Download, Lock } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import KundaliChart from "@/components/KundaliChart";
import DashaExplorer from "@/components/DashaExplorer";
import WhyPanel from "@/components/WhyPanel";
import { useDisplayMode } from "@/context/DisplayModeContext";
import { useAuth } from "@/context/AuthContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Safety net for birth places saved before the geocode fix, which stored the
// full Nominatim address (house/road/taluka/postal code and all). New
// selections already save a clean "City, State, Country" label — this just
// keeps old profiles from showing the long form until they re-save it.
function shortenPlace(full) {
  if (!full) return full;
  const parts = full.split(",").map((s) => s.trim()).filter(Boolean);
  if (parts.length <= 3) return parts.join(", ");
  const meaningful = parts.filter((p) => !/^\d[\d\s-]*$/.test(p)); // drop bare postal codes
  return meaningful.slice(-3).join(", ");
}

// Short, deterministic one-liners keyed by where transiting Moon sits from
// Lagna today — purely derived from data already on the page (no extra API
// call), just enough to fill the header space with something useful rather
// than blank air.
const MOON_TRANSIT_NOTE = {
  1: "Moon is transiting your own Lagna today — expect heightened emotional visibility.",
  2: "Moon is moving through your 2nd house — a good day for finances and family conversations.",
  3: "Moon is in your 3rd house — courage and communication are favored today.",
  4: "Moon is transiting your 4th house — home and inner peace take center stage today.",
  5: "Moon is in your 5th house — creativity and romance get a gentle boost today.",
  6: "Moon is moving through your 6th house — a productive day for routine and resolving conflicts.",
  7: "Moon is transiting your 7th house — partnerships and one-on-one connections are highlighted.",
  8: "Moon is in your 8th house — a more introspective, low-key day is likely.",
  9: "Moon is transiting your 9th house — good day for learning, travel, or seeking guidance.",
  10: "Moon is in your 10th house — career visibility and public matters are in focus today.",
  11: "Moon is moving through your 11th house — favorable for gains, networking, and social plans.",
  12: "Moon is transiting your 12th house — a quieter day suited for rest and reflection.",
};

function todaysTransitNote(transits) {
  const moon = transits.planets.find((p) => p.name === "Moon");
  if (!moon || !moon.house_from_lagna) return null;
  return MOON_TRANSIT_NOTE[moon.house_from_lagna] || null;
}

// Chandra Kundali (Moon chart) — same natal planets, houses recomputed
// with the Moon's sign as the 1st house instead of the Lagna's. Purely
// derived from data already on the page, no extra API call needed.
function buildMoonChart(planets) {
  const moon = planets.find((p) => p.name === "Moon");
  if (!moon) return null;
  return {
    ascendant: { sign_idx: moon.sign_idx, sign_en: moon.sign_en },
    planets: planets.map((p) => ({
      ...p,
      house: ((p.sign_idx - moon.sign_idx + 12) % 12) + 1,
    })),
  };
}

// Benefic/malefic badge — reused on the Natal Planets card. Uses the same
// tint variables Muhurta uses (baked-in alpha, dark-mode safe) rather than
// fixed hex, so this doesn't reintroduce the dark-mode legibility bug.
function NatureBadge({ label, nature, title }) {
  const isBenefic = nature === "benefic";
  return (
    <span
      className="text-[9px] font-bold px-1 rounded leading-none py-0.5"
      style={{
        color: isBenefic ? "var(--jai-green-deep)" : "var(--jai-terracotta)",
        background: isBenefic ? "var(--jai-tint-good)" : "var(--jai-tint-bad)",
      }}
      title={title}
    >
      {label}
    </span>
  );
}

// Antardasha/Pratyantardasha now carry full "YYYY-MM-DD HH:MM:SS" timestamps
// (needed for Sookshma/Prana precision elsewhere); this strip only needs the date.
const dateOnly = (str) => (str ? str.split(" ")[0] : str);

export default function Dashboard() {
  const navigate = useNavigate();
  const { isAdvanced } = useDisplayMode();
  const { user } = useAuth();
  const hasAdvancedPlan = user?.plan === "advanced";
  const [chart, setChart] = useState(null);
  const [transits, setTransits] = useState(null);
  const [loading, setLoading] = useState(true);
  // Controls whether Transit / Moon / D9 charts are shown alongside D1,
  // or collapsed so D1 can take the spotlight.
  const [showAll, setShowAll] = useState(true);
  // Additional Divisional Charts: collapsed shows only D10; expanded shows
  // D10 plus every other extra varga (D2/D4/D6/D7/D16/D24/D60).
  const [showAllVargas, setShowAllVargas] = useState(false);
  const [yogaWhy, setYogaWhy] = useState(null); // { name, detail, citations, loading, error }
  const [downloadingCard, setDownloadingCard] = useState(false);

  const downloadShareCard = async () => {
    if (!hasAdvancedPlan) {
      toast.message("The chart card is an Advanced-tier feature", {
        description: "Join the Advanced waitlist to unlock it.",
      });
      navigate("/pricing");
      return;
    }
    setDownloadingCard(true);
    try {
      const res = await axios.get(`${API}/profile/share-card`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "image/png" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${(chart?.profile?.name || "compass-astro").replace(/\s+/g, "-")}-compass-astro-chart.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      if (err?.response?.status === 403) {
        toast.message("The chart card is an Advanced-tier feature", {
          description: "Join the Advanced waitlist to unlock it.",
        });
        navigate("/pricing");
      } else {
        toast.error("Could not generate your share card — try again in a moment.");
      }
    } finally {
      setDownloadingCard(false);
    }
  };

  const openYogaWhy = async (y) => {
    setYogaWhy({ name: y.name, detail: y.detail, citations: [], loading: true, error: false });
    try {
      const res = await axios.get(`${API}/yogas/citations`, { params: { name: y.name } });
      setYogaWhy({ name: y.name, detail: y.detail, citations: res.data.citations || [], loading: false, error: false });
    } catch {
      // Distinct from a genuine empty result — a failed request (network,
      // 404, backend down) should never read as "we checked and found
      // nothing," or a future outage quietly looks like missing scholarship.
      setYogaWhy({ name: y.name, detail: y.detail, citations: [], loading: false, error: true });
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const [c, t] = await Promise.all([
          axios.get(`${API}/profile/chart`),
          axios.get(`${API}/transits`),
        ]);
        setChart(c.data);
        setTransits(t.data);
      } catch (e) {
        if (e.response?.status === 404) {
          navigate("/onboarding", { replace: true });
          return;
        }
        toast.error("Could not load your chart");
      } finally {
        setLoading(false);
      }
    })();
  }, [navigate]);

  if (loading) {
    return <ChartLoadingState />;
  }

  if (!chart) return null;

  const asc = chart.ascendant;
  const dasha = chart.current_dasha;
  const antar = chart.current_antardasha;
  const pratyantar = chart.current_pratyantardasha;
  const navamsa = chart.navamsa;
  const dasamsa = chart.dasamsa;
  const houseLords = chart.house_lords || [];
  const yogas = chart.yogas || [];
  const moonChart = buildMoonChart(chart.planets);

  return (
    <div className="max-w-7xl mx-auto px-8 py-12" data-testid="dashboard-page">
      <div className="mb-12 flex items-end justify-between gap-6 flex-wrap fade-up">
        <div>
          <div className="overline mb-4">Namaste · Your Vedic Chart</div>
          <h1 className="font-serif-display text-5xl sm:text-6xl leading-[0.95] text-[color:var(--jai-parchment)]" data-testid="dashboard-title">
            {chart.profile.name}<span className="text-[color:var(--jai-gold)]">.</span>
          </h1>
          <div className="mt-3 text-[color:var(--jai-text-muted)] text-sm tracking-wide">
            {chart.profile.dob} · {chart.profile.tob}{chart.profile.tob_unknown ? " (approx.)" : ""} · {shortenPlace(chart.profile.place)} · Lagna lord: <span className="text-[color:var(--jai-green-deep)] font-semibold">{asc.lord}</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={downloadShareCard}
            disabled={downloadingCard}
            className="rounded-full px-5 py-3 font-serif-display text-base border border-[color:var(--jai-border)] text-[color:var(--jai-green-deep)] inline-flex items-center gap-2 hover:border-[color:var(--jai-gold)] hover:text-[color:var(--jai-gold)] transition-colors disabled:opacity-60"
            data-testid="download-share-card-btn"
            title={
              hasAdvancedPlan
                ? "Download a one-page image of your chart — D1 & D9, planets, strengths and yogas"
                : "Advanced-tier feature — join the waitlist to unlock it"
            }
          >
            {downloadingCard ? (
              <Loader2 size={16} className="animate-spin" />
            ) : hasAdvancedPlan ? (
              <Download size={16} />
            ) : (
              <Lock size={13} />
            )}
            {downloadingCard ? "Preparing…" : "My chart card"}
            {!hasAdvancedPlan && !downloadingCard && (
              <span className="text-[10px] tracking-wide uppercase px-2 py-0.5 rounded-full border border-[color:var(--jai-gold)] text-[color:var(--jai-gold)]">
                Advanced
              </span>
            )}
          </button>
          <Link
            to="/chat"
            className="gold-btn rounded-full px-6 py-3 font-serif-display text-lg inline-flex items-center gap-2 glow-hover"
            data-testid="cta-open-chat"
          >
            Ask the Shastras <MoveRight size={16} />
          </Link>
        </div>
      </div>

      {chart.profile.tob_unknown && (
        <div className="mb-8 card-surface px-6 py-4 border-l-4 border-[color:var(--jai-gold)] fade-up" data-testid="tob-approximate-banner">
          <p className="text-sm text-[color:var(--jai-green-deep)] leading-relaxed">
            <strong>Your birth time is approximate</strong> — estimated from {chart.profile.tob_period === "before_sunrise" ? "before" : "after"} sunrise,
            not an exact clock time. House placements and divisional charts below carry more uncertainty as a
            result. For reliability, lean on your <strong>Chandra Kundali (Moon chart)</strong> further down this
            page — the classical fallback for exactly this situation.
          </p>
        </div>
      )}

      {dasha && (
        <div className="card-surface px-8 py-4 fade-up flex items-center justify-between flex-wrap gap-4" data-testid="current-dasha">
          <div className="overline shrink-0">Current Dasha</div>
          <div className="flex items-center gap-6 flex-wrap">
            <div className="flex items-baseline gap-2">
              <span className="font-serif-display text-2xl text-[color:var(--jai-gold)]">{dasha.lord}</span>
              <span className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">MD · {dasha.start} → {dasha.end}</span>
            </div>
            {antar && (
              <div className="flex items-baseline gap-2">
                <span className="font-serif-display text-xl text-[color:var(--jai-green-deep)]">{antar.lord}</span>
                <span className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">AD · {dateOnly(antar.start)} → {dateOnly(antar.end)}</span>
              </div>
            )}
            {isAdvanced && pratyantar && (
              <div className="flex items-baseline gap-2">
                <span className="font-serif-display text-lg text-[color:var(--jai-gold-soft)]">{pratyantar.lord}</span>
                <span className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">PD · {dateOnly(pratyantar.start)} → {dateOnly(pratyantar.end)}</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div className={`mt-6 grid grid-cols-1 ${showAll ? "lg:grid-cols-12" : ""} gap-6 fade-up delay-1 items-stretch`}>
        <div
          className={`${showAll ? "lg:col-span-6" : "w-full max-w-2xl mx-auto"} card-surface p-8 flex flex-col transition-all duration-300`}
          data-testid="rasi-card"
        >
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-start gap-3">
              <button
                type="button"
                onClick={() => setShowAll((v) => !v)}
                className="mt-0.5 w-7 h-7 shrink-0 rounded-full flex items-center justify-center border border-[color:var(--jai-border)] text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)] hover:border-[color:var(--jai-gold)] transition-colors"
                title={showAll ? "Collapse Transit, D9 & D10" : "Show Transit, D9 & D10"}
                data-testid="toggle-extra-charts"
              >
                <ChevronDown
                  size={14}
                  className={`transition-transform duration-300 ${showAll ? "" : "rotate-180"}`}
                />
              </button>
              <div>
                <div className="overline">Rasi Chakra · D1</div>
                <div className="font-serif-display text-2xl mt-1 text-[color:var(--jai-parchment)]">Lagna: {asc.sign_en}</div>
              </div>
            </div>
            <div className="text-right">
              <div className="overline">Degree</div>
              <div className="font-serif-display text-xl text-[color:var(--jai-gold)]">{asc.degree_in_sign}°</div>
            </div>
          </div>
          <div className="flex-1 flex items-center">
            <KundaliChart planets={chart.planets} ascendantSign={asc.sign_idx} ascendant={asc} />
          </div>
        </div>

        {showAll && (
          <div className="lg:col-span-6 card-surface p-8 flex flex-col" data-testid="transits-card">
            <div className="flex items-center justify-between mb-1">
              <div className="overline">Live Transits · Today</div>
              <div className="text-[10px] text-[color:var(--jai-text-muted)]">
                {new Date(transits.as_of).toLocaleString(undefined, {
                  timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                  dateStyle: "medium",
                  timeStyle: "short",
                })}
              </div>
            </div>
            <div className="font-serif-display text-base mt-1 mb-4 text-[color:var(--jai-parchment)] leading-snug min-h-[3.5rem]">
              {todaysTransitNote(transits) || "Today's sky, mapped against your birth chart."}
            </div>
            {(() => {
              const retro = transits.planets.filter((p) => p.retrograde && p.name !== "Ketu" && p.name !== "Rahu");
              if (retro.length === 0) return null;
              return (
                <div
                  className="mb-4 px-4 py-2.5 rounded-lg border border-[color:var(--jai-gold)]/40 bg-[color:var(--jai-gold)]/10 text-sm text-[color:var(--jai-green-deep)]"
                  data-testid="retrograde-banner"
                >
                  <strong>{retro.map((p) => p.name).join(", ")}</strong>
                  {retro.length === 1 ? " is" : " are"} retrograde right now.
                </div>
              );
            })()}
            <div className="flex-1 flex items-center">
              <KundaliChart
                planets={transits.planets
                  .filter((t) => t.house_from_lagna)
                  .map((t) => ({ ...t, house: t.house_from_lagna }))}
                ascendantSign={asc.sign_idx}
                showNakshatra={false}
                testid="kundali-chart-transit"
              />
            </div>
          </div>
        )}
      </div>

      {showAll ? (
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up delay-2">
          {moonChart && (
            <div className="lg:col-span-6 card-surface p-8" data-testid="moon-chart-card">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <div className="overline">Chandra Kundali · Moon Chart</div>
                  <div className="font-serif-display text-2xl mt-1 text-[color:var(--jai-parchment)]">Moon Lagna: {moonChart.ascendant.sign_en}</div>
                </div>
                <div className="text-right text-[10px] text-[color:var(--jai-text-muted)] max-w-[140px]">
                  Mind, emotions &amp; day-to-day life
                </div>
              </div>
              <KundaliChart planets={moonChart.planets} ascendantSign={moonChart.ascendant.sign_idx} showNakshatra={false} testid="kundali-chart-moon" />
            </div>
          )}

          <div className="lg:col-span-6 card-surface p-8" data-testid="navamsa-card">
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="overline">Navamsa · D9</div>
                <div className="font-serif-display text-2xl mt-1 text-[color:var(--jai-parchment)]">D9 Lagna: {navamsa.ascendant.sign_en}</div>
              </div>
              <div className="text-right text-[10px] text-[color:var(--jai-text-muted)] max-w-[140px]">
                Marriage &amp; second half of life
              </div>
            </div>
            <KundaliChart planets={navamsa.planets} ascendantSign={navamsa.ascendant.sign_idx} showNakshatra={false} testid="kundali-chart-d9" />
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="mt-4 w-full max-w-2xl mx-auto flex items-center justify-center gap-2 text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)] py-3 border border-dashed border-[color:var(--jai-border)] rounded-full transition-colors fade-up delay-2"
          data-testid="expand-extra-charts"
        >
          <ChevronDown size={12} className="rotate-180" />
          Transit · Moon Chart · D9 — click to expand
        </button>
      )}

      {/* D10 + D2/D4/D6/D7/D16/D24/D60 — additional divisional (varga)
          charts for astrologers. Hidden in Simple mode. D10 (career) is
          always shown first; the rest collapse behind a toggle. Collapsed,
          D10 is rendered at the same size/style as the D9 card above so it
          doesn't look like an orphaned small card with dead space beside
          it; expanded, everything (including D10) drops to the smaller
          grid-of-cards style used for the rest of the vargas. */}
      {isAdvanced && (dasamsa || chart.extra_vargas) && (
        <div className="mt-8 fade-up delay-2">
          <div className="flex items-center justify-between mb-4">
            <div className="overline">Additional Divisional Charts</div>
            {chart.extra_vargas && (
              <button
                type="button"
                onClick={() => setShowAllVargas((v) => !v)}
                className="flex items-center gap-1.5 text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)] transition-colors"
                data-testid="toggle-extra-vargas"
              >
                <ChevronDown
                  size={12}
                  className={`transition-transform duration-300 ${showAllVargas ? "rotate-180" : ""}`}
                />
                {showAllVargas ? "Show D10 only" : "Show all divisional charts"}
              </button>
            )}
          </div>

          {!showAllVargas ? (
            dasamsa && (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <div className="lg:col-span-6 card-surface p-8" data-testid="dasamsa-card">
                  <div className="flex items-center justify-between mb-6">
                    <div>
                      <div className="overline">Dasamsa · D10</div>
                      <div className="font-serif-display text-2xl mt-1 text-[color:var(--jai-parchment)]">D10 Lagna: {dasamsa.ascendant.sign_en}</div>
                    </div>
                    <div className="text-right text-[10px] text-[color:var(--jai-text-muted)] max-w-[140px]">
                      Career &amp; professional status
                    </div>
                  </div>
                  <KundaliChart planets={dasamsa.planets} ascendantSign={dasamsa.ascendant.sign_idx} showNakshatra={false} testid="kundali-chart-d10" />
                </div>
              </div>
            )
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {dasamsa && (
                <div className="card-surface p-6" data-testid="dasamsa-card">
                  <div className="mb-4">
                    <div className="overline">Dasamsa · D10</div>
                    <div className="font-serif-display text-lg mt-1 text-[color:var(--jai-parchment)]">
                      Lagna: {dasamsa.ascendant.sign_en}
                    </div>
                  </div>
                  <KundaliChart planets={dasamsa.planets} ascendantSign={dasamsa.ascendant.sign_idx} showNakshatra={false} testid="kundali-chart-d10" />
                </div>
              )}
              {chart.extra_vargas && Object.entries(chart.extra_vargas).map(([key, v]) => (
                <div key={key} className="card-surface p-6" data-testid={`varga-card-${key}`}>
                  <div className="mb-4">
                    <div className="overline">{v.label}</div>
                    <div className="font-serif-display text-lg mt-1 text-[color:var(--jai-parchment)]">
                      Lagna: {v.ascendant.sign_en}
                    </div>
                  </div>
                  <KundaliChart planets={v.planets} ascendantSign={v.ascendant.sign_idx} showNakshatra={false} testid={`kundali-chart-${key}`} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up delay-3">
        <div className={`${isAdvanced ? "lg:col-span-7" : "lg:col-span-6"} card-surface ${isAdvanced ? "p-8" : "p-5"}`}>
          <div className={`flex items-center justify-between flex-wrap gap-3 ${isAdvanced ? "mb-5" : "mb-3"}`}>
            <div className="overline">Natal Planets · Sidereal</div>
            {isAdvanced && (
            <div className="flex flex-wrap gap-2 text-[10px] font-semibold" data-testid="dignity-legend">
              <span className="px-2 py-0.5 rounded-full" style={{ background: "var(--jai-dignity-exalted-bg)", color: "var(--jai-dignity-exalted-fg)" }}>↑ Exalted</span>
              <span className="px-2 py-0.5 rounded-full" style={{ background: "var(--jai-dignity-debilitated-bg)", color: "var(--jai-dignity-debilitated-fg)" }}>↓ Debilitated</span>
              <span className="px-2 py-0.5 rounded-full" style={{ background: "var(--jai-dignity-moolatrikona-bg)", color: "var(--jai-dignity-moolatrikona-fg)" }}>MT Moolatrikona</span>
              <span className="px-2 py-0.5 rounded-full" style={{ background: "var(--jai-dignity-own-bg)", color: "var(--jai-dignity-own-fg)" }}>OWN — own sign</span>
              <span className="px-2 py-0.5 rounded-full" style={{ background: "var(--jai-dignity-vargottama-bg)", color: "var(--jai-dignity-vargottama-fg)" }}>VG Vargottama</span>
            </div>
            )}
          </div>
          <div className={`grid ${isAdvanced ? "grid-cols-2 gap-x-8 gap-y-3" : "grid-cols-1 gap-y-1"}`}>
            {chart.planets.map((p) => {
              const nature = chart.planet_nature?.[p.name];
              return (
              <div key={p.name} className={`flex items-baseline justify-between border-b border-[color:var(--jai-border)]/50 ${isAdvanced ? "py-2" : "py-1"}`}>
                <div>
                  <div className={`font-serif-display ${isAdvanced ? "text-lg" : "text-sm"} text-[color:var(--jai-parchment)] flex items-center gap-2`}>
                    {p.name}{p.retrograde ? " ℞" : ""}
                    {p.nakshatra && (
                      <span className={`font-sans ${isAdvanced ? "text-xs" : "text-[10px]"} font-normal text-[color:var(--jai-text-muted)]`}>
                        {p.nakshatra}
                      </span>
                    )}
                    {isAdvanced && p.dignity && p.dignity.map((d) => (
                      <span
                        key={d}
                        className="text-[9px] font-semibold px-1.5 py-0.5 rounded"
                        style={{
                          background:
                            d === "Exalted" ? "var(--jai-dignity-exalted-bg)" :
                            d === "Debilitated" ? "var(--jai-dignity-debilitated-bg)" :
                            d === "Moolatrikona" ? "var(--jai-dignity-moolatrikona-bg)" :
                            d === "Own Sign" ? "var(--jai-dignity-own-bg)" :
                            "var(--jai-dignity-vargottama-bg)",
                          color:
                            d === "Exalted" ? "var(--jai-dignity-exalted-fg)" :
                            d === "Debilitated" ? "var(--jai-dignity-debilitated-fg)" :
                            d === "Moolatrikona" ? "var(--jai-dignity-moolatrikona-fg)" :
                            d === "Own Sign" ? "var(--jai-dignity-own-fg)" :
                            "var(--jai-dignity-vargottama-fg)",
                        }}
                      >
                        {d === "Exalted" ? "↑ EX" : d === "Debilitated" ? "↓ DB" : d === "Moolatrikona" ? "MT" : d === "Own Sign" ? "OWN" : "VG"}
                      </span>
                    ))}
                  </div>
                  {isAdvanced && (
                    <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">
                      pada {p.pada} · D9 {p.navamsa_sign}
                    </div>
                  )}
                  {isAdvanced && nature && (nature.natural || nature.functional) && (
                    <div className="flex items-center gap-1 mt-1">
                      {nature.natural && (
                        <NatureBadge
                          label={nature.natural === "benefic" ? "B" : "M"}
                          nature={nature.natural}
                          title={`Natural nature: ${nature.natural === "benefic" ? "Benefic" : "Malefic"}`}
                        />
                      )}
                      {nature.functional && (
                        <NatureBadge
                          label={nature.functional === "benefic" ? "FB" : "FM"}
                          nature={nature.functional}
                          title={`Functional nature for this Lagna: ${nature.functional === "benefic" ? "Benefic" : "Malefic"}`}
                        />
                      )}
                    </div>
                  )}
                </div>
                <div className="text-right">
                  <div className={`${isAdvanced ? "text-sm" : "text-xs"} text-[color:var(--jai-gold)]`}>{p.sign_en} {p.degree_in_sign}°</div>
                  {isAdvanced && <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">house {p.house}</div>}
                  {isAdvanced && chart.shadbala && chart.shadbala[p.name] && (
                    <div
                      className="text-[10px] mt-0.5"
                      style={{ color: "var(--jai-gold-soft)" }}
                      title="Shadbala — relative planetary strength within this chart (partial classical implementation)"
                    >
                      Shadbala {chart.shadbala[p.name].total_rupas}
                    </div>
                  )}
                </div>
              </div>
              );
            })}
          </div>
        </div>

        {isAdvanced ? (
        <div className="lg:col-span-5 card-surface p-8" data-testid="dasha-timeline">
          <div className="overline mb-5">Vimshottari Dasha · 120-Year Cycle</div>
          <DashaExplorer mahadashas={chart.dashas} currentMahadasha={dasha} />
        </div>
        ) : (
        <div className="lg:col-span-6 card-surface p-5" data-testid="dasha-simple-card">
          <div className="overline mb-3">Vimshottari Dasha</div>
          <DashaExplorer mahadashas={chart.dashas} currentMahadasha={dasha} maxDepth={1} compact />
        </div>
        )}
      </div>

      {/* House Lords + Yogas — technical detail meant for astrologers, not
          shown in Simple mode. */}
      {isAdvanced && (
      <div className="mt-8 grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up delay-3">
        <div className="lg:col-span-7 card-surface p-8" data-testid="house-lords-card">
          <div className="overline mb-3">House Lords (Bhava Adhipati)</div>
          <div className="max-h-[480px] overflow-y-auto pr-1">
            {houseLords.map((h) => (
              <div
                key={h.house}
                className="grid items-center border-b border-[color:var(--jai-border)]/30 py-1.5 text-sm gap-3"
                style={{ gridTemplateColumns: "90px 1fr 100px 50px 50px" }}
              >
                <div>
                  <span className="font-serif-display text-base text-[color:var(--jai-parchment)]">H{h.house}</span>
                  <span className="ml-2 text-xs text-[color:var(--jai-text-muted)]">{h.sign_en}</span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-[color:var(--jai-green-deep)] font-semibold">{h.lord}</span>
                  {h.lord_sits_in_house && (
                    <span className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">
                      H{h.lord_sits_in_house} · {h.lord_sits_in_sign_en}
                    </span>
                  )}
                </div>
                <div className="text-right">
                  <div className="text-[9px] uppercase tracking-widest text-[color:var(--jai-text-muted)]/70">Aspected by</div>
                  <div className="text-xs text-[color:var(--jai-gold-soft)]">
                    {h.aspected_by && h.aspected_by.length > 0 ? h.aspected_by.join(", ") : "—"}
                  </div>
                </div>
                {h.ashtakavarga_sav != null && (
                  <div className="flex flex-col items-center" title="Sarvashtakavarga (SAV) — benefic point support for this sign, out of 337 total across the chart">
                    <div
                      className="w-9 h-9 rounded flex items-center justify-center text-xs font-serif-display border"
                      style={{
                        borderColor: h.ashtakavarga_sav >= 30 ? "var(--jai-gold)" : h.ashtakavarga_sav >= 25 ? "var(--jai-border-gold)" : "var(--jai-border)",
                        color: h.ashtakavarga_sav >= 30 ? "var(--jai-gold-soft)" : h.ashtakavarga_sav >= 25 ? "var(--jai-text-muted)" : "var(--jai-text-muted)",
                        opacity: h.ashtakavarga_sav >= 25 ? 1 : 0.6,
                      }}
                    >
                      {h.ashtakavarga_sav}
                    </div>
                    <div className="text-[8px] uppercase tracking-widest text-[color:var(--jai-text-muted)]/60 mt-0.5">SAV</div>
                  </div>
                )}
                {h.bhava_bala && (
                  <div className="flex flex-col items-center" title="Bhava Bala — relative house strength within this chart (partial classical implementation)">
                    <div className="w-9 h-9 rounded flex items-center justify-center text-xs font-serif-display border border-[color:var(--jai-border)]" style={{ color: "var(--jai-text-muted)" }}>
                      {h.bhava_bala.total_rupas}
                    </div>
                    <div className="text-[8px] uppercase tracking-widest text-[color:var(--jai-text-muted)]/60 mt-0.5">BB</div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-5 card-surface p-8" data-testid="yogas-card">
          <div className="overline mb-5">Detected Yogas</div>
          {yogas.length === 0 && (
            <p className="text-sm text-[color:var(--jai-text-muted)] italic">No tracked yogas active in this chart. Ask Compass Astro to discover subtler combinations.</p>
          )}
          <div className="space-y-4">
            {yogas.map((y) => (
              <div key={y.name} className="border-l-2 border-[color:var(--jai-gold)] pl-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-serif-display text-lg text-[color:var(--jai-green-deep)]">{y.name}</div>
                  <button
                    onClick={() => openYogaWhy(y)}
                    className="shrink-0 inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border border-[color:var(--jai-gold)] text-[color:var(--jai-gold)] hover:bg-[color:var(--jai-gold)] hover:text-[color:var(--jai-surface)] transition-colors"
                    data-testid={`yoga-why-btn-${y.name.replace(/\s+/g, "-")}`}
                  >
                    <Info size={10} /> Why?
                  </button>
                </div>
                <div className="mt-1 text-xs leading-relaxed text-[color:var(--jai-text-muted)]">{y.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
      )}

      <WhyPanel
        open={!!yogaWhy}
        onOpenChange={(v) => !v && setYogaWhy(null)}
        logic={yogaWhy?.detail}
        citations={yogaWhy?.citations}
        emptyLabel={
          yogaWhy?.loading
            ? "Looking up the classical source…"
            : yogaWhy?.error
            ? "Couldn't reach the source lookup just now — this isn't the same as no citation existing. Try again in a moment."
            : "No matching passage found in the corpus for this yoga yet."
        }
      />
    </div>
  );
}

const LOADING_STEPS = [
  "Casting your chart…",
  "Reading the transits…",
  "Consulting the shastras…",
  "Weighing the dashas…",
];

// Render's free tier spins down when idle, so a first visitor can sit on
// this for 30-60s. A cycling message makes that wait feel active instead
// of stuck — same duration, different feeling. (The "waking up the
// ephemeris engine" toast from AppShell can also appear alongside this on
// a genuine cold start; this component covers the plain first-load case.)
function ChartLoadingState() {
  const [step, setStep] = useState(0);
  const [showColdStartNote, setShowColdStartNote] = useState(false);

  useEffect(() => {
    const stepTimer = setInterval(() => {
      setStep((s) => (s + 1) % LOADING_STEPS.length);
    }, 2800);
    const coldTimer = setTimeout(() => setShowColdStartNote(true), 8000);
    return () => {
      clearInterval(stepTimer);
      clearTimeout(coldTimer);
    };
  }, []);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 px-6 text-center">
      <Loader2 className="animate-spin text-[color:var(--jai-gold)]" size={32} />
      <p className="font-serif-display text-lg text-[color:var(--jai-green-deep)]" data-testid="chart-loading-step">
        {LOADING_STEPS[step]}
      </p>
      {showColdStartNote && (
        <p className="text-xs text-[color:var(--jai-text-muted)] max-w-xs" data-testid="chart-loading-cold-note">
          Taking longer than usual — if the server was asleep, this can take up to a minute.
        </p>
      )}
    </div>
  );
}
