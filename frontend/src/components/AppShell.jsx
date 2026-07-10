import { NavLink, useNavigate } from "react-router-dom";
import { LayoutGrid, MessageSquare, BookOpen, Sparkles, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function AppShell({ children }) {
  const navigate = useNavigate();
  const name = localStorage.getItem("jyotish_profile_name") || "Seeker";

  const nav = [
    { to: "/dashboard", label: "Kundali", Icon: LayoutGrid, testId: "nav-dashboard" },
    { to: "/chat", label: "Conversation", Icon: MessageSquare, testId: "nav-chat" },
    { to: "/library", label: "Library", Icon: BookOpen, testId: "nav-library" },
  ];

  const signOut = () => {
    localStorage.removeItem("jyotish_profile_id");
    localStorage.removeItem("jyotish_profile_name");
    navigate("/onboarding");
  };

  return (
    <div className="relative min-h-screen flex" data-testid="app-shell">
      <aside className="w-72 shrink-0 border-r border-[color:var(--jai-border)] bg-[color:var(--jai-bg)]/85 backdrop-blur-xl sticky top-0 h-screen flex flex-col z-10">
        <div className="p-8 border-b border-[color:var(--jai-border)]">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full border border-[color:var(--jai-gold)] flex items-center justify-center">
              <Sparkles size={18} className="text-[color:var(--jai-gold)]" />
            </div>
            <div>
              <div className="font-serif-display text-2xl leading-none text-[color:var(--jai-gold-soft)]">Jyotish AI</div>
              <div className="overline mt-1">Vedic Counsel</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {nav.map(({ to, label, Icon, testId }) => (
            <NavLink
              key={to}
              to={to}
              data-testid={testId}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                  isActive
                    ? "bg-[color:var(--jai-surface-2)] text-[color:var(--jai-gold-soft)] border border-[color:var(--jai-border)]"
                    : "text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-text)] hover:bg-[color:var(--jai-surface)]/60"
                }`
              }
            >
              <Icon size={17} />
              <span className="font-medium tracking-wide">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-6 border-t border-[color:var(--jai-border)]">
          <div className="text-xs text-[color:var(--jai-text-muted)] mb-1">Signed in as</div>
          <div className="font-serif-display text-xl text-[color:var(--jai-parchment)] mb-3" data-testid="profile-name">{name}</div>
          <Button
            variant="ghost"
            size="sm"
            onClick={signOut}
            data-testid="signout-btn"
            className="text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)] px-0"
          >
            <LogOut size={14} className="mr-2" /> Reset chart
          </Button>
        </div>
      </aside>

      <main className="flex-1 relative z-[1] overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
