import { useEffect, useRef, useState, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import axios from "axios";
import { getStoredToken } from "@/context/AuthContext";
import { useDisplayMode } from "@/context/DisplayModeContext";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Send,
  Loader2,
  Sparkles,
  ScrollText,
  ChevronDown,
  ChevronUp,
  Mic,
  MicOff,
  Paperclip,
  X,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import WhyPanel, { splitAnswerLogic, groupCitationsByBook } from "@/components/WhyPanel";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SUGGESTIONS = [
  "How's my career going right now?",
  "Any advice on my love life?",
  "What should I focus on this year?",
  "Is a big change coming for me?",
];

export default function Chat() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAdvanced } = useDisplayMode();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [logicOpen, setLogicOpen] = useState(false);
  const [activeLogic, setActiveLogic] = useState({ logic: "", citations: [] });
  const [attachments, setAttachments] = useState([]); // {url, filename, preview}
  const [uploading, setUploading] = useState(false);
  const [listening, setListening] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [threadMeta, setThreadMeta] = useState(null); // { name, project_key, project_label }
  const endRef = useRef(null);
  const scrollContainerRef = useRef(null);
  const userScrolledUpRef = useRef(false);
  const fileRef = useRef(null);
  const recognitionRef = useRef(null);

  const profileId = null; // profile now server-side per authenticated user

  // Resolve / create the active thread from URL ?t= or fallback
  const urlThread = new URLSearchParams(location.search).get("t");

  useEffect(() => {
    (async () => {
      if (urlThread) {
        setSessionId(urlThread);
      } else {
        // Load threads; if none, create a default; otherwise pick the most recent
        try {
          const res = await axios.get(`${API}/threads`);
          const list = res.data.threads || [];
          if (list.length === 0) {
            const created = await axios.post(`${API}/threads`, { name: "General" });
            navigate(`/chat?t=${created.data.id}`, { replace: true });
          } else {
            navigate(`/chat?t=${list[0].id}`, { replace: true });
          }
        } catch (e) {
          toast.error("Could not load your conversations");
        }
      }
    })();
  }, [urlThread, navigate]);

  // Load thread history when sessionId changes
  useEffect(() => {
    if (!sessionId) return;
    setMessages([]);
    const token = getStoredToken();
    fetch(`${API}/chat/${sessionId}/history`, {
      credentials: "include",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.json())
      .then((d) => setMessages(d.messages || []))
      .catch(() => {});
  }, [sessionId]);

  // Project badge — which life-area (if any) this thread is scoped to.
  const [projectLabels, setProjectLabels] = useState({});
  useEffect(() => {
    axios.get(`${API}/projects`).then((res) => {
      const map = {};
      (res.data.projects || []).forEach((p) => { map[p.key] = p.label; });
      setProjectLabels(map);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!sessionId) { setThreadMeta(null); return; }
    axios.get(`${API}/threads/${sessionId}`).then((res) => setThreadMeta(res.data)).catch(() => setThreadMeta(null));
  }, [sessionId]);

  // Previously this ran scrollIntoView on every streamed chunk unconditionally,
  // which meant scrolling up during an answer was immediately overridden —
  // the page only "let go" once streaming finished. Now it only auto-scrolls
  // if the user hasn't deliberately scrolled away from the bottom, matching
  // how most chat UIs (including this one's own inspiration) behave.
  useEffect(() => {
    if (userScrolledUpRef.current) return;
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  const handleMessagesScroll = () => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    userScrolledUpRef.current = distanceFromBottom > 120; // small threshold so landing near the bottom still counts as "at bottom"
  };

  // ---- Voice input (Web Speech API) ----
  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      toast.error("Voice input not supported in this browser (try Chrome).");
      return;
    }
    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = "en-IN";
    let finalText = "";
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += t;
        else interim += t;
      }
      setInput((prev) => (finalText || interim).trim());
    };
    rec.onerror = (e) => {
      toast.error(`Voice error: ${e.error}`);
      setListening(false);
    };
    rec.onend = () => setListening(false);
    recognitionRef.current = rec;
    rec.start();
    setListening(true);
  };

  const stopListening = () => {
    recognitionRef.current?.stop();
    setListening(false);
  };

  // ---- Attachments ----
  const onAttach = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    for (const f of files) {
      try {
        const fd = new FormData();
        fd.append("file", f);
        const res = await axios.post(`${API}/chat/attachment`, fd, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        setAttachments((a) => [...a, { ...res.data, preview: URL.createObjectURL(f) }]);
      } catch (err) {
        toast.error(err.response?.data?.detail || "Upload failed");
      }
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const removeAttachment = (idx) => setAttachments((a) => a.filter((_, i) => i !== idx));

  // ---- Send ----
  const send = useCallback(async (text) => {
    const question = (text ?? input).trim();
    if ((!question && attachments.length === 0) || streaming || !sessionId) return;

    userScrolledUpRef.current = false;
    setInput("");
    const attach = attachments.slice();
    setAttachments([]);

    setMessages((m) => [...m, { role: "user", content: question, attachments: attach.map((a) => a.url) }]);
    setStreaming(true);
    setMessages((m) => [...m, { role: "assistant", content: "", citations: [] }]);

    try {
      const token = getStoredToken();
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: question || "Please analyze the attached image.",
          attachment_urls: attach.map((a) => a.url),
        }),
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
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
          } else if (evtName === "done") {
            // Server signaled completion — bail immediately even if reader
            // hasn't seen {done:true} (some proxies keep the SSE conn open).
            setStreaming(false);
            return;
          } else if (evtName === "error") {
            toast.error(`Claude API: ${data.error}`);
            setMessages((m) => {
              const c = [...m];
              const last = c[c.length - 1];
              if (last?.role === "assistant" && !last.content) {
                c[c.length - 1] = { ...last, content: `_(Error: ${data.error})_` };
              }
              return c;
            });
          }
        }
      }
    } catch (e) {
      const err = e?.message || String(e);
      toast.error(`Conversation error: ${err}`);
      setMessages((m) => {
        const c = [...m];
        const last = c[c.length - 1];
        if (last?.role === "assistant" && !last.content) {
          c[c.length - 1] = { ...last, content: `_(Network / stream error: ${err})_` };
        }
        return c;
      });
    } finally {
      setStreaming(false);
    }
  }, [input, attachments, streaming, sessionId]);

  const openLogic = (m) => {
    // Basic mode gets the Why button too, but tapping it doesn't reveal
    // the real reasoning — that stays an Advanced/Astrologer-mode feature.
    if (!isAdvanced) {
      setActiveLogic({ logic: "", citations: [], locked: true });
      setLogicOpen(true);
      return;
    }
    const parsed = splitAnswerLogic(m.content || "");
    setActiveLogic({
      logic: m.logic || parsed.logic,
      citations: m.citations || [],
      locked: false,
    });
    setLogicOpen(true);
  };

  const hasMessages = messages.length > 0;

  return (
    <div className="flex flex-col h-screen max-w-5xl mx-auto px-6 lg:px-12" data-testid="chat-page">
      <div className="py-8 border-b border-[color:var(--jai-border)]">
        <div className="overline flex items-center gap-2">
          Conversation with the Shastras
          {threadMeta?.project_key && projectLabels[threadMeta.project_key] && (
            <span
              className="normal-case tracking-normal text-xs px-2 py-0.5 rounded-full border border-[color:var(--jai-border-gold)] text-[color:var(--jai-gold)]"
              data-testid="chat-project-badge"
            >
              {projectLabels[threadMeta.project_key]}
            </span>
          )}
        </div>
        <h1 className="font-serif-display text-3xl sm:text-4xl mt-2 text-[color:var(--jai-parchment)]">
          Ask, and the classics answer.
        </h1>
      </div>

      <div
        ref={scrollContainerRef}
        onScroll={handleMessagesScroll}
        className="flex-1 overflow-y-auto py-8 space-y-8"
        data-testid="chat-messages"
      >
        {!hasMessages && (
          <div className="mt-8 space-y-8 fade-up">
            <p className="text-[color:var(--jai-text-muted)] max-w-xl">
              Ask anything — career, love, timing, life direction. Answers come in plain language.
              {" "}Curious about the reasoning? Tap <span className="text-[color:var(--jai-gold)]">Why?</span> on any reply.
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
          <MessageBubble key={i} msg={m} idx={i} onWhy={openLogic} advanced={isAdvanced} />
        ))}
        {streaming && (
          <div className="text-[color:var(--jai-text-muted)] text-sm flex items-center gap-2">
            <Loader2 size={14} className="animate-spin" /> reading the stars…
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Attachment previews above input */}
      {attachments.length > 0 && (
        <div className="flex gap-2 mb-2 flex-wrap" data-testid="attachment-preview-list">
          {attachments.map((a, i) => (
            <div key={i} className="relative">
              <img src={a.preview} alt={a.filename} className="h-16 w-16 object-cover rounded-md border border-[color:var(--jai-border)]" />
              <button
                onClick={() => removeAttachment(i)}
                className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-[color:var(--jai-green)] text-[color:var(--jai-surface)] flex items-center justify-center"
                data-testid={`remove-attachment-${i}`}
              >
                <X size={11} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="py-4 border-t border-[color:var(--jai-border)]">
        <div className="flex items-end gap-2">
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" multiple className="hidden" onChange={onAttach} data-testid="attachment-input" />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-12 w-12 text-[color:var(--jai-text-muted)] hover:text-[color:var(--jai-green-deep)]"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            title="Attach image"
            data-testid="attach-btn"
          >
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Paperclip size={17} />}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={`h-12 w-12 ${listening ? "text-red-600" : "text-[color:var(--jai-text-muted)]"} hover:text-[color:var(--jai-green-deep)]`}
            onClick={listening ? stopListening : startListening}
            title={listening ? "Stop recording" : "Speak your question"}
            data-testid="mic-btn"
          >
            {listening ? <MicOff size={17} /> : <Mic size={17} />}
          </Button>
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
            }}
            placeholder="What would you like to know?"
            disabled={streaming}
            rows={2}
            className="flex-1 bg-[color:var(--jai-surface)] border-[color:var(--jai-border)] resize-none text-base font-serif-display text-[color:var(--jai-parchment)] placeholder:text-[color:var(--jai-text-muted)]/60 focus-visible:ring-1 focus-visible:ring-[color:var(--jai-gold)]/50"
            data-testid="chat-input"
          />
          <Button onClick={() => send()} disabled={streaming || (!input.trim() && attachments.length === 0)} className="gold-btn h-12 px-6" data-testid="chat-send-btn">
            {streaming ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </Button>
        </div>
        <p className="mt-2 text-center text-[10px] text-[color:var(--jai-text-muted)]/80" data-testid="chat-disclaimer">
          Compass Astro offers astrological perspective, not medical, legal, or financial advice — for those decisions, please consult a qualified professional.
        </p>
      </div>

      <WhyPanel
        open={logicOpen}
        onOpenChange={setLogicOpen}
        logic={activeLogic.logic}
        citations={activeLogic.citations}
        locked={activeLogic.locked}
      />
    </div>
  );
}

function MessageBubble({ msg, idx, onWhy, advanced }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] space-y-2">
          {msg.attachments?.map((u, i) => (
            <img key={i} src={`${process.env.REACT_APP_BACKEND_URL}${u}`} alt="attachment" className="max-h-40 rounded-lg border border-[color:var(--jai-border)]" />
          ))}
          {msg.content && (
            <div className="rounded-2xl px-5 py-3 bg-[color:var(--jai-green)] text-[color:var(--jai-surface)] shadow-sm" data-testid="user-message" data-ph-mask>
              {msg.content}
            </div>
          )}
        </div>
      </div>
    );
  }

  const parsed = splitAnswerLogic(msg.content || "");
  const answer = msg.answer ?? parsed.answer;
  const hasLogic = !!(msg.logic || parsed.logic);

  return (
    <div className="flex gap-4" data-testid="assistant-message">
      <div className="w-9 h-9 rounded-full border border-[color:var(--jai-gold)] flex items-center justify-center shrink-0">
        <Sparkles size={14} className="text-[color:var(--jai-gold)]" />
      </div>
      <div className="max-w-[85%] flex-1">
        <div className="card-surface px-6 py-5 border-l-2 border-l-[color:var(--jai-gold)]">
          <div className="md-body text-[color:var(--jai-parchment)] leading-relaxed" data-testid={`assistant-answer-${idx}`} data-ph-mask>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {answer || (msg.content ? "…" : "")}
            </ReactMarkdown>
          </div>
        </div>
        {(hasLogic || (msg.citations?.length ?? 0) > 0) && (
          <div className="mt-3 flex items-center gap-2 flex-wrap">
            <button
              onClick={() => onWhy(msg)}
              className="inline-flex items-center gap-1.5 text-xs px-3 py-1 rounded-full border border-[color:var(--jai-gold)] text-[color:var(--jai-gold)] hover:bg-[color:var(--jai-gold)] hover:text-[color:var(--jai-surface)] transition-colors"
              data-testid={`why-btn-${idx}`}
            >
              <Info size={11} /> Why?
            </button>
            {advanced && groupCitationsByBook(msg.citations).slice(0, 3).map((grouped) => (
              <TooltipProvider key={grouped.book} delayDuration={100}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border border-[color:var(--jai-border)] bg-[color:var(--jai-surface)] text-[color:var(--jai-green-deep)] cursor-help" data-testid={`citation-${grouped.idx}`}>
                      <ScrollText size={11} className="text-[color:var(--jai-gold)]" />
                      {grouped.book}
                    </span>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-md bg-[color:var(--jai-surface)] border-[color:var(--jai-border)] text-[color:var(--jai-parchment)] space-y-2">
                    {grouped.excerpts.map((e) => (
                      <div key={e.idx}>
                        <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-gold)] mb-1">{e.chapter}</div>
                        <div className="italic font-serif-display text-sm leading-relaxed">{e.text}</div>
                      </div>
                    ))}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
