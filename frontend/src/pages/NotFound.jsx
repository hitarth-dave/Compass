import { Link } from "react-router-dom";
import PublicLayout from "@/components/PublicLayout";

export default function NotFound() {
  return (
    <PublicLayout>
      <title>Page not found — Compass Astro</title>
      <meta name="robots" content="noindex" />
      <section className="max-w-2xl mx-auto px-6 lg:px-12 pt-16 pb-24 text-center fade-up">
        <div className="overline mb-6">404</div>
        <h1 className="font-serif-display text-5xl sm:text-6xl text-[color:var(--jai-parchment)] mb-6">
          This page hasn't been <em className="text-[color:var(--jai-gold-display)]">charted yet.</em>
        </h1>
        <p className="text-lg text-[color:var(--jai-text-muted)] leading-relaxed mb-10">
          The page you're looking for doesn't exist, or the link may be out of date.
        </p>
        <Link to="/" className="gold-btn rounded-full px-8 py-4 font-serif-display text-lg inline-flex items-center justify-center">
          Back to home
        </Link>
      </section>
    </PublicLayout>
  );
}
