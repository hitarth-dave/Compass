import { useState } from "react";
import { Sparkles, BookOpen, MessageCircle, Compass as CompassIcon } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Navigate, Link } from "react-router-dom";
import PublicLayout from "@/components/PublicLayout";
import AuthButtons from "@/components/AuthButtons";
import Compass3D from "@/components/Compass3D";

export default function Home() {
  const { user, loading } = useAuth();
  // Static compass photo (with its own cosmic/splash background, feathered
  // to blend into the page) is the default hero visual; the interactive 3D
  // compass stays available as an alternate view behind a small toggle.
  const [heroView, setHeroView] = useState("photo"); // "photo" | "3d"
  if (loading) return null;
  if (user) return <Navigate to="/dashboard" replace />;

  return (
    <PublicLayout>
      {/* HERO */}
      <section className="max-w-6xl mx-auto px-6 lg:px-12 pt-6 pb-10 grid lg:grid-cols-2 gap-10 items-center">
        <div className="fade-up">
          <div className="overline mb-6">Sanatan · Jyotish · Personal Counsel</div>
          <h1 className="font-serif-display text-5xl sm:text-6xl lg:text-7xl leading-[0.95] text-[color:var(--jai-parchment)]">
            Your birth chart, <em className="text-[color:var(--jai-gold)]">read aloud</em> by the ancient shastras.
          </h1>
          <p className="mt-8 text-lg text-[color:var(--jai-text-muted)] max-w-xl leading-relaxed">
            Compass Astro casts your Vedic Kundali, listens to today's planetary transits, and answers
            your questions in plain everyday language — grounded in the classical texts. Career, love,
            timing, direction. No jargon. Real depth on demand.
          </p>
          <div className="mt-12">
            <AuthButtons label="Get your chart — sign in" />
            <p className="mt-4 text-xs text-[color:var(--jai-text-muted)] max-w-md">
              Your chart, chats and uploaded books stay private to your account.
            </p>
          </div>
        </div>

        <div className="fade-up delay-1 flex flex-col items-center">
          <div className="relative flex justify-center items-center" style={{ minHeight: "380px" }}>
            {heroView === "photo" ? (
              <img
                src="/compass-hero-photo.png"
                alt="A compass marking Career, Success, Love, Purpose, Health, Wealth and Marriage, set against a starfield"
                className="w-full max-w-2xl h-auto object-contain"
              />
            ) : (
              <Compass3D />
            )}
          </div>
          <button
            type="button"
            onClick={() => setHeroView(heroView === "photo" ? "3d" : "photo")}
            className="mt-2 text-xs uppercase tracking-widest text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)] transition-colors"
            data-testid="hero-view-toggle"
          >
            {heroView === "photo" ? "Prefer the interactive view? →" : "← Back to compass"}
          </button>
        </div>
      </section>

      {/* FEATURES */}
      <section className="max-w-6xl mx-auto px-6 lg:px-12 mt-16 grid grid-cols-1 sm:grid-cols-3 gap-6 fade-up delay-2">
        <FeatureCard Icon={Sparkles} title="A living Kundali"
          body="Sidereal chart, planetary positions, current Mahadasha and today's transits — all computed from Swiss Ephemeris the moment you land." />
        <FeatureCard Icon={MessageCircle} title="Ask anything, plainly"
          body="Career, relationships, timing, health — Compass Astro answers like a wise friend, and shows the reasoning on demand." />
        <FeatureCard Icon={BookOpen} title="Grounded in the classics"
          body="Every reading is rooted in Brihat Parashara Hora Shastra, Phaladeepika, Saravali, Jaimini Sutras, and more — plus any PDFs you upload." />
      </section>

      {/* SECOND BAND */}
      <section className="max-w-4xl mx-auto px-6 lg:px-12 mt-32 text-center fade-up">
        <div className="overline mb-6">Why Compass</div>
        <h2 className="font-serif-display text-4xl sm:text-5xl leading-tight text-[color:var(--jai-green-deep)]">
          Jyotish is a compass, not a verdict.
        </h2>
        <p className="mt-6 text-lg text-[color:var(--jai-text-muted)] leading-relaxed">
          It was never meant to fix your fate. Read rightly, a chart shows where you stand and which
          directions are open — the way a compass shows north without deciding your road. We compute
          your Kundali from real astronomical data, read it against the classical corpus, and hand you
          the bearing in words you can actually use.
        </p>
        <div className="mt-10">
          <Link to="/astrology" className="gold-accent-btn rounded-full px-8 py-3.5 inline-flex items-center gap-2 text-sm">
            <CompassIcon size={16} /> Explore what we read
          </Link>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-3xl mx-auto px-6 lg:px-12 mt-32 text-center fade-up">
        <h2 className="font-serif-display text-4xl sm:text-5xl text-[color:var(--jai-parchment)]">
          Find your <em className="text-[color:var(--jai-gold)]">bearing.</em>
        </h2>
        <p className="mt-5 text-[color:var(--jai-text-muted)]">Sign in and your chart is ready in seconds.</p>
        <div className="mt-8 flex justify-center">
          <AuthButtons compact label="Sign in" />
        </div>
      </section>
    </PublicLayout>
  );
}

function FeatureCard({ Icon, title, body }) {
  return (
    <div className="card-surface p-6">
      <Icon size={20} className="text-[color:var(--jai-gold)] mb-4" />
      <h3 className="font-serif-display text-xl text-[color:var(--jai-green-deep)] leading-snug">{title}</h3>
      <p className="mt-3 text-sm text-[color:var(--jai-text-muted)] leading-relaxed">{body}</p>
    </div>
  );
}
