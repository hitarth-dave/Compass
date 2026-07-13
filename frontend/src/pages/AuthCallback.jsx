import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AuthCallback() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash;
    const match = hash.match(/session_id=([^&]+)/);
    if (!match) {
      navigate("/", { replace: true });
      return;
    }
    const sessionId = match[1];
    // Clear hash immediately
    window.history.replaceState(null, "", window.location.pathname);
    (async () => {
      try {
        const res = await axios.post(`${API}/auth/session`, { session_id: sessionId });
        setUser(res.data);
        navigate("/dashboard", { replace: true, state: { user: res.data } });
      } catch (e) {
        navigate("/", { replace: true });
      }
    })();
  }, [navigate, setUser]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <Loader2 className="animate-spin text-[color:var(--jai-gold)]" size={32} />
    </div>
  );
}
