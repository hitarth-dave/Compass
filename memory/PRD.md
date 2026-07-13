# Jyotish AI — Product Requirements

## Original Problem Statement
User wants a Vedic astrology conversational web app. Backend uses ~100 Sanatan/Hindu Shastra & astrology books as the *single source of truth*. A Claude LLM layer interprets those books together with the user's Kundali chart and live planetary transits to answer questions and give predictions.

## User Choices (2026-07)
- **LLM**: Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`) via `emergentintegrations`
- **Knowledge base**: Both seeded corpus + user PDF uploads
- **Kundali & Transits**: Swiss Ephemeris (sidereal, Lahiri ayanamsa)
- **Auth**: Skipped for now — profile stored per browser via localStorage

## Architecture
- **Backend** (`/app/backend`):
  - `server.py` — FastAPI + `/api` router, SSE chat streaming, profile & book CRUD
  - `astrology.py` — Vedic chart, planets, nakshatras, Vimshottari Dashas, live transits
  - `knowledge.py` — Seeded excerpts from BPHS, Phaladeepika, Saravali, Jaimini, Uttara Kalamrita, Prashna Marga, etc. + PDF ingestion + BM25 retrieval
- **Frontend** (`/app/frontend/src`):
  - Onboarding → birth details form with Shadcn Calendar + geopy geocoding
  - Dashboard → SVG North-Indian Kundali chart, live transits, Vimshottari 120-yr timeline
  - Chat → streaming SSE chat with citation chips + tooltips
  - Library → grid of scriptures + search + PDF upload

## Implemented (2026-07-10)
- P0: onboarding, chart computation, dashboard, live transits, dasha timeline
- P0: chat streaming with Claude 4.5 + RAG citations grounded in Shastras
- P0: seed corpus (12 books, 20 passages) + PDF upload + BM25 search
- P0: Mystical dark UI (Cormorant Garamond + Manrope), gold/indigo palette

## Iteration 2 (2026-07-11) — Chart-aware + light theme
- Palette flipped to parchment / bottle-green light theme (Cormorant + Manrope preserved)
- KundaliChart renders planet name + degree + dignity codes (↑ Exalted, ↓ Debilitated, MT, OWN, VG) with color coding
- astrology.py adds: house_lords (12), Vimshottari Antardasha computation, Navamsa (D9) chart, yoga detection (Gaja Kesari, Chandra Mangala, Budha-Aditya, Kemadruma, Raja Yoga), transits with house_from_lagna + house_from_moon
- Chat handler uses skill-derived system prompt with structured response (Acknowledge/Chart Factors/Shastra Analysis/Synthesis/Prediction/Remedy)
- Conversation memory: prior turns summarized into system prompt for continuity
- Retrieval raised from k=5 → k=8; citations include BM25 score
- Dashboard adds panels: D9 Navamsa chart, House Lords with lord's placement, Detected Yogas, Antardasha alongside Mahadasha
- Chat adds "Show retrieved passages" toggle per assistant message revealing full excerpts on a parchment panel

## Iteration 3 (2026-07-11) — Parashara's Light chart notation
- KundaliChart rewritten to match Parashara's Light standard: 12-region NI diamond, planet initials (Su/Mo/Ma/Me/Ju/Ve/Sa/Ra/Ke) + retrograde "R" + DD:MM degree + 3-letter nakshatra abbreviation, color-coded per graha
- Ascendant rendered as "As DD:MM Nak" inside H1
- House-number positions fixed to prevent overlap
- Chat bug fix: MessageBubble now destructures {msg, idx} — was throwing ReferenceError

## Iteration 6 (2026-07-13) — Rebrand + Auth + Book scoping
- **Rebrand** Jyotish AI → **Compass Astro** ("Ancient wisdom, clear direction") across UI, page titles, system prompts.
- **Emergent Google Auth**: `/auth/session` exchanges Google `session_id` → 7-day `session_token` cookie + backend `user_sessions` collection; `/auth/me` + `/auth/logout`. Backend uses `Depends(get_current_user)` on every protected endpoint (falls back to `Authorization: Bearer` header for tests). Structure ready for future email/password provider.
- **Landing page** for logged-out visitors (`/`) with hero, feature cards, and "Continue with Google" button.
- **User-scoped data**: profiles, threads, messages, book_chunks, attachments all tagged with `user_id`. Custom `user_id` UUID (never `_id`).
- **Auto-name threads**: background Claude Haiku 4.5 call after first user turn generates a 2-5 word title if the thread has a default name; manual rename still works.
- **Library seed vs custom**: `/api/books` returns `{seed: [...], custom: [...]}`; delete only allowed on custom books (`DELETE /api/books/{book_id}` — seed is 400); UI shows locked seed corpus + user's uploads with a delete button.
- **Per-message book scoping**: `detect_book_scope()` parses trigger phrases ("from X", "as per X", "@X", etc.) against the user's book list. If a match is found, that turn's retrieval is filtered to that book and Claude is instructed to cite only from it. The filter NEVER persists past the current message — next question searches the full library again.

## Backlog / Next Actions
- P1: Email/password provider alongside Google (auth structure already ready)
- P1: Panchanga daily card (tithi, yoga, karana, rahu kala)
- P1: More divisional charts (D10 Dashamsa, D7, D24)
- P2: Ashtakoot matching, Muhurta timings, Ashtakavarga
- P2: Vector embeddings (upgrade from BM25) as corpus grows
- Polish: aria-describedby, thread-menu accessibility, resend/retry on stream failure
