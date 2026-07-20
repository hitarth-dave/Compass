import { useSignIn } from "@/components/PublicLayout";

function GoogleGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.9 2.5 30.4 0 24 0 14.6 0 6.5 5.4 2.5 13.2l7.9 6.2C12.5 13.3 17.8 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.5 24.5c0-1.7-.2-3.3-.5-4.9H24v9.3h12.7c-.5 3-2.2 5.5-4.7 7.2l7.6 5.9c4.4-4.1 6.9-10.1 6.9-17.5z"/>
      <path fill="#FBBC05" d="M10.4 28.6c-.6-1.6-.9-3.4-.9-5.1s.3-3.5.9-5.1l-7.9-6.2C1 15.7 0 19.7 0 24s1 8.3 2.5 11.8l7.9-7.2z"/>
      <path fill="#34A853" d="M24 48c6.4 0 11.9-2.1 15.9-5.7l-7.6-5.9c-2.1 1.4-4.8 2.3-8.3 2.3-6.2 0-11.5-3.8-13.6-9.4l-7.9 6.2C6.5 42.6 14.6 48 24 48z"/>
    </svg>
  );
}

function AppleGlyph() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
      <path d="M16.365 1.43c0 1.14-.417 2.2-1.11 2.98-.84.94-2.22 1.66-3.36 1.57-.14-1.13.44-2.32 1.11-3.06.75-.83 2.06-1.44 3.13-1.49.02.14.03.28.03.41zM20.9 17.02c-.55 1.27-.82 1.84-1.53 2.96-.99 1.56-2.39 3.5-4.12 3.51-1.54.02-1.94-1-4.03-.99-2.09.01-2.53 1.01-4.07.99-1.73-.01-3.05-1.76-4.04-3.32-2.77-4.36-3.06-9.48-1.35-12.2 1.21-1.93 3.13-3.06 4.93-3.06 1.83 0 2.98 1 4.49 1 1.47 0 2.36-1 4.48-1 1.6 0 3.3.87 4.51 2.38-3.96 2.17-3.32 7.82.75 9.72z"/>
    </svg>
  );
}

// Both providers route through the same Emergent OAuth screen (the app has a
// single OAuth entrypoint). Provider selection happens on Emergent's page.
export default function AuthButtons({ compact = false }) {
  const signIn = useSignIn();
  return (
    <div className={`flex ${compact ? "flex-row" : "flex-col sm:flex-row"} gap-3`}>
      <button
        onClick={signIn}
        className="gold-btn rounded-full px-7 py-3.5 font-serif-display text-lg inline-flex items-center justify-center gap-3 glow-hover"
        data-testid="google-signin-btn"
      >
        <GoogleGlyph /> Continue with Google
      </button>
      <button
        onClick={signIn}
        className="rounded-full px-7 py-3.5 font-serif-display text-lg inline-flex items-center justify-center gap-3 border border-[color:var(--jai-green)] text-[color:var(--jai-green-deep)] bg-transparent hover:bg-[color:var(--jai-green)] hover:text-[color:var(--jai-surface)] transition-colors"
        data-testid="apple-signin-btn"
      >
        <AppleGlyph /> Continue with Apple
      </button>
    </div>
  );
}
