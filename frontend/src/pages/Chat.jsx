import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Send, Loader2, Sparkles, ScrollText, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SUGGESTIONS = [
  "What does my current Mahadasha say about my career?",
  "Guidance on relationships from my chart",
  "Which planetary transits should I be aware of this month?",
  "What are the strongest yogas in my Kundali?",
];

export default function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sessionId] = useState(() => {
    const existing = localStorage.getItem("jyotish_session_id");
    if (existing) return existing;
    const sid = crypto.randomUUID();
    localStorage.setItem("jyotish_session_id", sid);
    return sid;
  });
  const endRef = useRef(null);

  useEffect(() => {
    // Load history
    fetch(`${API}/chat/${sessionId}/history`)
      .then((r) => r.json())
      .then((d) => setMessages(d.messages || []))
      .catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  const send = async (text) => {
    const question = (text ?? input).trim();
    if (!question || streaming) return;
    setInput("");
    const profileId = localStorage.getItem("jyotish_profile_id");
    setMessages((m) => [...m, { role: "user", content: question }]);
    setStreaming(true);

    // Append assistant placeholder
    setMessages((m) => [...m, { role: "assistant", content: "", citations: [] }]);

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile_id: profileId, session_id: sessionId, message: question }),
      });
      if (!res.body) throw new Error("no stream");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const events = buf.split("\n\n");
        buf = events.pop() || "";
        for (const ev of events) {
          const lines = ev.split("\n");
          const evtLine = lines.find((l) => l.startsWith("event:"));
          const dataLine = lines.find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          const evtName = evtLine?.slice(6).trim();
          const data = JSON.parse(dataLine.slice(5).trim());
          if (evtName === "citations") {
            setMessages((m) => {
              const c = [...m];
              c[c.length - 1] = { ...c[c.length - 1], citations: data };
              return c;
            });
          } else if (evtName === "delta") {
            setMessages((m) => {
              const c = [...m];
              c[c.length - 1] = { ...c[c.length - 1], content: c[c.length - 1].content + data.text };
              return c;
            });
          } else if (evtName === "error") {
            toast.error(data.error || "Stream error");
          }
        }
      }
    } catch (e) {
      toast.error("Conversation failed");
    } finally {
      setStreaming(false);
    }
  };

  const hasMessages = messages.length > 0;

  return (
    <div className="flex flex-col h-screen max-w-5xl mx-auto px-6 lg:px-12" data-testid="chat-page">
      <div className="py-8 border-b border-[color:var(--jai-border)]">
        <div className="overline">Conversation with the Shastras</div>
        <h1 className="font-serif-display text-3xl sm:text-4xl mt-2 text-[color:var(--jai-parchment)]">
          Ask, and the classics answer.
        </h1>
      </div>

      <div className="flex-1 overflow-y-auto py-8 space-y-8" data-testid="chat-messages">
        {!hasMessages && (
          <div className="mt-12 space-y-8 fade-up">
            <p className="text-[color:var(--jai-text-muted)] max-w-xl">
              Every reply is grounded in classical Sanatan Shastras — Brihat Parashara Hora Shastra, Phaladeepika,
              Saravali, Jaimini Sutras and more — cross-referenced with your Kundali and today's live transits.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left card-surface p-4 hover:border-[color:var(--jai-gold)] transition-colors"
                  data-testid={`suggestion-${s.slice(0, 12).replace(/\s/g, '-')}`}
                >
                  <Sparkles size={14} className="text-[color:var(--jai-gold)] mb-2" />
                  <div className="font-serif-display text-lg text-[color:var(--jai-parchment)] leading-snug">{s}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <MessageBubble key={i} msg={m} idx={i} />
        ))}
        {streaming && <div className="text-[color:var(--jai-text-muted)] text-sm flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> reading the stars…</div>}
        <div ref={endRef} />
      </div>

      <div className="py-6 border-t border-[color:var(--jai-border)]">
        <div className="flex items-end gap-3">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
            }}
            placeholder="What would you like to know?"
            disabled={streaming}
            rows={2}
            className="flex-1 bg-[color:var(--jai-surface)]/50 border-[color:var(--jai-border)] resize-none text-base font-serif-display text-[color:var(--jai-parchment)] placeholder:text-[color:var(--jai-text-muted)]/60 focus-visible:ring-1 focus-visible:ring-[color:var(--jai-gold)]/50"
            data-testid="chat-input"
          />
          <Button
            onClick={() => send()}
            disabled={streaming || !input.trim()}
            className="gold-btn h-14 px-6"
            data-testid="chat-send-btn"
          >
            {streaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </Button>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ msg }) {
  const [showPassages, setShowPassages] = useState(false);
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl px-5 py-3 bg-[color:var(--jai-green)] text-[color:var(--jai-surface)] shadow-sm" data-testid="user-message">
          {msg.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex gap-4" data-testid="assistant-message">
      <div className="w-9 h-9 rounded-full border border-[color:var(--jai-gold)] flex items-center justify-center shrink-0">
        <Sparkles size={14} className="text-[color:var(--jai-gold)]" />
      </div>
      <div className="max-w-[85%] flex-1">
        <div className="card-surface px-6 py-5 border-l-2 border-l-[color:var(--jai-gold)]">
          <FormattedText text={msg.content} citations={msg.citations || []} />
        </div>
        {msg.citations && msg.citations.length > 0 && (
          <>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {msg.citations.map((c) => (
                <TooltipProvider key={c.idx} delayDuration={100}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="inline-flex items-center gap-1.5 text-xs px-3 py-1 rounded-full border border-[color:var(--jai-border)] bg-[color:var(--jai-surface)] text-[color:var(--jai-green-deep)] cursor-help" data-testid={`citation-${c.idx}`}>
                        <ScrollText size={11} className="text-[color:var(--jai-gold)]" />
                        [{c.idx}] {c.book}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-md bg-[color:var(--jai-surface)] border-[color:var(--jai-border)] text-[color:var(--jai-parchment)]">
                      <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-gold)] mb-1">{c.chapter}</div>
                      <div className="italic font-serif-display text-sm leading-relaxed">{c.text}</div>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              ))}
              <button
                onClick={() => setShowPassages((v) => !v)}
                className="inline-flex items-center gap-1 text-xs text-[color:var(--jai-gold)] hover:text-[color:var(--jai-green-deep)] transition-colors ml-1"
                data-testid={`toggle-passages-${idx}`}
              >
                {showPassages ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                {showPassages ? "Hide retrieved passages" : "Show retrieved passages"}
              </button>
            </div>
            {showPassages && (
              <div className="mt-4 space-y-3 parchment-tint rounded-lg p-5 border border-[color:var(--jai-border)]" data-testid="retrieved-passages">
                {msg.citations.map((c) => (
                  <div key={c.idx} className="border-l-2 border-[color:var(--jai-gold)]/60 pl-4">
                    <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-gold)]">[{c.idx}] {c.book} · {c.chapter}</div>
                    <div className="mt-1 italic font-serif-display text-sm leading-relaxed text-[color:var(--jai-parchment)]">"{c.text}"</div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function FormattedText({ text }) {
  // Highlight [N] citations and paragraph breaks
  const parts = text.split(/(\[\d+\])/g);
  return (
    <div className="whitespace-pre-wrap leading-relaxed text-[color:var(--jai-parchment)]">
      {parts.map((p, i) =>
        /^\[\d+\]$/.test(p) ? (
          <sup key={i} className="text-[color:var(--jai-gold)] font-semibold mx-0.5">{p}</sup>
        ) : (
          <span key={i}>{p}</span>
        )
      )}
    </div>
  );
}
