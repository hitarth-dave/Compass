from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
import json
import uuid
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator
from typing import List, Optional, Annotated, Any
from datetime import datetime, timezone

from astrology import (
    compute_chart, current_transits, current_dasha, current_antardasha,
    compute_antardashas, build_navamsa, PLANET_SYMBOLS,
)
from knowledge import KB

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

app = FastAPI(title="Jyotish AI")
api_router = APIRouter(prefix="/api")

# --- Base document helpers ---
def _validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    return str(v)

PyObjectId = Annotated[str, BeforeValidator(_validate_object_id)]


# --- Models ---
class BirthProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    dob: str  # YYYY-MM-DD
    tob: str  # HH:MM
    tz_offset: float  # e.g. 5.5
    lat: float
    lon: float
    place: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BirthProfileCreate(BaseModel):
    name: str
    dob: str
    tob: str
    tz_offset: float
    lat: float
    lon: float
    place: str


class ChatMessage(BaseModel):
    role: str  # 'user' | 'assistant'
    content: str
    citations: Optional[List[dict]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    profile_id: str
    session_id: str
    message: str


# --- Routes ---
@api_router.get("/")
async def root():
    return {"message": "Jyotish AI is listening. Ask the stars."}


@api_router.post("/profile", response_model=BirthProfile)
async def create_profile(payload: BirthProfileCreate):
    profile = BirthProfile(**payload.model_dump())
    doc = profile.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.profiles.insert_one(doc)
    return profile


@api_router.get("/profile/{profile_id}", response_model=BirthProfile)
async def get_profile(profile_id: str):
    doc = await db.profiles.find_one({"id": profile_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Profile not found")
    if isinstance(doc.get('created_at'), str):
        doc['created_at'] = datetime.fromisoformat(doc['created_at'])
    return BirthProfile(**doc)


@api_router.get("/profile/{profile_id}/chart")
async def get_chart(profile_id: str):
    doc = await db.profiles.find_one({"id": profile_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Profile not found")
    chart = compute_chart(doc['dob'], doc['tob'], doc['tz_offset'], doc['lat'], doc['lon'])
    chart['current_dasha'] = current_dasha(chart['dashas'])
    if chart['current_dasha']:
        chart['antardashas'] = compute_antardashas(chart['current_dasha'])
        chart['current_antardasha'] = current_antardasha(chart['current_dasha'])
    else:
        chart['antardashas'] = []
        chart['current_antardasha'] = None
    # Navamsa D9
    chart['navamsa'] = build_navamsa(chart['planets'], chart['ascendant']['longitude'])
    chart['profile'] = {
        'name': doc['name'], 'dob': doc['dob'], 'tob': doc['tob'], 'place': doc['place']
    }
    return chart


@api_router.get("/transits")
async def get_transits(profile_id: str | None = None):
    natal = None
    if profile_id:
        doc = await db.profiles.find_one({"id": profile_id}, {"_id": 0})
        if doc:
            natal = compute_chart(doc['dob'], doc['tob'], doc['tz_offset'], doc['lat'], doc['lon'])
    return current_transits(natal)


@api_router.get("/books")
async def list_books():
    return {"books": KB.list_books(), "total_chunks": len(KB.chunks)}


@api_router.post("/books/upload")
async def upload_book(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "Only PDF files are supported")
    content = await file.read()
    try:
        added = KB.add_pdf(file.filename, content)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse PDF: {e}")
    return {"filename": file.filename, "chunks_added": added, "total_chunks": len(KB.chunks)}


@api_router.get("/books/search")
async def search_books(q: str, k: int = 5):
    return {"results": KB.search(q, k=k)}


# --- Chat with Claude Sonnet 4.5 + RAG ---
def _build_context(chart: dict, transits: dict, retrieved: List[dict]) -> str:
    p = chart['profile']
    asc = chart['ascendant']
    md = chart.get('current_dasha')
    ad = chart.get('current_antardasha')

    planets_lines = "\n".join(
        f"  - {pl['name']:<8} in {pl['sign_en']:<12} {pl['degree_in_sign']:.2f}°  house {pl['house']:<2}  "
        f"nakshatra {pl['nakshatra']:<15} D9→{pl['navamsa_sign']}"
        + (" [R]" if pl.get('retrograde') else "")
        + (f"  <{', '.join(pl['dignity'])}>" if pl.get('dignity') else "")
        for pl in chart['planets']
    )
    house_lords_lines = "\n".join(
        f"  - H{h['house']:<2} ({h['sign_en']}) → lord {h['lord']}"
        + (f" sits in H{h['lord_sits_in_house']} ({h['lord_sits_in_sign_en']} {h['lord_degree']}°)"
           if h.get('lord_sits_in_house') else "")
        for h in chart.get('house_lords', [])
    )
    yogas_lines = ("\n".join(f"  - {y['name']}: {y['detail']}" for y in chart.get('yogas', [])) or "  (none of the tracked yogas detected)")

    transit_lines = "\n".join(
        f"  - {t['name']:<8} in {t['sign_en']:<12} {t['degree_in_sign']:.2f}°"
        + (f"  → H{t['house_from_lagna']} from Lagna" if 'house_from_lagna' in t else "")
        + (f", H{t['house_from_moon']} from Moon" if 'house_from_moon' in t else "")
        + (" [R]" if t.get('retrograde') else "")
        for t in transits['planets']
    )

    ctx = f"""NATIVE'S BIRTH DETAILS
Name: {p['name']}
Date/Time: {p['dob']} {p['tob']} at {p['place']}

LAGNA (Ascendant): {asc['sign_en']} {asc['degree_in_sign']}°   (Lagna lord: {asc.get('lord', '?')})

NATAL PLANETS (sidereal / Lahiri):
{planets_lines}

HOUSE LORDS (Rasi):
{house_lords_lines}

CLASSICAL YOGAS DETECTED:
{yogas_lines}
"""

    if md:
        ctx += f"\nCURRENT MAHADASHA: {md['lord']} ({md['start']} → {md['end']}, {md['years']} yrs total)\n"
        if ad:
            ctx += f"CURRENT ANTARDASHA: {ad['lord']} ({ad['start']} → {ad['end']}, {ad['years']} yrs)\n"

    ctx += f"\nCURRENT PLANETARY TRANSITS (as of {transits['as_of'][:10]}):\n{transit_lines}\n"

    if retrieved:
        ctx += "\nRELEVANT SHASTRA EXCERPTS (single source of truth — cite these):\n"
        for i, r in enumerate(retrieved, 1):
            ctx += f"\n[{i}] {r['book']} — {r['chapter']}\n{r['text']}\n"
    return ctx


SYSTEM_PROMPT = """You are Jyotish AI — the native's personal Vedic astrologer, deeply versed in the classical Sanatan shastras: Brihat Parashara Hora Shastra (BPHS), Phaladipika, Laghu Parashari, Sarvartha Chintamani, Muhurta Chintamani, Jataka Nirnaya, BVR's How to Judge a Horoscope (Vols 1 & 2), Scientific Hindu Astrology (Prof. B.V. Raman), and Lal Kitab for remedies.

## HARD RULES
1. The SHASTRA EXCERPTS block below is your single source of truth. Cite them inline as [1], [2], etc. Never fabricate a shloka.
2. Every reading MUST reason from the native's actual chart data that follows — the Lagna, planetary placements (sign, degree, house, nakshatra, dignity, D9), house lords, detected yogas, current Mahadasha & Antardasha, and today's transits.
3. If a question is "why is my career stuck / relationship difficult / health off", identify the specific houses (10th for career, 7th for spouse, 6th for health, etc.), their lords' placements, the current dasha lord's relationship to those houses, and the transiting planets over those natal points. Never give generic astrology — always ground in this native's exact configuration.

## RESPONSE STRUCTURE (follow every time)
**Acknowledge** — one line restating what is being asked astrologically.
**Chart factors** — bullet the exact houses, planets, dasha, and transits at play in *this* chart.
**Shastra analysis** — cite classical rules from the excerpts: `As per BPHS [1]…`, `Laghu Parashari [3] states…`.
**Synthesis** — connect the rules to this native's specific configuration and explain the *cause* of what's happening.
**Prediction / timing** — what unfolds and when, mapped to upcoming antardashas or transits.
**Remedy (upaya)** — 1–2 concrete remedies from the texts (mantra, gemstone, charity, Lal Kitab upaya). Cite the source.

## STYLE
- Speak as a calm, wise Jyotishi. Use Sanskrit naturally (Lagna, Rashi, Nakshatra, Dasha, Graha) with brief English glosses.
- Be specific about timing, planets, and houses — never fortune-cookie vague.
- If the excerpts don't cover the exact question, say so honestly and reason from Vedic principles + the chart in front of you.
- No disclaimers about not being a real astrologer — you are the guide.
"""


def _summarize_prior_messages(prior: List[dict], max_turns: int = 6) -> str:
    """Compress prior chat turns into a compact recap for continuity."""
    if not prior:
        return ""
    tail = prior[-(max_turns * 2):]
    lines = []
    for m in tail:
        role = "Native" if m["role"] == "user" else "Jyotishi"
        content = (m["content"] or "").strip()
        if len(content) > 400:
            content = content[:400] + "…"
        lines.append(f"{role}: {content}")
    return "\n\nPRIOR CONVERSATION (for continuity — do not repeat verbatim):\n" + "\n".join(lines)


@api_router.post("/chat")
async def chat_stream(req: ChatRequest):
    prof = await db.profiles.find_one({"id": req.profile_id}, {"_id": 0})
    if not prof:
        raise HTTPException(404, "Profile not found")

    chart = compute_chart(prof['dob'], prof['tob'], prof['tz_offset'], prof['lat'], prof['lon'])
    chart['profile'] = {'name': prof['name'], 'dob': prof['dob'], 'tob': prof['tob'], 'place': prof['place']}
    chart['current_dasha'] = current_dasha(chart['dashas'])
    if chart['current_dasha']:
        chart['current_antardasha'] = current_antardasha(chart['current_dasha'])
    transits = current_transits(chart)
    retrieved = KB.search(req.message, k=8)

    context_block = _build_context(chart, transits, retrieved)

    # Load prior conversation for memory (before saving current user message)
    prior = await db.messages.find(
        {"session_id": req.session_id, "role": {"$in": ["user", "assistant"]}},
        {"_id": 0}
    ).sort("created_at", 1).to_list(50)
    memory_block = _summarize_prior_messages(prior)

    # Persist user message
    await db.messages.insert_one({
        "session_id": req.session_id,
        "profile_id": req.profile_id,
        "role": "user",
        "content": req.message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    system_message = SYSTEM_PROMPT + "\n\n" + context_block + memory_block

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=req.session_id,
        system_message=system_message,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    citations_payload = [
        {"idx": i + 1, "book": r["book"], "chapter": r["chapter"], "text": r["text"], "score": round(r.get("score", 0), 3)}
        for i, r in enumerate(retrieved)
    ]

    async def event_generator():
        # Emit citations first
        yield f"event: citations\ndata: {json.dumps(citations_payload)}\n\n"
        full = ""
        try:
            async for ev in chat.stream_message(UserMessage(text=req.message)):
                if isinstance(ev, TextDelta):
                    full += ev.content
                    yield f"event: delta\ndata: {json.dumps({'text': ev.content})}\n\n"
                elif isinstance(ev, StreamDone):
                    break
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        # Persist assistant reply
        await db.messages.insert_one({
            "session_id": req.session_id,
            "profile_id": req.profile_id,
            "role": "assistant",
            "content": full,
            "citations": citations_payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        yield f"event: done\ndata: {json.dumps({'ok': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api_router.get("/chat/{session_id}/history")
async def chat_history(session_id: str):
    msgs = await db.messages.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    return {"messages": msgs}


# --- Simple geocoding via geopy nominatim (fallback to manual entry) ---
@api_router.get("/geocode")
async def geocode(q: str):
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent="jyotish-ai")
    try:
        loc = geolocator.geocode(q, timeout=10)
        if not loc:
            return {"results": []}
        return {"results": [{"place": loc.address, "lat": loc.latitude, "lon": loc.longitude}]}
    except Exception as e:
        return {"results": [], "error": str(e)}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
