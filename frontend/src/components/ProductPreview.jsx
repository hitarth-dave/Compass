import { MessageCircle } from "lucide-react";
import KundaliChart from "@/components/KundaliChart";

// A illustrative sample chart + a snippet of what a real answer reads like.
// Nothing here is wired to real data — it exists purely so a first-time
// visitor can see, before signing in, what "your chart, read aloud" actually
// looks like. Swap SAMPLE_PLANETS / SAMPLE_QA for a real anonymized example
// once you have one you like.
const SAMPLE_PLANETS = [
  { name: "Sun", house: 10, degree_in_sign: 14.32, nakshatra: "Uttara Phalguni", retrograde: false },
  { name: "Moon", house: 7, degree_in_sign: 22.1, nakshatra: "Vishakha", retrograde: false },
  { name: "Mars", house: 3, degree_in_sign: 3.4, nakshatra: "Krittika", retrograde: false },
  { name: "Mercury", house: 10, degree_in_sign: 28.6, nakshatra: "Hasta", retrograde: false },
  { name: "Jupiter", house: 11, degree_in_sign: 9.8, nakshatra: "Shatabhisha", retrograde: false },
  { name: "Venus", house: 9, degree_in_sign: 17.2, nakshatra: "Purva Ashadha", retrograde: false },
  { name: "Saturn", house: 1, degree_in_sign: 25.9, nakshatra: "Uttara Bhadrapada", retrograde: true },
  { name: "Rahu", house: 5, degree_in_sign: 11.0, nakshatra: "Purva Phalguni", retrograde: false },
  { name: "Ketu", house: 11, degree_in_sign: 11.0, nakshatra: "Shatabhisha", retrograde: false },
];

const SAMPLE_ASCENDANT = { degree_in_sign: 6.4, nakshatra: "Uttara Bhadrapada" };
const SAMPLE_ASCENDANT_SIGN = 12;

const SAMPLE_QA = {
  question: "Is this a good year to change jobs?",
  answer:
    "Your current Mahadasha is Jupiter, running through your 11th house of gains — that's a supportive backdrop for a move. Mercury sits with the Sun in your 10th house of career this year, which tends to sharpen how you're seen professionally. The stronger window opens once the Jupiter–Mercury Antardasha begins, roughly...",
};

export default function ProductPreview() {
  return (
    <section className="max-w-6xl mx-auto px-6 lg:px-12 mt-24 fade-up delay-2" data-testid="product-preview">
      <div className="text-center mb-10">
        <div className="overline mb-4">See it before you sign in</div>
        <h2 className="font-serif-display text-3xl sm:text-4xl text-[color:var(--jai-green-deep)]">
          This is what "read aloud" looks like.
        </h2>
        <p className="mt-3 text-[color:var(--jai-text-muted)] max-w-xl mx-auto">
          A sample chart and a sample answer — illustrative, not your data. Yours is cast the moment you sign in.
        </p>
      </div>

      <div className="card-surface p-6 sm:p-10 grid md:grid-cols-2 gap-10 items-center">
        <div>
          <KundaliChart
            planets={SAMPLE_PLANETS}
            ascendantSign={SAMPLE_ASCENDANT_SIGN}
            ascendant={SAMPLE_ASCENDANT}
            testid="preview-kundali-chart"
          />
          <p className="mt-2 text-center text-xs text-[color:var(--jai-text-muted)] tracking-wide">
            Sample Kundali — illustrative only
          </p>
        </div>

        <div>
          <div className="flex items-start gap-3 mb-4">
            <div className="w-8 h-8 rounded-full flex items-center justify-center bg-[color:var(--jai-gold)]/10 border border-[color:var(--jai-border-gold)] shrink-0">
              <MessageCircle size={14} className="text-[color:var(--jai-gold)]" />
            </div>
            <div className="gold-border rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-[color:var(--jai-green-deep)] font-serif-display italic">
              {SAMPLE_QA.question}
            </div>
          </div>
          <div className="parchment-tint rounded-2xl rounded-tl-sm border border-[color:var(--jai-border)] px-5 py-4">
            <p className="text-sm leading-relaxed text-[color:var(--jai-text)]">
              {SAMPLE_QA.answer}
            </p>
            <button
              type="button"
              className="mt-3 text-xs text-[color:var(--jai-gold)] hover:text-[color:var(--jai-gold-soft)] tracking-wide"
            >
              Show reasoning &amp; sources →
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
