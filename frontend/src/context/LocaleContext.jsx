import { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";
import axios from "axios";
import en from "@/translations/en.json";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LOCALE_KEY = "compass_locale";
const RTL_LANGS = new Set(["ur"]); // Urdu is the only Tier 1/2/3 RTL language

// Loaded lazily (see setLocale below) via dynamic import so the initial
// bundle only ships English; every other translation file is fetched only
// when someone actually picks that language. en.json is bundled eagerly
// since it's both the default and the fallback for any missing key.
const LOADERS = {
  hi: () => import("@/translations/hi.json"),
  gu: () => import("@/translations/gu.json"),
  mr: () => import("@/translations/mr.json"),
  ta: () => import("@/translations/ta.json"),
  te: () => import("@/translations/te.json"),
  kn: () => import("@/translations/kn.json"),
  bn: () => import("@/translations/bn.json"),
  pa: () => import("@/translations/pa.json"),
  ur: () => import("@/translations/ur.json"),
  ne: () => import("@/translations/ne.json"),
  si: () => import("@/translations/si.json"),
  es: () => import("@/translations/es.json"),
  pt: () => import("@/translations/pt.json"),
  fr: () => import("@/translations/fr.json"),
  id: () => import("@/translations/id.json"),
};

function getInitialLocale() {
  const stored = localStorage.getItem(LOCALE_KEY);
  return stored && (stored === "en" || LOADERS[stored]) ? stored : "en";
}

function applyDocumentAttrs(code) {
  document.documentElement.lang = code;
  document.documentElement.dir = RTL_LANGS.has(code) ? "rtl" : "ltr";
}

function lookup(dict, key) {
  return key.split(".").reduce((acc, part) => (acc && typeof acc === "object" ? acc[part] : undefined), dict);
}

const LocaleContext = createContext(null);

export function LocaleProvider({ children, user }) {
  const [locale, setLocaleState] = useState(getInitialLocale);
  const [dict, setDict] = useState(en);
  const appliedFromUser = useRef(false);

  // Apply <html lang>/dir on mount and whenever locale changes.
  useEffect(() => {
    applyDocumentAttrs(locale);
  }, [locale]);

  const loadLocale = useCallback(async (code) => {
    if (code === "en") {
      setDict(en);
      return;
    }
    const loader = LOADERS[code];
    if (!loader) {
      setDict(en); // unknown code — fail safe to English rather than a blank UI
      return;
    }
    try {
      const mod = await loader();
      setDict(mod.default || mod);
    } catch {
      setDict(en); // a failed chunk load shouldn't leave the UI half-translated
    }
  }, []);

  // Once the account loads, it's the source of truth (works across devices).
  // Runs only once per sign-in, not on every user object change, so a
  // manual switch later in the session doesn't get silently reverted.
  useEffect(() => {
    if (user?.language && !appliedFromUser.current) {
      appliedFromUser.current = true;
      if (user.language !== locale) {
        setLocaleState(user.language);
        localStorage.setItem(LOCALE_KEY, user.language);
        loadLocale(user.language);
      }
    }
  }, [user, locale, loadLocale]);

  // Load whichever locale we started with (from localStorage) immediately,
  // without waiting for auth — a returning visitor shouldn't see a flash of
  // English before their saved preference kicks in.
  useEffect(() => {
    loadLocale(locale);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setLocale = useCallback(async (code) => {
    setLocaleState(code);
    localStorage.setItem(LOCALE_KEY, code);
    await loadLocale(code);
    if (user) {
      try {
        await axios.patch(`${API}/account`, { language: code });
      } catch {
        // Not fatal — the choice still applies locally via localStorage,
        // it just won't follow the person to another device this time.
      }
    }
  }, [user, loadLocale]);

  const t = useCallback((key) => {
    const value = lookup(dict, key);
    if (value !== undefined) return value;
    const fallback = lookup(en, key);
    return fallback !== undefined ? fallback : key;
  }, [dict]);

  return (
    <LocaleContext.Provider value={{ locale, setLocale, t, isRtl: RTL_LANGS.has(locale) }}>
      {children}
    </LocaleContext.Provider>
  );
}

export const useLocale = () => useContext(LocaleContext);
