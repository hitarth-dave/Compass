import { Navigate, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export const REDIRECT_KEY = "compass_redirect_after_login";

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="animate-spin text-[color:var(--jai-gold)]" size={28} />
      </div>
    );
  }

  if (!user) {
    // Previously this silently dumped visitors on the homepage with no
    // explanation and no way back to what they were trying to reach.
    // Remember where they were headed, then land on Home with a flag that
    // opens the sign-in modal automatically and reads as intentional.
    sessionStorage.setItem(REDIRECT_KEY, location.pathname + location.search);
    return <Navigate to="/?signin=1" replace />;
  }

  return children;
}
