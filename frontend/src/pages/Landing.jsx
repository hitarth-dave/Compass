// cache-bust: force-recompile 2026-07-20-1
import { Compass, Sparkles, BookOpen, MessageCircle, Sun, Moon } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useTheme } from "@/context/ThemeContext";
import { Navigate } from "react-router-dom";
import { createPortal } from "react-dom";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
export default function Landing() {
  const { user, loading } = useAuth();
  const { theme, toggleTheme } = useTheme();

  if (loading) return null;
  if (user) return <Navigate to="/dashboard" replace />;

  const signIn = () => {
    // Derive redirect from browser origin — do NOT hardcode.
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="relative min-h-screen overflow-hidden" data-testid="landing-page">
      {/* Rendered via portal directly into document.body — NOT as a normal child
          here. A plain `fixed` element positions relative to the nearest
          ancestor that has a CSS transform/filter/perspective applied (this
          page's fade-up scroll animations use transform), which can silently
          reposition or hide a fixed element far from where it visually
          should be, even though its code and styles are both correct. The
          portal sidesteps that entirely by attaching straight to <body>. */}
      {createPortal(
        <button
          onClick={toggleTheme}
          className="fixed top-4 right-4 z-[9999] w-10 h-10 rounded-full flex items-center justify-center bg-[color:var(--jai-surface)] border border-[color:var(--jai-border)] text-[color:var(--jai-gold)] hover:text-[color:var(--jai-gold-soft)] hover:border-[color:var(--jai-border-gold)] transition-colors shadow-md"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          data-testid="theme-toggle-btn"
        >
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </button>,
        document.body
      )}

      <div className="absolute inset-0 -z-10">
        <div
          className="absolute inset-0 opacity-25"
          style={{
            backgroundImage: "url(https://images.unsplash.com/photo-1648717008621-ee7e6acfe270?w=1920&q=80)",
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        />
        <div className="absolute inset-0 bg-[color:var(--jai-bg)]/85" />
      </div>

      <div className="max-w-6xl mx-auto px-6 lg:px-12 py-8">
        <header className="flex items-center justify-between fade-up">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full border border-[color:var(--jai-gold)] flex items-center justify-center">
              <Compass size={18} className="text-[color:var(--jai-gold)]" />
            </div>
            <div>
              <div className="font-serif-display text-2xl leading-none text-[color:var(--jai-green-deep)]">Compass Astro</div>
              <div className="overline mt-1">Ancient wisdom, clear direction</div>
            </div>
          </div>
          <button
            onClick={signIn}
            className="hidden sm:inline-flex items-center gap-2 text-sm text-[color:var(--jai-green-deep)] hover:text-[color:var(--jai-gold)]"
            data-testid="signin-header-btn"
          >
            Sign in
          </button>
        </header>

        <section className="mt-24 sm:mt-28 max-w-3xl fade-up delay-1">
          <div className="overline mb-6">Sanatan · Jyotish · Personal Counsel</div>
          <h1 className="font-serif-display text-5xl sm:text-6xl lg:text-7xl leading-[0.95] text-[color:var(--jai-parchment)]">
            Your birth chart, <em className="text-[color:var(--jai-gold)]">read aloud</em><br />
            by the ancient shastras.
          </h1>
          <p className="mt-8 text-lg text-[color:var(--jai-text-muted)] max-w-2xl leading-relaxed">
            Compass Astro casts your Vedic Kundali, listens to today's planetary transits, and answers your
            questions in plain everyday language — grounded in the classical texts of Sanatan astrology.
            Career, love, timing, direction. No jargon. Real depth on demand.
          </p>

          <div className="mt-12 flex flex-col sm:flex-row gap-4">
            <button
              onClick={signIn}
              className="gold-btn rounded-full px-8 py-4 font-serif-display text-lg inline-flex items-center justify-center gap-3 glow-hover"
              data-testid="google-signin-btn"
            >
              <GoogleGlyph /> Continue with Google
            </button>
            <div className="text-xs text-[color:var(--jai-text-muted)] self-center max-w-xs">
              Your chart, chats and uploaded books stay private to your account.
            </div>
          </div>
        </section>

        <section className="mt-32 grid grid-cols-1 sm:grid-cols-3 gap-6 fade-up delay-2">
          <FeatureCard Icon={Sparkles} title="A living Kundali"
            body="Sidereal chart, planetary positions, current Mahadasha and today's transits — all computed from Swiss Ephemeris the moment you land." />
          <FeatureCard Icon={MessageCircle} title="Ask anything, plainly"
            body="Career, relationships, timing, health — Compass Astro answers like a wise friend, and shows the reasoning on demand." />
          <FeatureCard Icon={BookOpen} title="Grounded in the classics"
            body="Every reading is rooted in Brihat Parashara Hora Shastra, Phaladeepika, Saravali, Jaimini Sutras, and more — plus any PDFs you upload." />
        </section>

        <footer className="mt-32 mb-6 text-xs text-[color:var(--jai-text-muted)] text-center tracking-wide">
          Sidereal · Lahiri Ayanamsa · Vimshottari Dasha · Powered by Claude Sonnet 4.5
        </footer>
      </div>
    </div>
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

function GoogleGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.9 2.5 30.4 0 24 0 14.6 0 6.5 5.4 2.5 13.2l7.9 6.2C12.5 13.3 17.8 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.5 24.5c0-1.7-.2-3.3-.5-4.9H24v9.3h12.7c-.5 3-2.2 5.5-4.7 7.2l7.6 5.9c4.4-4.1 6.9-10.1 6.9-17.5z"/>
      <path fill="#FBBC05" d="M10.4 28.6c-.6-1.6-.9-3.4-.9-5.1s.3-3.5.9-5.1l-7.9-6.2C1 15.7 0 19.7 0 24s1 8.3 2.5 11.8l7.9-7.2z"/>
      <path fill="#34A853" d="M24 48c6.4 0 11.9-2.1 15.9-5.7l-7.6-5.9c-2.1 1.4-4.8 2.3-8.3 2.3-6.2 0-11.5-3.8-13.6-9.4l-7.9 6.2C6.5 42.6 14.6 48 24 48z"/>
    </svg>
  );
}
