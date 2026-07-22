import { useAuth } from "@/context/AuthContext";

// This used to render separate Google/Apple buttons that both redirected to
// Emergent's hosted OAuth page. Now there's exactly one real auth surface —
// AuthModal — so every one of these is just a styled entry point into it,
// which is also what fixes the "Google button shown twice on one page"
// duplication: the actual sign-in controls now live in a single place.
export default function AuthButtons({ compact = false, label = "Sign in" }) {
  const { openAuthModal } = useAuth();
  return (
    <button
      onClick={() => openAuthModal("signin")}
      className={`gold-btn rounded-full ${compact ? "px-6 py-3" : "px-8 py-4"} font-serif-display text-lg inline-flex items-center justify-center gap-3 glow-hover`}
      data-testid="open-auth-modal-btn"
    >
      {label}
    </button>
  );
}
