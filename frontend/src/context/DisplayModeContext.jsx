import { createContext, useContext, useEffect, useState } from "react";

// Two audiences share this app: everyday users who want plain-language
// answers, and astrologers who want the full technical chart data to work
// from. This context is the single on/off switch between those two views —
// same pattern as ThemeContext (persisted, applied globally via context so
// Dashboard, Chat, and any future page all read from one source of truth).
const MODE_KEY = "compass_display_mode";

function getInitialMode() {
  const stored = localStorage.getItem(MODE_KEY);
  return stored === "advanced" ? "advanced" : "simple";
}

const DisplayModeContext = createContext(null);

export function DisplayModeProvider({ children }) {
  const [mode, setMode] = useState(getInitialMode);

  useEffect(() => {
    localStorage.setItem(MODE_KEY, mode);
  }, [mode]);

  const toggleMode = () => setMode((m) => (m === "advanced" ? "simple" : "advanced"));

  return (
    <DisplayModeContext.Provider value={{ mode, setMode, toggleMode, isAdvanced: mode === "advanced" }}>
      {children}
    </DisplayModeContext.Provider>
  );
}

export const useDisplayMode = () => useContext(DisplayModeContext);
