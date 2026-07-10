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

from astrology import compute_chart, current_transits, current_dasha, PLANET_SYMBOLS
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
    chart['profile'] = {
        'name': doc['name'], 'dob': doc['dob'], 'tob': doc['tob'], 'place': doc['place']
    }
    return chart


@api_router.get("/transits")
async def get_transits():
    return current_transits()


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
    curr_dasha = chart.get('current_dasha')
    planets_lines = "\n".join(
        f"  - {pl['name']} in {pl['sign']} ({pl['sign_en']}) {pl['degree_in_sign']}° "
        f"house {pl['house']}, nakshatra {pl['nakshatra']}"
        + (" [R]" if pl.get('retrograde') else "")
        for pl in chart['planets']
    )
    transit_lines = "\n".join(
        f"  - {t['name']} in {t['sign']} ({t['sign_en']}) {t['degree_in_sign']}° — nak {t['nakshatra']}"
        + (" [R]" if t.get('retrograde') else "")
        for t in transits['planets']
    )
    ctx = f"""NATIVE'S BIRTH DETAILS
Name: {p['name']}
Date/Time: {p['dob']} {p['tob']} at {p['place']}

LAGNA (Ascendant): {asc['sign']} ({asc['sign_en']}) {asc['degree_in_sign']}°

NATAL PLANETS (sidereal / Lahiri):
{planets_lines}

CURRENT MAHADASHA: {curr_dasha['lord']} ({curr_dasha['start']} → {curr_dasha['end']}) — {curr_dasha['years']} yrs
""" if curr_dasha else f"""NATIVE'S BIRTH DETAILS
Name: {p['name']}
Date/Time: {p['dob']} {p['tob']} at {p['place']}

LAGNA (Ascendant): {asc['sign']} ({asc['sign_en']}) {asc['degree_in_sign']}°

NATAL PLANETS (sidereal / Lahiri):
{planets_lines}
"""

    ctx += f"\nCURRENT PLANETARY TRANSITS (as of {transits['as_of'][:10]}):\n{transit_lines}\n"

    if retrieved:
        ctx += "\nRELEVANT SHASTRA EXCERPTS (single source of truth — cite these):\n"
        for i, r in enumerate(retrieved, 1):
            ctx += f"\n[{i}] {r['book']} — {r['chapter']}\n{r['text']}\n"
    return ctx


SYSTEM_PROMPT = """You are Jyotish AI — a compassionate, precise Vedic astrologer trained in the classical Sanatan Shastras (Brihat Parashara Hora Shastra, Phaladeepika, Saravali, Jaimini Sutras, Uttara Kalamrita, and more).

Rules of engagement:
1. The SHASTRA EXCERPTS provided below the birth details are your single source of truth. Always ground your interpretation in them and cite them inline as [1], [2], etc.
2. Read the native's natal chart carefully — Lagna, planetary placements, nakshatras, current Mahadasha — and cross-reference with the live transits.
3. Structure your response with warm clarity: (a) what the classical texts say, (b) how it applies to this native's chart right now, (c) practical guidance and remedies (upayas) if appropriate.
4. Use Sanskrit terms respectfully (Lagna, Rashi, Nakshatra, Dasha, Graha) with brief English glosses.
5. Never fabricate scripture. If the excerpts don't cover the question, say so honestly and offer general Vedic principles instead.
6. Speak in a calm, reverent, first-person tone. Avoid disclaimers about "not being a real astrologer" — you are a knowledgeable guide."""


@api_router.post("/chat")
async def chat_stream(req: ChatRequest):
    # Load profile + chart + transits + retrieve
    prof = await db.profiles.find_one({"id": req.profile_id}, {"_id": 0})
    if not prof:
        raise HTTPException(404, "Profile not found")

    chart = compute_chart(prof['dob'], prof['tob'], prof['tz_offset'], prof['lat'], prof['lon'])
    chart['profile'] = {'name': prof['name'], 'dob': prof['dob'], 'tob': prof['tob'], 'place': prof['place']}
    chart['current_dasha'] = current_dasha(chart['dashas'])
    transits = current_transits()
    retrieved = KB.search(req.message, k=5)

    context_block = _build_context(chart, transits, retrieved)

    # Persist user message
    await db.messages.insert_one({
        "session_id": req.session_id,
        "profile_id": req.profile_id,
        "role": "user",
        "content": req.message,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Fetch prior messages for this session (excluding the one just added)
    prior = await db.messages.find(
        {"session_id": req.session_id, "role": {"$in": ["user", "assistant"]}},
        {"_id": 0}
    ).sort("created_at", 1).to_list(50)

    system_message = SYSTEM_PROMPT + "\n\n" + context_block

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=req.session_id,
        system_message=system_message,
    ).with_model("anthropic", "claude-sonnet-4-5-20250929")

    citations_payload = [
        {"idx": i + 1, "book": r["book"], "chapter": r["chapter"], "text": r["text"]}
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
