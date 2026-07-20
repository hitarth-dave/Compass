import { useState } from "react";
import { Mail, MessageSquare, Send } from "lucide-react";
import { toast } from "sonner";
import PublicLayout from "@/components/PublicLayout";

export default function Contact() {
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [sending, setSending] = useState(false);

  const update = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name || !form.email || !form.message) {
      toast.error("Please fill in every field.");
      return;
    }
    setSending(true);
    // NOTE: no contact endpoint exists yet on the backend. This opens the
    // user's mail client as a dependable fallback. Wire to POST /api/contact
    // later if you add one.
    const subject = encodeURIComponent(`Compass Astro — message from ${form.name}`);
    const body = encodeURIComponent(`${form.message}\n\n— ${form.name} (${form.email})`);
    window.location.href = `mailto:hello@compass-astro.app?subject=${subject}&body=${body}`;
    setTimeout(() => {
      setSending(false);
      toast.success("Opening your mail app…");
    }, 400);
  };

  return (
    <PublicLayout>
      <section className="max-w-5xl mx-auto px-6 lg:px-12 pt-6 grid lg:grid-cols-2 gap-14 items-start">
        <div className="fade-up">
          <div className="overline mb-6">Contact</div>
          <h1 className="font-serif-display text-5xl sm:text-6xl leading-[0.98] text-[color:var(--jai-parchment)]">
            Questions, feedback, or <em className="text-[color:var(--jai-gold)]">a chart that puzzles you?</em>
          </h1>
          <p className="mt-8 text-lg text-[color:var(--jai-text-muted)] leading-relaxed">
            We read everything. Whether it's a bug, a billing question, or a point of Jyotish you'd
            like to discuss, send a note and we'll get back to you.
          </p>

          <div className="mt-10 space-y-4">
            <div className="flex items-center gap-3 text-[color:var(--jai-green-deep)]">
              <Mail size={18} className="text-[color:var(--jai-gold)]" />
              <span className="text-sm">hello@compass-astro.app</span>
            </div>
            <div className="flex items-center gap-3 text-[color:var(--jai-green-deep)]">
              <MessageSquare size={18} className="text-[color:var(--jai-gold)]" />
              <span className="text-sm">Replies usually within a day or two.</span>
            </div>
          </div>
        </div>

        <form onSubmit={submit} className="card-surface p-8 fade-up delay-1" data-testid="contact-form">
          <label className="block mb-5">
            <span className="text-sm text-[color:var(--jai-green-deep)]">Your name</span>
            <input
              value={form.name} onChange={update("name")}
              className="mt-2 w-full rounded-lg border border-[color:var(--jai-border)] bg-[color:var(--jai-surface)] px-4 py-3 text-[color:var(--jai-green-deep)] outline-none focus:border-[color:var(--jai-gold)]"
              placeholder="Arjun Sharma" data-testid="contact-name"
            />
          </label>
          <label className="block mb-5">
            <span className="text-sm text-[color:var(--jai-green-deep)]">Email</span>
            <input
              type="email" value={form.email} onChange={update("email")}
              className="mt-2 w-full rounded-lg border border-[color:var(--jai-border)] bg-[color:var(--jai-surface)] px-4 py-3 text-[color:var(--jai-green-deep)] outline-none focus:border-[color:var(--jai-gold)]"
              placeholder="you@example.com" data-testid="contact-email"
            />
          </label>
          <label className="block mb-6">
            <span className="text-sm text-[color:var(--jai-green-deep)]">Message</span>
            <textarea
              value={form.message} onChange={update("message")} rows={5}
              className="mt-2 w-full rounded-lg border border-[color:var(--jai-border)] bg-[color:var(--jai-surface)] px-4 py-3 text-[color:var(--jai-green-deep)] outline-none focus:border-[color:var(--jai-gold)] resize-none"
              placeholder="What's on your mind?" data-testid="contact-message"
            />
          </label>
          <button
            type="submit" disabled={sending}
            className="w-full rounded-full px-6 py-3.5 font-serif-display text-lg bg-[color:var(--jai-green)] text-[color:var(--jai-surface)] hover:bg-[color:var(--jai-green-deep)] transition-colors inline-flex items-center justify-center gap-2 disabled:opacity-60"
            data-testid="contact-submit"
          >
            <Send size={16} /> {sending ? "Sending…" : "Send message"}
          </button>
        </form>
      </section>
    </PublicLayout>
  );
}
