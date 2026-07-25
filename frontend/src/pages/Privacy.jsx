import PublicLayout from "@/components/PublicLayout";

export default function Privacy() {
  return (
    <PublicLayout>
      <title>Privacy Policy — Compass Astro</title>
      <meta name="description" content="How Compass Astro collects, uses, and protects your data." />

      <section className="max-w-3xl mx-auto px-6 lg:px-12 pt-6 pb-24 fade-up">
        <div className="overline mb-6">Privacy Policy</div>
        <h1 className="font-serif-display text-4xl sm:text-5xl text-[color:var(--jai-parchment)] mb-4">
          Your data, plainly explained.
        </h1>
        <p className="text-sm text-[color:var(--jai-text-muted)] mb-12">Last updated: July 2026</p>

        <div className="space-y-10 text-[color:var(--jai-green-deep)] leading-relaxed">
          <div>
            <h2 className="font-serif-display text-2xl mb-3">What we collect</h2>
            <ul className="list-disc pl-5 space-y-2 text-sm">
              <li>Account details: name, email, and password (stored as a salted hash — we never see or store your plain-text password).</li>
              <li>Birth details you provide to cast a chart: date, time, and place of birth.</li>
              <li>Your current location, when you provide it separately for transits and Panchang.</li>
              <li>Chat questions and conversation history, and any PDF texts you choose to upload.</li>
              <li>Basic product-analytics events (pages viewed, buttons clicked), collected via PostHog.</li>
            </ul>
          </div>

          <div>
            <h2 className="font-serif-display text-2xl mb-3">Session recordings</h2>
            <p className="text-sm">
              We use PostHog to record how people use the app, so we can find and fix confusing or broken
              flows. Session recordings mask the actual text you type into any input field — birth
              details, chat questions, contact form — so that content isn't captured in the recording
              itself. Layout, clicks, and navigation are still recorded. If you'd rather opt out of
              analytics entirely, contact us and we'll exclude your account.
            </p>
          </div>

          <div>
            <h2 className="font-serif-display text-2xl mb-3">How we use it</h2>
            <p className="text-sm">
              Your birth details and questions are sent to Anthropic's Claude API to generate your
              readings and answers — this is the core of the product. We use your data to run the
              service, respond to support requests, and improve the product. We do not sell your
              personal data, and we do not share it with advertisers.
            </p>
          </div>

          <div>
            <h2 className="font-serif-display text-2xl mb-3">Who we share data with</h2>
            <p className="text-sm mb-3">We use a small number of service providers to run Compass Astro:</p>
            <ul className="list-disc pl-5 space-y-2 text-sm">
              <li><strong>Anthropic</strong> (Claude API) — processes your questions and chart data to generate answers.</li>
              <li><strong>MongoDB Atlas</strong> — stores your account, chart, and conversation data.</li>
              <li><strong>Google</strong> — if you choose to sign in with Google.</li>
              <li><strong>Resend</strong> — sends verification, password reset, and contact-form emails.</li>
              <li><strong>PostHog</strong> — product analytics, as described above.</li>
            </ul>
            <p className="text-sm mt-3">Each of these providers only receives what's needed to perform its function.</p>
          </div>

          <div>
            <h2 className="font-serif-display text-2xl mb-3">Your rights</h2>
            <p className="text-sm">
              You can review and update your account details from Settings at any time. You can permanently
              delete your account and associated data from Settings → Delete account. If you're in a
              jurisdiction with specific data-protection rights (such as the EU's GDPR or India's DPDP
              Act), you may also have rights to request a copy of your data or object to certain processing
              — contact us and we'll respond promptly.
            </p>
          </div>

          <div>
            <h2 className="font-serif-display text-2xl mb-3">Data retention</h2>
            <p className="text-sm">
              We retain your account and chart data for as long as your account is active. Deleting your
              account removes your personal data from our active systems; some records may persist briefly
              in backups before they age out.
            </p>
          </div>

          <div>
            <h2 className="font-serif-display text-2xl mb-3">Questions</h2>
            <p className="text-sm">
              Reach out any time at{" "}
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
