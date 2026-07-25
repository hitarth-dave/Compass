import { useState } from "react";
import { Check } from "lucide-react";
import PublicLayout from "@/components/PublicLayout";
import AuthButtons from "@/components/AuthButtons";
import WaitlistModal from "@/components/WaitlistModal";
import FAQ from "@/components/FAQ";
import { useAuth } from "@/context/AuthContext";

const FAQ_ITEMS = [
  {
    q: "Is Compass Astro really free right now?",
    a: "Yes — every feature on Seeker is free and unlimited while we're in beta. Sadhaka and Acharya are paid tiers we're building checkout for; join the waitlist and we'll email you the moment they're live.",
  },
  {
    q: "Can I cancel anytime?",
    a: "Yes — there's no lock-in. Once paid plans launch, cancel from Settings and you'll keep access through the end of your current billing period.",
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
    name: "Seeker",
    price: "Free",
    cadence: "",
    tagline: "Cast your chart and start asking.",
    features: [
      "Full sidereal Kundali",
      "Current Mahadasha & today's transits",
      "Unlimited questions — free while in beta",
      "Reasoning panel on any answer",
    ],
    cta: "Start free",
    kind: "free",
    featured: false,
  },
  {
    name: "Sadhaka",
    price: "$9",
    cadence: "/ month",
    tagline: "For steady, ongoing counsel.",
    features: [
      "Everything in Seeker",
      "Divisional (varga) charts",
      "Upload your own PDF texts",
      "Transit alerts for key periods (coming soon)",
    ],
    cta: "Join waitlist",
    kind: "waitlist",
    featured: true,
  },
  {
    name: "Acharya",
    price: "$29",
    cadence: "/ month",
    tagline: "Depth for the serious student.",
    features: [
      "Everything in Sadhaka",
      "Yearly Varshaphala reading (coming soon)",
      "Muhurta (timing) requests",
      "Priority model & longer answers",
      "Early access to new features",
    ],
    cta: "Join waitlist",
    kind: "waitlist",
    featured: false,
  },
];

export default function Pricing() {
  const [waitlistTier, setWaitlistTier] = useState(null);

  return (
    <PublicLayout>
      <title>Pricing — Compass Astro</title>
      <meta
        name="description"
        content="Compass Astro is free while in beta. See what's on Seeker, Sadhaka and Acharya, and join the waitlist for paid plans."
      />

      <section className="max-w-3xl mx-auto px-6 lg:px-12 pt-6 text-center fade-up">
        <div className="overline mb-6">Pricing</div>
        <h1 className="font-serif-display text-5xl sm:text-6xl text-[color:var(--jai-parchment)]">
          Free while in beta. <em className="text-[color:var(--jai-gold-display)]">Go deeper when you're ready.</em>
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
          Compass Astro is free to use in full while we're in beta. Sadhaka and Acharya are taking
          waitlist signups — you'll be the first to know when checkout opens.
        </p>
        <div className="mt-8 flex justify-center">
          <AuthButtons label="Start free, no card needed" />
        </div>
      </section>

      <FAQ items={FAQ_ITEMS} title="Before you start." />

      {waitlistTier && (
        <WaitlistModal tier={waitlistTier} onClose={() => setWaitlistTier(null)} />
      )}
    </PublicLayout>
  );
}

// A single button that either opens the shared auth modal (free tier) or
// the waitlist modal (paid tiers with no checkout wired yet) — styled by
// prominence either way.
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
