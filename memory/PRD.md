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

## Backlog / Next Actions
- P1: Divisional charts (Navamsa D9, Dashamsa D10)
- P1: Antardasha (sub-period) computation & display
- P1: Panchanga (tithi, yoga, karana) daily card
- P2: User accounts & multi-chart storage
- P2: Muhurta / auspicious timing recommendations
- P2: Kundali matching (Ashtakoot) for two natives
- P2: Vector embeddings for semantic retrieval (upgrade from BM25)
