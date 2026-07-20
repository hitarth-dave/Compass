import { Star, Orbit, Clock, ScrollText, Sparkles, Moon } from "lucide-react";
import PublicLayout from "@/components/PublicLayout";
import AuthButtons from "@/components/AuthButtons";

const READINGS = [
  { Icon: Star, title: "Kundali interpretation", body: "Your full sidereal birth chart — lagna, the twelve bhavas, and every graha's placement — read house by house against the classical rules, not generic sun-sign copy." },
  { Icon: Orbit, title: "Planetary transits (Gochara)", body: "Where the grahas move today relative to your natal Moon, and what each transit tends to open, test, or ripen. Timed, not vague." },
  { Icon: Clock, title: "Dashas & timing", body: "Your Vimshottari Mahadasha, Antardasha and deeper levels — so a prediction always comes with a 'when', not just a 'what'." },
  { Icon: Sparkles, title: "Yogas & combinations", body: "Classical yogas present in your chart, named with the source rule, so you can see exactly why a reading says what it says." },
  { Icon: ScrollText, title: "Remedies from the shastras", body: "Upayas matched to your chart and drawn from the tradition — mantra, daana, and observance, explained plainly and without fear-selling." },
  { Icon: Moon, title: "Ask in plain language", body: "Career, marriage, health, a decision this week — ask like you'd ask a wise friend. The reasoning is always one tap away." },
];

const TEXTS = [
  "Brihat Parashara Hora Shastra",
  "Phaladeepika",
  "Saravali",
  "Jaimini Sutras",
  "Brihat Jataka",
  "Sarvartha Chintamani",
];

export default function Astrology() {
  return (
    <PublicLayout>
      <section className="max-w-4xl mx-auto px-6 lg:px-12 pt-6 fade-up">
        <div className="overline mb-6">The practice</div>
        <h1 className="font-serif-display text-5xl sm:text-6xl leading-[0.98] text-[color:var(--jai-parchment)]">
          Everything a good astrologer would read — <em className="text-[color:var(--jai-gold)]">computed and explained.</em>
        </h1>
        <p className="mt-8 text-lg text-[color:var(--jai-text-muted)] leading-relaxed max-w-2xl">
          Compass Astro follows the sidereal zodiac with Lahiri Ayanamsa and the Vimshottari dasha
          system. It computes your chart from Swiss Ephemeris and reads it against the classical
          corpus — then translates the result into language you can act on.
        </p>
      </section>

      <section className="max-w-6xl mx-auto px-6 lg:px-12 mt-20 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 fade-up delay-1">
        {READINGS.map((r) => (
          <div key={r.title} className="card-surface p-6">
            <r.Icon size={20} className="text-[color:var(--jai-gold)] mb-4" />
            <h3 className="font-serif-display text-xl text-[color:var(--jai-green-deep)] leading-snug">{r.title}</h3>
            <p className="mt-3 text-sm text-[color:var(--jai-text-muted)] leading-relaxed">{r.body}</p>
          </div>
        ))}
      </section>

      <section className="max-w-4xl mx-auto px-6 lg:px-12 mt-32 text-center fade-up">
        <div className="overline mb-6">Rooted in the classics</div>
        <h2 className="font-serif-display text-4xl sm:text-5xl text-[color:var(--jai-green-deep)]">
          Sources, not guesswork.
        </h2>
        <p className="mt-6 text-[color:var(--jai-text-muted)] leading-relaxed max-w-2xl mx-auto">
          Readings draw on the foundational texts of Jyotish. You can also upload your own PDFs and
          have them read alongside the standard corpus.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          {TEXTS.map((t) => (
            <span key={t} className="gold-border rounded-full px-5 py-2 text-sm text-[color:var(--jai-green-deep)] font-serif-display">
              {t}
            </span>
          ))}
        </div>
      </section>

      <section className="max-w-3xl mx-auto px-6 lg:px-12 mt-32 text-center fade-up">
        <h2 className="font-serif-display text-4xl text-[color:var(--jai-parchment)]">
          See your own chart <em className="text-[color:var(--jai-gold)]">read aloud.</em>
        </h2>
        <div className="mt-8 flex justify-center">
          <AuthButtons />
        </div>
      </section>
    </PublicLayout>
  );
}
