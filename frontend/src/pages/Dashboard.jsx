import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, MoveRight } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import KundaliChart from "@/components/KundaliChart";
import DashaExplorer from "@/components/DashaExplorer";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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

// Antardasha/Pratyantardasha now carry full "YYYY-MM-DD HH:MM:SS" timestamps
// (needed for Sookshma/Prana precision elsewhere); this strip only needs the date.
const dateOnly = (str) => (str ? str.split(" ")[0] : str);

export default function Dashboard() {
  const navigate = useNavigate();
  const [chart, setChart] = useState(null);
  const [transits, setTransits] = useState(null);
  const [loading, setLoading] = useState(true);

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
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin text-[color:var(--jai-gold)]" size={32} />
      </div>
    );
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

  return (
    <div className="max-w-7xl mx-auto px-8 py-12" data-testid="dashboard-page">
      <div className="mb-12 flex items-end justify-between gap-6 flex-wrap fade-up">
        <div>
          <div className="overline mb-4">Namaste · Your Vedic Chart</div>
          <h1 className="font-serif-display text-5xl sm:text-6xl leading-[0.95] text-[color:var(--jai-parchment)]" data-testid="dashboard-title">
            {chart.profile.name}<span className="text-[color:var(--jai-gold)]">.</span>
          </h1>
          <div className="mt-3 text-[color:var(--jai-text-muted)] text-sm tracking-wide">
            {chart.profile.dob} · {chart.profile.tob} · {chart.profile.place} · Lagna lord: <span className="text-[color:var(--jai-green-deep)] font-semibold">{asc.lord}</span>
          </div>
        </div>
        <Link
          to="/chat"
          className="gold-btn rounded-full px-6 py-3 font-serif-display text-lg inline-flex items-center gap-2 glow-hover"
          data-testid="cta-open-chat"
        >
          Ask the Shastras <MoveRight size={16} />
        </Link>
      </div>

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
            {pratyantar && (
              <div className="flex items-baseline gap-2">
                <span className="font-serif-display text-lg text-[color:var(--jai-gold-soft)]">{pratyantar.lord}</span>
                <span className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">PD · {dateOnly(pratyantar.start)} → {dateOnly(pratyantar.end)}</span>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up delay-1 items-stretch">
        <div className="lg:col-span-6 card-surface p-8 flex flex-col" data-testid="rasi-card">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="overline">Rasi Chakra · D1</div>
              <div className="font-serif-display text-2xl mt-1 text-[color:var(--jai-parchment)]">Lagna: {asc.sign_en}</div>
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
      </div>

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up delay-2">
        <div className="lg:col-span-6 card-surface p-8" data-testid="navamsa-card">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="overline">Navamsa · D9</div>
              <div className="font-serif-display text-2xl mt-1 text-[color:var(--jai-parchment)]">D9 Lagna: {navamsa.ascendant.sign_en}</div>
            </div>
            <div className="text-right text-[10px] text-[color:var(--jai-text-muted)] max-w-[140px]">
              Marriage & second half of life
            </div>
          </div>
          <KundaliChart planets={navamsa.planets} ascendantSign={navamsa.ascendant.sign_idx} showNakshatra={false} testid="kundali-chart-d9" />
        </div>

        {dasamsa && (
          <div className="lg:col-span-6 card-surface p-8" data-testid="dasamsa-card">
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="overline">Dasamsa · D10</div>
                <div className="font-serif-display text-2xl mt-1 text-[color:var(--jai-parchment)]">D10 Lagna: {dasamsa.ascendant.sign_en}</div>
              </div>
              <div className="text-right text-[10px] text-[color:var(--jai-text-muted)] max-w-[140px]">
                Career & professional status
              </div>
            </div>
            <KundaliChart planets={dasamsa.planets} ascendantSign={dasamsa.ascendant.sign_idx} showNakshatra={false} testid="kundali-chart-d10" />
          </div>
        )}
      </div>

      {/* House Lords + Yogas */}
      <div className="mt-8 grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up delay-3">
        <div className="lg:col-span-7 card-surface p-8" data-testid="house-lords-card">
          <div className="overline mb-3">House Lords (Bhava Adhipati)</div>
          <div className="max-h-[480px] overflow-y-auto pr-1">
            {houseLords.map((h) => (
              <div
                key={h.house}
                className="grid items-center border-b border-[color:var(--jai-border)]/30 py-1.5 text-sm gap-3"
                style={{ gridTemplateColumns: "95px 1fr 110px 56px" }}
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
                <div className="font-serif-display text-lg text-[color:var(--jai-green-deep)]">{y.name}</div>
                <div className="mt-1 text-xs leading-relaxed text-[color:var(--jai-text-muted)]">{y.detail}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up delay-3">
        <div className="lg:col-span-7 card-surface p-8">
          <div className="flex items-center justify-between mb-5 flex-wrap gap-3">
            <div className="overline">Natal Planets · Sidereal</div>
            <div className="flex flex-wrap gap-2 text-[10px] font-semibold" data-testid="dignity-legend">
              <span className="px-2 py-0.5 rounded-full" style={{ background: "rgba(15,81,50,0.12)", color: "#0F5132" }}>↑ Exalted</span>
              <span className="px-2 py-0.5 rounded-full" style={{ background: "rgba(160,82,45,0.15)", color: "#A0522D" }}>↓ Debilitated</span>
              <span className="px-2 py-0.5 rounded-full" style={{ background: "rgba(184,134,11,0.15)", color: "#B8860B" }}>MT Moolatrikona</span>
              <span className="px-2 py-0.5 rounded-full" style={{ background: "rgba(218,165,32,0.18)", color: "#8B6914" }}>OWN Own</span>
              <span className="px-2 py-0.5 rounded-full" style={{ background: "rgba(59,76,153,0.15)", color: "#3B4C99" }}>VG Vargottama</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-x-8 gap-y-3">
            {chart.planets.map((p) => (
              <div key={p.name} className="flex items-baseline justify-between border-b border-[color:var(--jai-border)]/50 py-2">
                <div>
                  <div className="font-serif-display text-lg text-[color:var(--jai-parchment)] flex items-center gap-2">
                    {p.name}{p.retrograde ? " ℞" : ""}
                    {p.dignity && p.dignity.map((d) => (
                      <span
                        key={d}
                        className="text-[9px] font-semibold px-1.5 py-0.5 rounded"
                        style={{
                          background:
                            d === "Exalted" ? "rgba(15,81,50,0.15)" :
                            d === "Debilitated" ? "rgba(160,82,45,0.15)" :
                            d === "Moolatrikona" ? "rgba(184,134,11,0.15)" :
                            d === "Own Sign" ? "rgba(218,165,32,0.18)" :
                            "rgba(59,76,153,0.15)",
                          color:
                            d === "Exalted" ? "#0F5132" :
                            d === "Debilitated" ? "#A0522D" :
                            d === "Moolatrikona" ? "#B8860B" :
                            d === "Own Sign" ? "#8B6914" :
                            "#3B4C99",
                        }}
                      >
                        {d === "Exalted" ? "↑ EX" : d === "Debilitated" ? "↓ DB" : d === "Moolatrikona" ? "MT" : d === "Own Sign" ? "OWN" : "VG"}
                      </span>
                    ))}
                  </div>
                  <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">{p.nakshatra} · pada {p.pada} · D9 {p.navamsa_sign}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm text-[color:var(--jai-gold)]">{p.sign_en} {p.degree_in_sign}°</div>
                  <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">house {p.house}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-5 card-surface p-8" data-testid="dasha-timeline">
          <div className="overline mb-5">Vimshottari Dasha · 120-Year Cycle</div>
          <DashaExplorer mahadashas={chart.dashas} currentMahadasha={dasha} />
        </div>
      </div>
    </div>
  );
}
