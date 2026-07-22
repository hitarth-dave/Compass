import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { X, Loader2, Eye, EyeOff } from "lucide-react";
import { useAuth, setStoredToken } from "@/context/AuthContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID;

// The Google Identity Services script tag (added in index.html) loads async,
// so it may not exist yet the instant this modal first opens. Poll briefly
// rather than assuming it's ready.
function waitForGoogle(timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    (function poll() {
      if (window.google?.accounts?.id) return resolve();
      if (Date.now() - start > timeoutMs) return reject(new Error("Google script did not load"));
      setTimeout(poll, 150);
    })();
  });
}

const emptyForm = { name: "", email: "", password: "", rememberMe: false, code: "" };

export default function AuthModal() {
  const { authModalOpen, authModalMode, closeAuthModal, setUser } = useAuth();
  const [mode, setMode] = useState("signin"); // "signin" | "signup"
  const [step, setStep] = useState("form"); // "form" | "verify"
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const googleBtnRef = useRef(null);
  // Keeps the Google callback pointed at the latest handler without having
  // to re-run the (somewhat expensive) initialize/renderButton effect below
  // on every keystroke in the form.
  const onGoogleCredentialRef = useRef(() => {});

  // Reset to a clean slate every time the modal is (re)opened.
  useEffect(() => {
    if (authModalOpen) {
      setMode(authModalMode || "signin");
      setStep("form");
      setForm(emptyForm);
      setShowPassword(false);
    }
  }, [authModalOpen, authModalMode]);

  async function afterLogin(data) {
    if (data?.session_token) setStoredToken(data.session_token);
    setUser(data);
    closeAuthModal();
    window.location.href = "/dashboard";
  }

  async function handleGoogleCredential(credential) {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/auth/google`, { credential });
      await afterLogin(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Google sign-in failed");
    } finally {
      setLoading(false);
    }
  }
  onGoogleCredentialRef.current = handleGoogleCredential;

  // Render Google's own button widget into googleBtnRef. Only (re)runs when
  // the modal opens or returns to the form step — not on every render.
  useEffect(() => {
    if (!authModalOpen || step !== "form") return;
    let cancelled = false;
    waitForGoogle()
      .then(() => {
        if (cancelled || !googleBtnRef.current) return;
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (resp) => onGoogleCredentialRef.current(resp.credential),
        });
        googleBtnRef.current.innerHTML = ""; // avoid stacking duplicate buttons on re-run
        window.google.accounts.id.renderButton(googleBtnRef.current, {
          theme: "outline", size: "large", shape: "pill", width: 300, text: "continue_with",
        });
      })
      .catch(() => {
        // Google script failed to load in time — email/password still works,
        // so degrade silently rather than blocking the whole modal on it.
      });
    return () => { cancelled = true; };
  }, [authModalOpen, step]);

  async function handleSignup(e) {
    e.preventDefault();
    setLoading(true);
    try {
      await axios.post(`${API}/auth/signup`, { name: form.name, email: form.email, password: form.password });
      setStep("verify");
      toast.success("Check your email for a verification code");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not sign up");
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await axios.post(`${API}/auth/verify`, { email: form.email, code: form.code });
      await afterLogin(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Incorrect code");
    } finally {
      setLoading(false);
    }
  }

  async function handleResendCode() {
    try {
      await axios.post(`${API}/auth/resend-code`, { email: form.email });
      toast.success("New code sent");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Could not resend code");
    }
  }

  async function handleLogin(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await axios.post(`${API}/auth/login`, {
        email: form.email, password: form.password, remember_me: form.rememberMe,
      });
      await afterLogin(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Incorrect email or password");
    } finally {
      setLoading(false);
    }
  }

  if (!authModalOpen) return null;

  return (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center p-4" data-testid="auth-modal">
      <div className="absolute inset-0 bg-black/50" onClick={closeAuthModal} />
      <div className="relative card-surface w-full max-w-md p-8 max-h-[90vh] overflow-y-auto">
        <button
          onClick={closeAuthModal}
          className="absolute top-4 right-4 text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)]"
          data-testid="auth-modal-close"
        >
          <X size={18} />
        </button>

        {step === "form" && (
          <>
            <h2 className="font-serif-display text-2xl text-[color:var(--jai-parchment)] mb-6">
              {mode === "signin" ? "Sign in" : "Create your account"}
            </h2>

            <div ref={googleBtnRef} className="flex justify-center min-h-[44px]" data-testid="google-signin-slot" />
            <button
              disabled
              title="Apple sign-in is coming soon"
              className="w-full mt-3 rounded-full px-6 py-3 font-serif-display inline-flex items-center justify-center gap-3 border border-[color:var(--jai-border)] text-[color:var(--jai-text-muted)] opacity-50 cursor-not-allowed"
              data-testid="apple-signin-btn-disabled"
            >
              Continue with Apple
            </button>

            <div className="flex items-center gap-3 my-6">
              <div className="flex-1 h-px bg-[color:var(--jai-border)]" />
              <span className="text-xs uppercase tracking-widest text-[color:var(--jai-text-muted)]">or</span>
              <div className="flex-1 h-px bg-[color:var(--jai-border)]" />
            </div>

            <form onSubmit={mode === "signin" ? handleLogin : handleSignup} className="space-y-4">
              {mode === "signup" && (
                <input
                  type="text"
                  placeholder="Name"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-4 py-3 rounded-lg bg-transparent border border-[color:var(--jai-border)] text-[color:var(--jai-parchment)] focus:outline-none focus:border-[color:var(--jai-gold)]"
                  data-testid="auth-name-input"
                />
              )}
              <input
                type="email"
                placeholder="Email"
                required
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="w-full px-4 py-3 rounded-lg bg-transparent border border-[color:var(--jai-border)] text-[color:var(--jai-parchment)] focus:outline-none focus:border-[color:var(--jai-gold)]"
                data-testid="auth-email-input"
              />
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  placeholder="Password"
                  required
                  minLength={mode === "signup" ? 8 : undefined}
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className="w-full px-4 py-3 pr-11 rounded-lg bg-transparent border border-[color:var(--jai-border)] text-[color:var(--jai-parchment)] focus:outline-none focus:border-[color:var(--jai-gold)]"
                  data-testid="auth-password-input"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)]"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>

              {mode === "signin" && (
                <label className="flex items-center gap-2 text-sm text-[color:var(--jai-text-muted)]">
                  <input
                    type="checkbox"
                    checked={form.rememberMe}
                    onChange={(e) => setForm({ ...form, rememberMe: e.target.checked })}
                  />
                  Remember me
                </label>
              )}

              <button
                type="submit"
                disabled={loading}
                className="gold-btn w-full rounded-full px-6 py-3 font-serif-display text-lg inline-flex items-center justify-center gap-2 disabled:opacity-60"
                data-testid="auth-submit-btn"
              >
                {loading && <Loader2 size={16} className="animate-spin" />}
                {mode === "signin" ? "Sign in" : "Create account"}
              </button>
            </form>

            <p className="mt-6 text-center text-sm text-[color:var(--jai-text-muted)]">
              {mode === "signin" ? (
                <>
                  New here?{" "}
                  <button className="text-[color:var(--jai-gold)] hover:underline" onClick={() => setMode("signup")}>
                    Create an account
                  </button>
                </>
              ) : (
                <>
                  Already have an account?{" "}
                  <button className="text-[color:var(--jai-gold)] hover:underline" onClick={() => setMode("signin")}>
                    Sign in
                  </button>
                </>
              )}
            </p>
          </>
        )}

        {step === "verify" && (
          <>
            <h2 className="font-serif-display text-2xl text-[color:var(--jai-parchment)] mb-2">Check your email</h2>
            <p className="text-sm text-[color:var(--jai-text-muted)] mb-6">
              We sent a 6-digit code to <span className="text-[color:var(--jai-parchment)]">{form.email}</span>.
              Enter it below to finish creating your account.
            </p>
            <form onSubmit={handleVerify} className="space-y-4">
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                placeholder="6-digit code"
                required
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value.replace(/\D/g, "") })}
                className="w-full px-4 py-3 rounded-lg bg-transparent border border-[color:var(--jai-border)] text-[color:var(--jai-parchment)] text-center tracking-[0.5em] text-xl focus:outline-none focus:border-[color:var(--jai-gold)]"
                data-testid="auth-code-input"
              />
              <button
                type="submit"
                disabled={loading}
                className="gold-btn w-full rounded-full px-6 py-3 font-serif-display text-lg inline-flex items-center justify-center gap-2 disabled:opacity-60"
                data-testid="auth-verify-btn"
              >
                {loading && <Loader2 size={16} className="animate-spin" />}
                Verify &amp; create account
              </button>
            </form>
            <p className="mt-4 text-center text-sm">
              <button onClick={handleResendCode} className="text-[color:var(--jai-gold)] hover:underline" data-testid="auth-resend-code-btn">
                Resend code
              </button>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
