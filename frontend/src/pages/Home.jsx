import { useEffect } from "react";
import { Sparkles, BookOpen, MessageCircle, Compass as CompassIcon } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Navigate, Link, useSearchParams } from "react-router-dom";
import PublicLayout from "@/components/PublicLayout";
import AuthButtons from "@/components/AuthButtons";
import CredibilityBar from "@/components/CredibilityBar";
import HowItWorks from "@/components/HowItWorks";
import ProductPreview from "@/components/ProductPreview";

export default function Home() {
  const { user, loading, openAuthModal } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  // Landing here via ?signin=1 means ProtectedRoute redirected a signed-out
  // visitor away from a gated page (e.g. /dashboard). Open the sign-in modal
  // automatically instead of leaving them to notice the "Sign in" button
  // themselves — AuthModal's afterLogin sends them on to where they were
  // headed once they've signed in.
  useEffect(() => {
    if (searchParams.get("signin") === "1") {
      openAuthModal("signin");
      searchParams.delete("signin");
      setSearchParams(searchParams, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) return null;
  if (user) return <Navigate to="/dashboard" replace />;

  return (
    <PublicLayout>
      <title>Compass Astro — Your birth chart, read from the classical shastras</title>
      <meta
        name="description"
        content="Ask your Vedic astrology questions and get answers grounded in classical texts like Brihat Parashara Hora Shastra — with citations you can trace, not generic horoscope content."
      />
      <meta property="og:title" content="Compass Astro" />
      <meta property="og:description" content="Your birth chart, read aloud by the ancient shastras — with citations you can trace." />
      <meta property="og:image" content="/compass-hero-tight.png" />
      <meta property="og:type" content="website" />
      <meta name="twitter:card" content="summary_large_image" />
      {/* HERO
          The text stays inside the same centered max-w-6xl container the nav
          uses, so it lines up with the logo above it at every screen width.
          The image can't live in that same container and also reach the true
          browser edge — max-w-6xl is centered, so on any screen wider than
          ~1152px there's leftover margin outside it, and the image was
          stopping at the container's edge, not the window's edge (that gap
          is what looked like a hard line). So on desktop the image is taken
          out of the grid and absolutely positioned against this full-width
          section instead, anchored to the section's actual right edge. */}
      <section className="relative pt-0 pb-6 lg:min-h-[30vw] overflow-x-hidden">
        <div className="max-w-6xl mx-auto px-6 lg:px-12 grid lg:grid-cols-2 gap-8 items-start">
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
              <AuthButtons label="See your chart — free to start" />
              <p className="mt-4 text-xs text-[color:var(--jai-text-muted)] max-w-md">
                Your chart, chats and uploaded books stay private to your account.
              </p>
            </div>
          </div>

          {/* Mobile/tablet: image stacks normally below the text. Hidden on
              desktop, where the true edge-to-edge version below takes over. */}
          <div className="fade-up delay-1 lg:hidden">
            <img
              src="/compass-hero-tight.png"
              alt="A compass marking Growth, Success, Love, Wisdom, Marriage, Happiness, Health and Money, set against a starfield"
              className="w-full h-auto object-contain"
            />
          </div>
        </div>

        {/* Desktop: bleeds to the section's real right edge (the true browser
            edge), not the max-w-6xl container's edge. */}
        <div className="hidden lg:block absolute top-0 right-0 w-[52vw] fade-up delay-1">
          <img
            src="/compass-hero-tight.png"
            alt="A compass marking Growth, Success, Love, Wisdom, Marriage, Happiness, Health and Money, set against a starfield"
            className="w-full h-auto object-contain"
          />
        </div>
      </section>

      <CredibilityBar />

      <HowItWorks />

      <ProductPreview />

      {/* FEATURES */}
      <section className="max-w-6xl mx-auto px-6 lg:px-12 mt-24 grid grid-cols-1 sm:grid-cols-3 gap-6 fade-up delay-2">
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
          <AuthButtons compact label="Cast your chart free" />
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
