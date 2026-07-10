import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";

import Onboarding from "@/pages/Onboarding";
import Dashboard from "@/pages/Dashboard";
import Chat from "@/pages/Chat";
import Library from "@/pages/Library";
import AppShell from "@/components/AppShell";

function ProtectedShell({ children }) {
  const profileId = localStorage.getItem("jyotish_profile_id");
  if (!profileId) return <Navigate to="/onboarding" replace />;
  return <AppShell>{children}</AppShell>;
}

function Root() {
  const profileId = localStorage.getItem("jyotish_profile_id");
  return <Navigate to={profileId ? "/dashboard" : "/onboarding"} replace />;
}

function App() {
  return (
    <div className="App">
      <Toaster theme="dark" position="top-right" />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Root />} />
          <Route path="/onboarding" element={<Onboarding />} />
          <Route path="/dashboard" element={<ProtectedShell><Dashboard /></ProtectedShell>} />
          <Route path="/chat" element={<ProtectedShell><Chat /></ProtectedShell>} />
          <Route path="/library" element={<ProtectedShell><Library /></ProtectedShell>} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
