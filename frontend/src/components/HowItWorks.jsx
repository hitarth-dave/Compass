import { LogIn, Compass as CompassIcon, MessageCircle } from "lucide-react";

const STEPS = [
  {
    Icon: LogIn,
    title: "Sign in, enter your birth details",
    body: "Date, time and place of birth — that's all we need to cast an accurate sidereal chart.",
  },
  {
    Icon: CompassIcon,
    title: "We cast your Kundali instantly",
    body: "Swiss Ephemeris computes your chart, current Mahadasha, and today's transits the moment you land.",
  },
  {
    Icon: MessageCircle,
    title: "Ask anything, in plain language",
    body: "Career, love, timing, direction — get an answer grounded in the classics, with the reasoning one tap away.",
  },
];

export default function HowItWorks() {
  return (
    <section className="max-w-5xl mx-auto px-6 lg:px-12 mt-24 fade-up delay-1" data-testid="how-it-works">
      <div className="text-center mb-12">
        <div className="overline mb-4">How it works</div>
        <h2 className="font-serif-display text-3xl sm:text-4xl text-[color:var(--jai-green-deep)]">
          Three steps to your bearing.
        </h2>
      </div>
      <div className="grid sm:grid-cols-3 gap-10 sm:gap-6">
        {STEPS.map((s, i) => (
          <div key={s.title} className="relative text-center sm:text-left">
            <div className="flex sm:flex-col items-center sm:items-start gap-4 sm:gap-0">
              <div className="w-12 h-12 rounded-full flex items-center justify-center border border-[color:var(--jai-border-gold)] text-[color:var(--jai-gold)] shrink-0 sm:mb-5">
                <s.Icon size={18} />
              </div>
              <div className="font-serif-display text-lg text-[color:var(--jai-green-deep)] leading-snug">
                <span className="text-[color:var(--jai-gold)] mr-1">{i + 1}.</span> {s.title}
              </div>
            </div>
            <p className="mt-3 text-sm text-[color:var(--jai-text-muted)] leading-relaxed">{s.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
