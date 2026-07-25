import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { X, Loader2 } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Sadhaka and Acharya have no checkout wired yet. Rather than pointing
 * their CTAs at the same sign-in modal as the free tier (which is what
 * they did before — every pricing CTA called the same openAuthModal, so a
 * "paying" user had no way to actually pay and no record was kept of
 * intent), this collects an email + tier and stores it server-side so
 * you have a real list to email when checkout ships.
 */
export default function WaitlistModal({ tier, onClose }) {
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e) {
    e.preventDefault();
    if (!email) return;
    setSending(true);
    try {
      await axios.post(`${API}/waitlist`, { email, tier });
      setDone(true);
      toast.success("You're on the list — we'll email you when checkout opens.");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Could not join the waitlist. Try again?");
    } finally {
      setSending(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-[10000] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="waitlist-modal-title"
      data-testid="waitlist-modal"
    >
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative modal-surface w-full max-w-md p-8">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-gold)]"
          aria-label="Close"
          data-testid="waitlist-modal-close"
        >
          <X size={18} />
        </button>

        {!done ? (
          <>
            <h2 id="waitlist-modal-title" className="font-serif-display text-2xl text-[color:var(--jai-green-deep)] mb-2">
              Join the {tier} waitlist
            </h2>
            <p className="text-sm text-[color:var(--jai-text-muted)] mb-6">
              Checkout for {tier} isn't live yet. Leave your email and you'll be the first to know
              when it opens — Compass Astro is free to use in the meantime.
            </p>
            <form onSubmit={submit} className="space-y-4">
              <label className="block">
                <span className="sr-only">Email</span>
                <input
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full px-4 py-3 rounded-lg bg-transparent border border-[color:var(--jai-border)] text-[color:var(--jai-green-deep)] focus:outline-none focus:border-[color:var(--jai-gold)]"
                  data-testid="waitlist-email-input"
                />
              </label>
              <button
                type="submit"
                disabled={sending}
                className="gold-btn w-full rounded-full px-6 py-3 font-serif-display text-lg inline-flex items-center justify-center gap-2 disabled:opacity-60"
                data-testid="waitlist-submit-btn"
              >
                {sending && <Loader2 size={16} className="animate-spin" />}
                Notify me
              </button>
            </form>
          </>
        ) : (
          <>
            <h2 className="font-serif-display text-2xl text-[color:var(--jai-green-deep)] mb-2">You're on the list</h2>
            <p className="text-sm text-[color:var(--jai-text-muted)]">
              We'll email {email} the moment {tier} checkout opens.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
