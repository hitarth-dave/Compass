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

## Iteration 4-5 (2026-07-13) — Chat & sidebar upgrades
- Markdown rendering in chat via `react-markdown` + `remark-gfm` (styled via .md-body CSS)
- System prompt rewritten: plain everyday language, ≤300 words, NO jargon (nakshatra/dasha/etc.) in visible reply; technical reasoning embedded in a `<LOGIC>...</LOGIC>` block that the frontend strips from the bubble
- "Why?" button per assistant message opens a right-side Sheet (`data-testid=logic-panel`) showing the LOGIC content + shastra excerpts consulted
- Collapsible sidebar: hamburger toggle switches w-72↔w-16, persisted via `localStorage['jyotish_sidebar_collapsed']`
- Multiple named chat threads under Conversation: expand toggle, create/rename/delete via dropdown menu + AlertDialog; URL keyed by `?t=<threadId>`; each thread has its own history
- Voice mic via Web Speech API (webkitSpeechRecognition) into the input textarea
- Image attachments (JPG/PNG/WEBP) upload to `/api/chat/attachment` and stream to Claude Sonnet 4.5 vision via `ImageContent(image_base64=…)` — real vision output (colors/shapes/text) confirmed by iteration-5 test

## Backlog / Next Actions
- P1: Multi-chart profiles + Emergent Google Auth (user login) — next up
- P1: Panchanga daily card (tithi, yoga, karana, hora, rahu kala)
- P1: More divisional charts (D10 Dashamsa career, D7 Saptamsa children, D24 Chaturvimshamsa learning)
- P2: Kundali matching (Ashtakoot) for two natives
- P2: Muhurta / auspicious timing recommendations
- P2: Vector embeddings (upgrade from BM25) as corpus grows past ~500 chunks
- P2: Ashtakavarga (SAV/BAV) transit strength scoring
- Polish: aria-describedby on Sheet/AlertDialog; defer user_msg persistence until first delta; thread delete → 404 on missing id; make thread-menu visible for keyboard/touch users
