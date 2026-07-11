import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Loader2, MoveRight } from "lucide-react";
import { Link } from "react-router-dom";
import KundaliChart from "@/components/KundaliChart";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Dashboard() {
  const [chart, setChart] = useState(null);
  const [transits, setTransits] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const id = localStorage.getItem("jyotish_profile_id");
    if (!id) return;
    (async () => {
      try {
        const [c, t] = await Promise.all([
          axios.get(`${API}/profile/${id}/chart`),
          axios.get(`${API}/transits`, { params: { profile_id: id } }),
        ]);
        setChart(c.data);
        setTransits(t.data);
      } catch (e) {
        toast.error("Could not load your chart");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

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
  const navamsa = chart.navamsa;
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

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up delay-1">
        <div className="lg:col-span-8 card-surface p-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="overline">Rasi Chakra · North Indian (D1)</div>
              <div className="font-serif-display text-3xl mt-1 text-[color:var(--jai-parchment)]">Lagna: {asc.sign_en}</div>
            </div>
            <div className="text-right">
              <div className="overline">Ascendant Degree</div>
              <div className="font-serif-display text-2xl text-[color:var(--jai-gold)]">{asc.degree_in_sign}°</div>
            </div>
          </div>
          <KundaliChart planets={chart.planets} ascendantSign={asc.sign_idx} />
        </div>

        <div className="lg:col-span-4 space-y-6">
          {dasha && (
            <div className="card-surface p-6" data-testid="current-dasha">
              <div className="overline mb-3">Current Dasha</div>
              <div className="flex items-baseline gap-3">
                <div className="font-serif-display text-4xl text-[color:var(--jai-gold)]">{dasha.lord}</div>
                <div className="text-[color:var(--jai-text-muted)]">MD</div>
              </div>
              <div className="mt-1 text-xs text-[color:var(--jai-text-muted)]">{dasha.start} → {dasha.end} · {dasha.years}y</div>
              {antar && (
                <>
                  <div className="mt-4 flex items-baseline gap-3">
                    <div className="font-serif-display text-2xl text-[color:var(--jai-green-deep)]">{antar.lord}</div>
                    <div className="text-[color:var(--jai-text-muted)] text-xs">AD (Antardasha)</div>
                  </div>
                  <div className="mt-1 text-xs text-[color:var(--jai-text-muted)]">{antar.start} → {antar.end}</div>
                </>
              )}
            </div>
          )}

          <div className="card-surface p-6" data-testid="transits-card">
            <div className="overline mb-4">Live Transits · Today</div>
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {transits.planets.map((t) => (
                <div key={t.name} className="flex items-baseline justify-between text-sm border-b border-[color:var(--jai-border)]/50 py-2">
                  <span className="font-medium text-[color:var(--jai-text)]">{t.name}</span>
                  <span className="text-[color:var(--jai-text-muted)] text-xs">
                    {t.sign_en} · {t.degree_in_sign}°{t.retrograde ? " R" : ""}
                    {t.house_from_lagna ? <span className="ml-1 text-[color:var(--jai-gold)]">· H{t.house_from_lagna}</span> : null}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* D9 Navamsa + House Lords + Yogas */}
      <div className="mt-8 grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up delay-2">
        <div className="lg:col-span-5 card-surface p-8" data-testid="navamsa-card">
          <div className="flex items-center justify-between mb-6">
            <div>
              <div className="overline">Navamsa · D9</div>
              <div className="font-serif-display text-2xl mt-1 text-[color:var(--jai-parchment)]">D9 Lagna: {navamsa.ascendant.sign_en}</div>
            </div>
            <div className="text-right text-xs text-[color:var(--jai-text-muted)] max-w-[180px]">
              D9 reveals second-half of life & marriage
            </div>
          </div>
          <KundaliChart planets={navamsa.planets} ascendantSign={navamsa.ascendant.sign_idx} />
        </div>

        <div className="lg:col-span-4 card-surface p-8" data-testid="house-lords-card">
          <div className="overline mb-5">House Lords (Bhava Adhipati)</div>
          <div className="space-y-1 max-h-[520px] overflow-y-auto pr-1">
            {houseLords.map((h) => (
              <div key={h.house} className="flex items-baseline justify-between border-b border-[color:var(--jai-border)]/40 py-2 text-sm">
                <div>
                  <span className="font-serif-display text-lg text-[color:var(--jai-parchment)]">H{h.house}</span>
                  <span className="ml-2 text-[color:var(--jai-text-muted)]">{h.sign_en}</span>
                </div>
                <div className="text-right">
                  <div className="text-[color:var(--jai-green-deep)] font-semibold">{h.lord}</div>
                  {h.lord_sits_in_house && (
                    <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">
                      sits H{h.lord_sits_in_house} · {h.lord_sits_in_sign_en}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-3 card-surface p-8" data-testid="yogas-card">
          <div className="overline mb-5">Detected Yogas</div>
          {yogas.length === 0 && (
            <p className="text-sm text-[color:var(--jai-text-muted)] italic">No tracked yogas active in this chart. Ask Jyotish AI to discover subtler combinations.</p>
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
          <div className="space-y-1 max-h-80 overflow-y-auto">
            {chart.dashas.map((d, i) => {
              const isCurrent = dasha && d.lord === dasha.lord && d.start === dasha.start;
              return (
                <div
                  key={i}
                  className={`px-3 py-2 rounded flex justify-between items-baseline ${isCurrent ? "bg-[color:var(--jai-gold)]/10 border border-[color:var(--jai-gold)]/40" : ""}`}
                >
                  <div>
                    <div className={`font-serif-display text-lg ${isCurrent ? "text-[color:var(--jai-gold-soft)]" : "text-[color:var(--jai-parchment)]"}`}>{d.lord}</div>
                    <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">{d.years} yrs</div>
                  </div>
                  <div className="text-xs text-[color:var(--jai-text-muted)] text-right">
                    {d.start}<br/>{d.end}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
