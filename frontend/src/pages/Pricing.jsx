import { Check } from "lucide-react";
import PublicLayout, { useSignIn } from "@/components/PublicLayout";
import AuthButtons from "@/components/AuthButtons";

const TIERS = [
  {
    name: "Seeker",
    price: "Free",
    cadence: "",
    tagline: "Cast your chart and start asking.",
    features: [
      "Full sidereal Kundali",
      "Current Mahadasha & today's transits",
      "Up to 10 questions a month",
      "Reasoning panel on any answer",
    ],
    cta: "Start free",
    featured: false,
  },
  {
    name: "Sadhaka",
    price: "$9",
    cadence: "/ month",
    tagline: "For steady, ongoing counsel.",
    features: [
      "Everything in Seeker",
      "Unlimited questions",
      "Divisional (varga) charts",
      "Upload your own PDF texts",
      "Transit alerts for key periods",
    ],
    cta: "Choose Sadhaka",
    featured: true,
  },
  {
    name: "Acharya",
    price: "$29",
    cadence: "/ month",
    tagline: "Depth for the serious student.",
    features: [
      "Everything in Sadhaka",
      "Yearly Varshaphala reading",
      "Muhurta (timing) requests",
      "Priority model & longer answers",
      "Early access to new features",
    ],
    cta: "Choose Acharya",
    featured: false,
  },
];

export default function Pricing() {
  return (
    <PublicLayout>
      <section className="max-w-3xl mx-auto px-6 lg:px-12 pt-6 text-center fade-up">
        <div className="overline mb-6">Pricing</div>
        <h1 className="font-serif-display text-5xl sm:text-6xl text-[color:var(--jai-parchment)]">
          Start free. <em className="text-[color:var(--jai-gold)]">Go deeper when you're ready.</em>
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
            {t.featured && <div className="overline mb-3">Most chosen</div>}
            <h3 className="font-serif-display text-2xl text-[color:var(--jai-green-deep)]">{t.name}</h3>
            <p className="mt-1 text-sm text-[color:var(--jai-text-muted)]">{t.tagline}</p>
            <div className="mt-6 flex items-baseline gap-1">
              <span className="font-serif-display text-5xl text-[color:var(--jai-parchment)]">{t.price}</span>
              <span className="text-sm text-[color:var(--jai-text-muted)]">{t.cadence}</span>
            </div>
            <ul className="mt-8 space-y-3 flex-1">
              {t.features.map((f) => (
                <li key={f} className="flex items-start gap-3 text-sm text-[color:var(--jai-green-deep)]">
                  <Check size={16} className="text-[color:var(--jai-gold)] mt-0.5 shrink-0" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <div className="mt-8">
              <AuthButtonsInline label={t.cta} featured={t.featured} />
            </div>
          </div>
        ))}
      </section>

      <section className="max-w-2xl mx-auto px-6 lg:px-12 mt-24 text-center fade-up">
        <p className="text-sm text-[color:var(--jai-text-muted)]">
          Prices shown are placeholders for layout — set your real plans before launch. All tiers
          share one sign-in.
        </p>
        <div className="mt-8 flex justify-center">
          <AuthButtons />
        </div>
      </section>
    </PublicLayout>
  );
}

// A single button that routes into the same sign-in flow, styled by prominence.
function AuthButtonsInline({ label, featured }) {
  const signIn = useSignIn();
  return (
    <button
      onClick={signIn}
      className={`w-full rounded-full px-6 py-3 font-serif-display text-lg transition-colors ${
        featured
          ? "bg-[color:var(--jai-green)] text-[color:var(--jai-surface)] hover:bg-[color:var(--jai-green-deep)]"
          : "gold-btn"
      }`}
    >
      {label}
    </button>
  );
}
