import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import { Suspense, lazy } from "react";
import axios from "axios";
import { Loader2 } from "lucide-react";
import "@/App.css";

import { AuthProvider, useAuth } from "@/context/AuthContext";
import { ThemeProvider, useTheme } from "@/context/ThemeContext";
import { DisplayModeProvider } from "@/context/DisplayModeContext";
import { LocaleProvider } from "@/context/LocaleContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import ErrorBoundary from "@/components/ErrorBoundary";
import AppShell from "@/components/AppShell";

// Public marketing pages load eagerly — they're small and are the pages
// that actually need to convert a first-time visitor, so there's no
// benefit to lazy-loading them.
import Home from "@/pages/Home";
import Astrology from "@/pages/Astrology";
import Pricing from "@/pages/Pricing";
import Contact from "@/pages/Contact";
import Privacy from "@/pages/Privacy";
import Terms from "@/pages/Terms";
import NotFound from "@/pages/NotFound";

// Signed-in routes are the heaviest part of the bundle (chart renderer,
// chat UI, markdown pipeline, date library) and a visitor who lands on the
// homepage and bounces was downloading all of it anyway. Route-level
// React.lazy means that code only loads once someone actually signs in.
const Onboarding = lazy(() => import("@/pages/Onboarding"));
const Dashboard = lazy(() => import("@/pages/Dashboard"));
const Muhurta = lazy(() => import("@/pages/Muhurta"));
const Chat = lazy(() => import("@/pages/Chat"));
const Library = lazy(() => import("@/pages/Library"));
const Settings = lazy(() => import("@/pages/Settings"));

axios.defaults.withCredentials = true;

function RouteFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <Loader2 className="animate-spin text-[color:var(--jai-gold)]" size={28} />
    </div>
  );
}

function AppRouter() {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Routes>
        {/* Public marketing site */}
        <Route path="/" element={<Home />} />
        <Route path="/astrology" element={<Astrology />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />

        {/* App (protected) */}
        <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
        <Route path="/dashboard" element={<ProtectedRoute><AppShell><Dashboard /></AppShell></ProtectedRoute>} />
        <Route path="/muhurta" element={<ProtectedRoute><AppShell><Muhurta /></AppShell></ProtectedRoute>} />
        <Route path="/chat" element={<ProtectedRoute><AppShell><Chat /></AppShell></ProtectedRoute>} />
        <Route path="/library" element={<ProtectedRoute><AppShell><Library /></AppShell></ProtectedRoute>} />
        <Route path="/settings" element={<ProtectedRoute><AppShell><Settings /></AppShell></ProtectedRoute>} />

        {/* Previously there was no catch-all at all — an unknown URL
            rendered a totally blank page (and Vercel served it with HTTP
            200, so search engines saw soft-404s everywhere). */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}

function ThemedToaster() {
  const { theme } = useTheme();
  return <Toaster theme={theme} position="top-right" />;
}

// LocaleProvider needs the signed-in user's saved `language` field to sync
// across devices, but it's a plain component (no dependency on AuthContext
// internals) so it can't call useAuth itself while ALSO being the thing
// AuthProvider wraps. This one-line bridge is simpler than making
// LocaleProvider aware of AuthContext directly.
function LocaleProviderBridge({ children }) {
  const { user } = useAuth();
  return <LocaleProvider user={user}>{children}</LocaleProvider>;
}

function App() {
  return (
    <div className="App">
      <ErrorBoundary>
        <BrowserRouter>
          <ThemeProvider>
            <AuthProvider>
              <LocaleProviderBridge>
                <DisplayModeProvider>
                  <ThemedToaster />
                  <AppRouter />
                </DisplayModeProvider>
              </LocaleProviderBridge>
            </AuthProvider>
          </ThemeProvider>
        </BrowserRouter>
      </ErrorBoundary>
    </div>
  );
}

export default App;
