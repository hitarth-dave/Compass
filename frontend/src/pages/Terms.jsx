import PublicLayout from "@/components/PublicLayout";

export default function Terms() {
  return (
    <PublicLayout>
      <title>Terms of Service — Compass Astro</title>
      <meta name="description" content="The terms governing your use of Compass Astro." />

      <section className="max-w-3xl mx-auto px-6 lg:px-12 pt-6 pb-24 fade-up">
        <div className="overline mb-6">Terms of Service</div>
        <h1 className="font-serif-display text-4xl sm:text-5xl text-[color:var(--jai-parchment)] mb-4">
          The short version, honestly written.
        </h1>
        <p className="text-sm text-[color:var(--jai-text-muted)] mb-12">Last updated: July 2026</p>

        <div className="space-y-10 text-[color:var(--jai-green-deep)] leading-relaxed">
          <div>
            <h2 className="font-serif-display text-2xl mb-3">What Compass Astro is</h2>
            <p className="text-sm">
              Compass Astro computes your Vedic (sidereal) birth chart from real astronomical data and
              answers your questions by drawing on classical Jyotish texts, using an AI model. It is
              offered for guidance, reflection, and educational purposes — as our homepage puts it,
              Jyotish is a compass, not a verdict.
            </p>
          </div>

          <div>
            <h2 className="font-serif-display text-2xl mb-3">Not professional advice</h2>
            <p className="text-sm">
              Compass Astro does not provide medical, legal, financial, or psychological advice, and
              nothing in the app should be treated as a substitute for advice from a qualified
              professional in those fields. Decisions about your health, finances, relationships, or
              legal matters are yours to make; we provide astrological perspective, not instructions.
            </p>
          </div>

          <div>
            <h2 className="font-serif-display text-2xl mb-3">Your account</h2>
            <p className="text-sm">
              You're responsible for keeping your login credentials secure and for the accuracy of the
              birth details you provide — chart accuracy depends on it. You must be at least 18, or the
              age of majority in your jurisdiction, to create an account.
            </p>
          </div>

          <div>
            <h2 className="font-serif-display text-2xl mb-3">Plans and billing</h2>
            <p className="text-sm">
              Compass Astro is currently free to use in full while in beta. Paid plans (Sadhaka, Acharya)
              are in development; if you join a waitlist for one, we'll only use that email to notify you
              when checkout is available. Pricing and features for paid plans may change before launch.
            </p>
          </div>

          <div>
            <h2 className="font-serif-display text-2xl mb-3">Acceptable use</h2>
            <p className="text-sm">
              Please don't use Compass Astro to attempt to disrupt the service, scrape or resell our
              classical-text corpus, impersonate another person, or upload content you don't have the
              right to share (e.g. copyrighted texts you don't own).
            </p>
          </div>

          <div>
            <h2 className="font-serif-display text-2xl mb-3">Changes</h2>
            <p className="text-sm">
              We may update these terms as the product evolves. We'll post the updated date at the top
              of this page; continued use after a change means you accept the update.
            </p>
          </div>

          <div>
            <h2 className="font-serif-display text-2xl mb-3">Contact</h2>
            <p className="text-sm">
              Questions about these terms? Reach us at{" "}
              <a href="mailto:daveastroanalyst@gmail.com" className="text-[color:var(--jai-gold)] hover:underline">
                daveastroanalyst@gmail.com
              </a>{" "}
              or via the <a href="/contact" className="text-[color:var(--jai-gold)] hover:underline">Contact</a> page.
            </p>
          </div>
        </div>
      </section>
    </PublicLayout>
  );
}
