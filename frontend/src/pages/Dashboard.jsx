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
          axios.get(`${API}/transits`),
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

  return (
    <div className="max-w-7xl mx-auto px-8 py-12" data-testid="dashboard-page">
      <div className="mb-12 flex items-end justify-between gap-6 flex-wrap fade-up">
        <div>
          <div className="overline mb-4">Namaste · Your Vedic Chart</div>
          <h1 className="font-serif-display text-5xl sm:text-6xl leading-[0.95] text-[color:var(--jai-parchment)]" data-testid="dashboard-title">
            {chart.profile.name}<span className="text-[color:var(--jai-gold-soft)]">.</span>
          </h1>
          <div className="mt-3 text-[color:var(--jai-text-muted)] text-sm tracking-wide">
            {chart.profile.dob} · {chart.profile.tob} · {chart.profile.place}
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
              <div className="overline">Rasi Chakra · North Indian</div>
              <div className="font-serif-display text-3xl mt-1 text-[color:var(--jai-parchment)]">Lagna: {asc.sign_en}</div>
            </div>
            <div className="text-right">
              <div className="overline">Ascendant Degree</div>
              <div className="font-serif-display text-2xl text-[color:var(--jai-gold-soft)]">{asc.degree_in_sign}°</div>
            </div>
          </div>
          <KundaliChart planets={chart.planets} ascendantSign={asc.sign_idx} />
        </div>

        <div className="lg:col-span-4 space-y-6">
          {dasha && (
            <div className="card-surface p-6" data-testid="current-dasha">
              <div className="overline mb-3">Current Mahadasha</div>
              <div className="font-serif-display text-4xl text-[color:var(--jai-gold-soft)]">{dasha.lord}</div>
              <div className="mt-3 text-sm text-[color:var(--jai-text-muted)]">
                {dasha.start} → {dasha.end}
              </div>
              <div className="mt-1 text-xs text-[color:var(--jai-text-muted)]">Span: {dasha.years} years</div>
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
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-12 gap-6 fade-up delay-2">
        <div className="lg:col-span-7 card-surface p-8">
          <div className="overline mb-5">Natal Planets · Sidereal</div>
          <div className="grid grid-cols-2 gap-x-8 gap-y-3">
            {chart.planets.map((p) => (
              <div key={p.name} className="flex items-baseline justify-between border-b border-[color:var(--jai-border)]/50 py-2">
                <div>
                  <div className="font-serif-display text-lg text-[color:var(--jai-parchment)]">{p.name}{p.retrograde ? " ℞" : ""}</div>
                  <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">{p.nakshatra} · pada {p.pada}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm text-[color:var(--jai-gold-soft)]">{p.sign_en} {p.degree_in_sign}°</div>
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
