import { useState } from "react";
import { Check } from "lucide-react";
import PublicLayout from "@/components/PublicLayout";
import AuthButtons from "@/components/AuthButtons";
import WaitlistModal from "@/components/WaitlistModal";
import FAQ from "@/components/FAQ";
import { useAuth } from "@/context/AuthContext";

const FAQ_ITEMS = [
  {
    q: "Is there a free tier?",
    a: "Not right now — all three tiers (Basic, Standard, Advanced) are opening through a waitlist as we finish checkout. Join the tier you want and we'll email you the moment it's live.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes — there's no lock-in. Once billing launches, cancel from Settings and you'll keep access through the end of your current billing period.",
  },
  {
    q: "Is my birth data and chat history private?",
    a: "Your chart, conversations and any PDFs you upload are private to your account. We don't sell or share your data. See our Privacy Policy for details.",
  },
  {
    q: "How is this different from a generic horoscope app?",
    a: "Compass Astro reads your actual sidereal Kundali — computed from Swiss Ephemeris — against classical texts like Brihat Parashara Hora Shastra, not generic sun-sign content. Every answer can show its reasoning.",
  },
  {
    q: "Can I upload my own astrology texts?",
    a: "Yes — upload PDFs and Compass Astro will read them alongside the standard classical corpus.",
  },
];

const TIERS = [
  {
    name: "Basic",
    price: "$0.99",
    cadence: "/ week",
    tagline: "Cast your chart and start asking.",
    features: [
      "Full sidereal Kundali",
      "Current Mahadasha & today's transits",
      "Unlimited questions",
      "Reasoning panel on any answer",
    ],
    cta: "Join waitlist",
    kind: "waitlist",
    featured: false,
  },
  {
    name: "Standard",
    price: "$2.99",
    cadence: "/ week",
    tagline: "For steady, ongoing counsel.",
    features: [
      "Everything in Basic",
      "Divisional (varga) charts",
      "Upload your own PDF texts",
      "Transit alerts for key periods (coming soon)",
    ],
    cta: "Join waitlist",
    kind: "waitlist",
    featured: true,
  },
  {
    name: "Advanced",
    price: "$6.99",
    cadence: "/ week",
    tagline: "The astrologer's tier — coming soon.",
    features: [
      "Everything in Standard",
      "Yearly Varshaphala reading (coming soon)",
      "Muhurta (timing) requests",
      "Priority model & longer answers",
      "Early access to new features",
    ],
    cta: "Join waitlist",
    kind: "waitlist",
    featured: false,
    comingSoon: true,
  },
];

export default function Pricing() {
  const [waitlistTier, setWaitlistTier] = useState(null);

  return (
    <PublicLayout>
      <title>Pricing — Compass Astro</title>
      <meta
        name="description"
        content="See what's on Basic, Standard and Advanced, and join the waitlist — checkout is opening soon."
      />

      <section className="max-w-3xl mx-auto px-6 lg:px-12 pt-6 text-center fade-up">
        <div className="overline mb-6">Pricing</div>
        <h1 className="font-serif-display text-5xl sm:text-6xl text-[color:var(--jai-parchment)]">
          Simple pricing. <em className="text-[color:var(--jai-gold-display)]">Go as deep as you need.</em>
        </h1>
        <p className="mt-6 text-lg text-[color:var(--jai-text-muted)] leading-relaxed">
          Every plan reads from the same classical corpus. You're paying for depth and volume, never
          for a different truth.
        </p>
      </section>

      <section className="max-w-6xl mx-auto px-6 lg:px-12 mt-16 grid grid-cols-1 md:grid-cols-3 gap-6 items-start fade-up delay-1">
        {TIERS.map((t) => (
          <div
            key={t.name}
            className={`card-surface p-8 flex flex-col ${t.featured ? "ring-1 ring-[color:var(--jai-gold)] md:-translate-y-3" : ""}`}
            data-testid={`tier-${t.name.toLowerCase()}`}
          >
            {t.featured && <div className="overline mb-3">Recommended</div>}
            {t.comingSoon && <div className="overline mb-3 text-[color:var(--jai-text-muted)]">Coming soon</div>}
            <h3 className="font-serif-display text-2xl text-[color:var(--jai-green-deep)]">{t.name}</h3>
            <p className="mt-1 text-sm text-[color:var(--jai-text-muted)]">{t.tagline}</p>
            <div className="mt-6 flex items-baseline gap-1">
              <span className="font-serif-display text-5xl text-[color:var(--jai-parchment)]">{t.price}</span>
              <span className="text-sm text-[color:var(--jai-text-muted)]">{t.cadence}</span>
            </div>
            <ul className="mt-8 space-y-3 flex-1">
              {t.features.map((f) => (
                <li key={f} className="flex items-start gap-3 text-sm text-[color:var(--jai-green-deep)]">
                  <Check size={16} className="text-[color:var(--jai-gold-display)] mt-0.5 shrink-0" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <div className="mt-8">
              <AuthButtonsInline tier={t} onWaitlist={() => setWaitlistTier(t.name)} />
            </div>
          </div>
        ))}
      </section>

      <section className="max-w-2xl mx-auto px-6 lg:px-12 mt-24 text-center fade-up">
        <p className="text-sm text-[color:var(--jai-text-muted)]">
          All three tiers are taking waitlist signups while we finish checkout — you'll be the first
          to know when your tier opens.
        </p>
        <div className="mt-8 flex justify-center">
          <AuthButtons label="Already have an account? Sign in" />
        </div>
      </section>

      <FAQ items={FAQ_ITEMS} title="Before you start." />

      {waitlistTier && (
        <WaitlistModal tier={waitlistTier} onClose={() => setWaitlistTier(null)} />
      )}
    </PublicLayout>
  );
}

// A single button that opens the waitlist modal — all three tiers are
// waitlist-only until checkout is wired up.
function AuthButtonsInline({ tier, onWaitlist }) {
  const { openAuthModal } = useAuth();
  return (
    <button
      onClick={() => (tier.kind === "waitlist" ? onWaitlist() : openAuthModal("signin"))}
      className={`w-full rounded-full px-6 py-3 font-serif-display text-lg transition-colors ${
        tier.featured
          ? "bg-[color:var(--jai-green)] text-[color:var(--jai-surface)] hover:bg-[color:var(--jai-green-deep)]"
          : "gold-btn"
      }`}
      data-testid={`tier-cta-${tier.name.toLowerCase()}`}
    >
      {tier.cta}
    </button>
  );
}
