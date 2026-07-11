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

## Backlog / Next Actions
- P1: Multi-chart profiles + Emergent Google Auth (user login) — next up
- P1: Panchanga daily card (tithi, yoga, karana, hora, rahu kala)
- P1: More divisional charts (D10 Dashamsa career, D7 Saptamsa children, D24 Chaturvimshamsa learning)
- P2: Kundali matching (Ashtakoot) for two natives
- P2: Muhurta / auspicious timing recommendations
- P2: Vector embeddings (upgrade from BM25) as corpus grows past ~500 chunks
- P2: Ashtakavarga (SAV/BAV) transit strength scoring
