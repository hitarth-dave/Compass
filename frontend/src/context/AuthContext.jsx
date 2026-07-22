import { useState, useEffect, createContext, useContext, useCallback } from "react";
import axios from "axios";

axios.defaults.withCredentials = true;

// Fallback for browsers that block cross-site cookies (Safari ITP, strict
// tracking-prevention modes, some mobile browsers): store the session token
// and send it as a Bearer header on every request. The cookie still works
// wherever it's supported; this just adds a second path that always works.
const TOKEN_KEY = "compass_session_token";

export function setStoredToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
    axios.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  }
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_KEY);
  delete axios.defaults.headers.common["Authorization"];
}

// For raw fetch() calls (e.g. streaming responses axios can't handle) that
// need to attach the same Bearer fallback axios gets automatically.
export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY);
}

// Apply any previously stored token immediately on load, before the first
// request goes out.
const existingToken = localStorage.getItem(TOKEN_KEY);
if (existingToken) {
  axios.defaults.headers.common["Authorization"] = `Bearer ${existingToken}`;
}

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  // Auth modal — shared across the header "Sign in" button, the hero CTA,
  // and the bottom-of-page CTA, so there's exactly ONE real sign-in/sign-up
  // surface in the app instead of duplicated button sets on every page.
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState("signin"); // "signin" | "signup"

  const checkAuth = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/auth/me`);
      setUser(res.data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const logout = async () => {
    try { await axios.post(`${API}/auth/logout`); } catch {}
    clearStoredToken();
    setUser(null);
  };

  const openAuthModal = (mode = "signin") => {
    setAuthModalMode(mode);
    setAuthModalOpen(true);
  };
  const closeAuthModal = () => setAuthModalOpen(false);

  return (
    <AuthContext.Provider
      value={{
        user, setUser, loading, refresh: checkAuth, logout,
        authModalOpen, authModalMode, openAuthModal, closeAuthModal,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
