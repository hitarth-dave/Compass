import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { useEffect } from "react";
import axios from "axios";
import "@/App.css";

import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider, useTheme } from "@/context/ThemeContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Home from "@/pages/Home";
import Astrology from "@/pages/Astrology";
import Pricing from "@/pages/Pricing";
import Contact from "@/pages/Contact";
import AuthCallback from "@/pages/AuthCallback";
import Onboarding from "@/pages/Onboarding";
import Dashboard from "@/pages/Dashboard";
import Chat from "@/pages/Chat";
import Library from "@/pages/Library";
import Settings from "@/pages/Settings";

axios.defaults.withCredentials = true;

function AppRouter() {
  const location = useLocation();
  // Keep the browser tab title as Compass Astro even if platform scripts override it.
  useEffect(() => {
    const setTitle = () => { document.title = "Compass Astro"; };
    setTitle();
    const obs = new MutationObserver(setTitle);
    const t = document.querySelector("title");
    if (t) obs.observe(t, { childList: true });
    return () => obs.disconnect();
  }, []);
  // CRITICAL: detect session_id in fragment synchronously (before route dispatch)
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      {/* Public marketing site */}
      <Route path="/" element={<Home />} />
      <Route path="/astrology" element={<Astrology />} />
      <Route path="/pricing" element={<Pricing />} />
      <Route path="/contact" element={<Contact />} />

      {/* App (protected) */}
      <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute><AppShell><Dashboard /></AppShell></ProtectedRoute>} />
      <Route path="/chat" element={<ProtectedRoute><AppShell><Chat /></AppShell></ProtectedRoute>} />
      <Route path="/library" element={<ProtectedRoute><AppShell><Library /></AppShell></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute><AppShell><Settings /></AppShell></ProtectedRoute>} />
    </Routes>
  );
}

function ThemedToaster() {
  const { theme } = useTheme();
  return <Toaster theme={theme} position="top-right" />;
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <ThemeProvider>
          <AuthProvider>
            <ThemedToaster />
            <AppRouter />
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
