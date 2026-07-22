import { Compass } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import AuthModal from "@/components/AuthModal";

const NAV = [
  { to: "/", label: "Home" },
  { to: "/astrology", label: "Astrology" },
  { to: "/pricing", label: "Pricing" },
  { to: "/contact", label: "Contact" },
];

export function PublicNav() {
  const location = useLocation();
  const { user, openAuthModal } = useAuth();
  return (
    <header className="relative z-20 flex items-center justify-between max-w-6xl mx-auto px-6 lg:px-12 py-8 fade-up">
      <Link to="/" className="flex items-center gap-3" data-testid="nav-brand">
        <div className="w-10 h-10 rounded-full border border-[color:var(--jai-gold)] flex items-center justify-center">
          <Compass size={18} className="text-[color:var(--jai-gold)]" />
        </div>
        <div>
          <div className="font-serif-display text-2xl leading-none text-[color:var(--jai-green-deep)]">Compass Astro</div>
          <div className="overline mt-1">Ancient wisdom, clear direction</div>
        </div>
      </Link>

      <nav className="hidden md:flex items-center gap-8">
        {NAV.map((item) => {
          const active = location.pathname === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`text-sm tracking-wide transition-colors ${
                active
                  ? "text-[color:var(--jai-gold)]"
                  : "text-[color:var(--jai-green-deep)] hover:text-[color:var(--jai-gold)]"
              }`}
              data-testid={`nav-${item.label.toLowerCase()}`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <button
        onClick={user ? undefined : () => openAuthModal("signin")}
        className="gold-btn rounded-full px-6 py-2.5 text-sm inline-flex items-center gap-2"
        data-testid="nav-signin"
      >
        {user ? "Open app" : "Sign in"}
      </button>
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className="relative z-20 border-t border-[color:var(--jai-border)] mt-32">
      <div className="max-w-6xl mx-auto px-6 lg:px-12 py-14 grid grid-cols-1 sm:grid-cols-4 gap-10">
        <div className="sm:col-span-2">
          <div className="font-serif-display text-2xl text-[color:var(--jai-green-deep)]">Compass Astro</div>
          <p className="mt-3 text-sm text-[color:var(--jai-text-muted)] max-w-sm leading-relaxed">
            Vedic astrology read from the classical shastras, answered in plain language.
            Sidereal · Lahiri Ayanamsa · Vimshottari Dasha.
          </p>
        </div>
        <div>
          <div className="overline mb-4">Explore</div>
          <ul className="space-y-2 text-sm text-[color:var(--jai-text-muted)]">
            {NAV.map((i) => (
              <li key={i.to}>
                <Link to={i.to} className="hover:text-[color:var(--jai-gold)]">{i.label}</Link>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <div className="overline mb-4">Legal</div>
          <ul className="space-y-2 text-sm text-[color:var(--jai-text-muted)]">
            <li><Link to="/contact" className="hover:text-[color:var(--jai-gold)]">Contact</Link></li>
            <li><span className="opacity-70">Privacy</span></li>
            <li><span className="opacity-70">Terms</span></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-[color:var(--jai-border)]">
        <div className="max-w-6xl mx-auto px-6 lg:px-12 py-6 text-xs text-[color:var(--jai-text-muted)] tracking-wide flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>© {new Date().getFullYear()} Compass Astro. Guidance from ancient shastras.</span>
          <span>Powered by Claude</span>
        </div>
      </div>
    </footer>
  );
}

export default function PublicLayout({ children }) {
  return (
    <div className="relative min-h-screen overflow-x-hidden" data-testid="public-layout">
      <PublicNav />
      <main className="relative z-10">{children}</main>
      <PublicFooter />
      <AuthModal />
    </div>
  );
}
