import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Info } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

/** Groups citations by book name so the same book never appears twice as a
 * separate pill/heading — each book appears once, with all its excerpts
 * (from possibly-different chapters) nested underneath. */
const MAX_CITATIONS = 5; // still bounded — a 1000-1300 word budget shouldn't mean unlimited full-page citations either
const EXCERPT_WORD_CAP = 80; // a substantial supporting quote, not a page reproduction

function cleanExcerptText(text) {
  if (!text) return "";
  // Retrieved passages sometimes carry OCR scan artifacts like
  // "---------------- page 33 of 482 -----------------" baked into the
  // text itself — strip those before showing anything to the user.
  const cleaned = text.replace(/-{5,}\s*page\s+\d+\s+of\s+\d+\s*-{5,}/gi, " ").replace(/\s+/g, " ").trim();
  return capWords(cleaned, EXCERPT_WORD_CAP);
}

export function groupCitationsByBook(citations) {
  const byBook = new Map();
  for (const c of (citations || []).slice(0, MAX_CITATIONS)) {
    if (!byBook.has(c.book)) {
      byBook.set(c.book, { book: c.book, idx: c.idx, excerpts: [] });
    }
    byBook.get(c.book).excerpts.push({ idx: c.idx, chapter: c.chapter, text: cleanExcerptText(c.text) });
  }
  return Array.from(byBook.values());
}

/**
 * Parses a model reply that embeds its reasoning in <LOGIC>...</LOGIC>.
 * Also guards against a stream that's cut off mid-tag (a partial opening
 * tag fragment, e.g. "<LOG", left dangling at the end of what's rendered
 * so far) leaking raw markup into the visible answer.
 */
const LOGIC_WORD_CAP = 1400; // safety ceiling, not a target — system prompt asks for
// 1000-1300 words; this only kicks in if the model runs well past that.
function capWords(text, maxWords) {
  const words = text.split(/\s+/);
  if (words.length <= maxWords) return text;
  return words.slice(0, maxWords).join(" ") + "…";
}

export function splitAnswerLogic(text) {
  if (!text) return { answer: "", logic: "" };
  const idx = text.indexOf("<LOGIC>");
  if (idx === -1) {
    const cleaned = text.replace(/<\/?L(O(G(I(C)?)?)?)?>?$/i, "");
    return { answer: cleaned.trim(), logic: "" };
  }
  const answer = text.slice(0, idx).trim();
  const rest = text.slice(idx + 7);
  const end = rest.indexOf("</LOGIC>");
  const logic = (end === -1 ? rest : rest.slice(0, end)).trim();
  return { answer, logic: capWords(logic, LOGIC_WORD_CAP) };
}

/**
 * Shared "Why?" drawer: the astrological logic plus grouped shastra
 * excerpts. Used from Chat (per-message), the Yogas panel (per-yoga), and
 * the Muhurta quick-question box — previously only Chat had this, so the
 * other two surfaces showed a bare answer/explanation with nothing behind it.
 */
export default function WhyPanel({ open, onOpenChange, logic, citations, locked, emptyLabel }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-lg lg:max-w-xl bg-[color:var(--jai-surface)] border-[color:var(--jai-border)] overflow-y-auto"
        data-testid="why-panel"
      >
        <SheetHeader>
          <SheetTitle className="font-serif-display text-[color:var(--jai-green-deep)] flex items-center gap-2">
            <Info size={16} className="text-[color:var(--jai-gold)]" /> The astrological logic
          </SheetTitle>
        </SheetHeader>
        <div className="mt-6 space-y-6">
          {locked ? (
            <div className="text-center py-10" data-testid="why-upgrade-prompt">
              <Info size={22} className="text-[color:var(--jai-gold)] mx-auto mb-3" />
              <p className="text-sm text-[color:var(--jai-parchment)] font-serif-display text-base mb-2">
                Upgrade to Advanced or Astrologer mode
              </p>
              <p className="text-sm text-[color:var(--jai-text-muted)] max-w-xs mx-auto leading-relaxed">
                The full astrological reasoning — planets, houses, dashas, transits, and shastra citations behind
                this answer — is available in Advanced mode.
              </p>
            </div>
          ) : logic ? (
            <div className="md-body text-sm text-[color:var(--jai-parchment)]">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{logic}</ReactMarkdown>
            </div>
          ) : (
            <p className="text-sm text-[color:var(--jai-text-muted)] italic">
              {emptyLabel || "No logic recorded for this answer."}
            </p>
          )}

          {!locked && citations?.length > 0 && (
            <div>
              <div className="overline mb-3">Shastra excerpts consulted</div>
              <div className="space-y-4">
                {groupCitationsByBook(citations).map((grouped) => (
                  <div key={grouped.book} className="border-l-2 border-[color:var(--jai-gold)] pl-3">
                    <div className="text-[10px] uppercase tracking-widest text-[color:var(--jai-gold)]">{grouped.book}</div>
                    <div className="mt-1 space-y-2">
                      {grouped.excerpts.map((e) => (
                        <div key={e.idx}>
                          <div className="text-[9px] uppercase tracking-widest text-[color:var(--jai-text-muted)]">[{e.idx}] {e.chapter}</div>
                          <div className="mt-0.5 italic font-serif-display text-sm leading-relaxed text-[color:var(--jai-parchment)]">"{e.text}"</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
