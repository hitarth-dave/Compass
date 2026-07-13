import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import axios from "axios";
import "@/App.css";

import { AuthProvider } from "@/context/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import AppShell from "@/components/AppShell";
import Landing from "@/pages/Landing";
import AuthCallback from "@/pages/AuthCallback";
import Onboarding from "@/pages/Onboarding";
import Dashboard from "@/pages/Dashboard";
import Chat from "@/pages/Chat";
import Library from "@/pages/Library";

axios.defaults.withCredentials = true;

function AppRouter() {
  const location = useLocation();
  // CRITICAL: detect session_id in fragment synchronously (before route dispatch)
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/onboarding" element={<ProtectedRoute><Onboarding /></ProtectedRoute>} />
      <Route path="/dashboard" element={<ProtectedRoute><AppShell><Dashboard /></AppShell></ProtectedRoute>} />
      <Route path="/chat" element={<ProtectedRoute><AppShell><Chat /></AppShell></ProtectedRoute>} />
      <Route path="/library" element={<ProtectedRoute><AppShell><Library /></AppShell></ProtectedRoute>} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <Toaster theme="light" position="top-right" />
      <BrowserRouter>
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
