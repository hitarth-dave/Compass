// A light trust/credibility strip. Swap the STAT copy for real numbers
// (users, charts cast, questions answered) once you have them — until then
// these lean on verifiable methodology rather than invented social proof.
const FACTS = [
  "Sidereal · Lahiri Ayanamsa",
  "Vimshottari Dasha system",
  "Computed from Swiss Ephemeris",
  "6 classical shastras, cited by name",
];

export default function CredibilityBar() {
  return (
    <section className="max-w-5xl mx-auto px-6 lg:px-12 mt-16 fade-up" data-testid="credibility-bar">
      <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 py-6 border-y border-[color:var(--jai-border)]">
        {FACTS.map((f) => (
          <span
            key={f}
            className="text-xs tracking-wide uppercase text-[color:var(--jai-text-muted)]"
          >
            {f}
          </span>
        ))}
      </div>
    </section>
  );
}
