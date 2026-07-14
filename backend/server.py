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

from anthropic import AsyncAnthropic
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', '/app/backend/uploads'))
ATTACH_DIR = UPLOAD_DIR / 'attachments'
ATTACH_DIR.mkdir(parents=True, exist_ok=True)

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']
CLAUDE_MODEL = os.environ.get('CLAUDE_MODEL', 'claude-sonnet-4-5-20250929')
anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

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
    attachment_urls: Optional[List[str]] = None


class ThreadCreate(BaseModel):
    profile_id: str
    name: str = "New chat"


class ThreadRename(BaseModel):
    name: str


class Thread(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    profile_id: str
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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


SYSTEM_PROMPT = """You are Jyotish AI — a warm, calm Vedic astrology guide. You speak like a wise friend, not a scholar.

## HARD RULES FOR THE ANSWER YOU SHOW THE USER
1. Everyday, plain English. Assume the user has ZERO astrology knowledge.
2. NO jargon in the visible answer. Never use these words in the main reply: nakshatra, retrograde, house (as in 10th house), dasha, antardasha, lagna, ascendant, graha, kendra, trikona, moolatrikona, vargottama, sign lord, planet lord, transit, aspect, degree, exalted, debilitated, ayanamsa. Translate them to natural language ("this phase of your life", "your career area", "the friend/planet guiding you now", "an important shift").
3. Maximum 300 words. Prefer 150–200. Short paragraphs, no headers, minimal bullets.
4. Direct answer to the question first. Then 2–4 sentences of grounded insight. Then one gentle, practical suggestion or remedy (in plain words, e.g. "chant on Tuesday mornings" instead of "Mangal beej mantra").
5. Never mention "as per BPHS [1]", "shastra", "citations", or reference numbers to the user. That reasoning lives ONLY in the LOGIC block below.

## LOGIC BLOCK (technical — hidden from the user, always required)
After your plain-language answer, output exactly this on a new line:

<LOGIC>
Then write the technical astrological reasoning: the planets, houses, nakshatras, dashas, antardashas, transits, dignities involved. Cite the shastra excerpts inline as [1], [2], etc. Structure it as short bullets:
- Chart factors: (planets/houses/dignities relevant)
- Dasha & timing: (Mahadasha/Antardasha, upcoming shift)
- Transits: (which transiting planets touch which natal points)
- Shastra grounding: (cite [N] excerpts)
- Synthesis: (why this configuration causes what the user is experiencing)
</LOGIC>

Do NOT deviate from this two-section format. The LOGIC block is required every time — even for greetings or vague questions — so the "Why?" panel always has content."""


def _summarize_prior_messages(prior: List[dict], max_turns: int = 6) -> str:
    """Compress prior chat turns into a compact recap for continuity."""
    if not prior:
        return ""
    tail = prior[-(max_turns * 2):]
    lines = []
    for m in tail:
        role = "User" if m["role"] == "user" else "Jyotish AI"
        # Use answer-only (strip LOGIC) for prior context
        content = (m.get("content") or "").strip()
        if "<LOGIC>" in content:
            content = content.split("<LOGIC>", 1)[0].strip()
        if len(content) > 300:
            content = content[:300] + "…"
        lines.append(f"{role}: {content}")
    return "\n\nPRIOR CONVERSATION (for continuity):\n" + "\n".join(lines)


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

    # Build attachments as base64 image blocks for Claude's native vision format.
    def _media_type(fp: Path) -> str:
        ext = fp.suffix.lower()
        return {
            '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.gif': 'image/gif', '.webp': 'image/webp',
        }.get(ext, 'image/jpeg')

    image_blocks = []
    for url in (req.attachment_urls or []):
        rel = url.split('/api/attachments/')[-1]
        fp = ATTACH_DIR / rel
        if fp.exists():
            b64 = base64.b64encode(fp.read_bytes()).decode()
            image_blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": _media_type(fp), "data": b64},
            })

    citations_payload = [
        {"idx": i + 1, "book": r["book"], "chapter": r["chapter"], "text": r["text"], "score": round(r.get("score", 0), 3)}
        for i, r in enumerate(retrieved)
    ]

    async def event_generator():
        # Emit citations first
        yield f"event: citations\ndata: {json.dumps(citations_payload)}\n\n"
        full = ""
        try:
            content_blocks = image_blocks + [{"type": "text", "text": req.message}]
            async with anthropic_client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=4096,
                system=system_message,
                messages=[{"role": "user", "content": content_blocks}],
            ) as stream:
                async for text_delta in stream.text_stream:
                    full += text_delta
                    yield f"event: delta\ndata: {json.dumps({'text': text_delta})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        # Persist assistant reply — store both raw content (with LOGIC block) and pre-split fields
        answer_only = full
        logic_only = ""
        if "<LOGIC>" in full:
            parts = full.split("<LOGIC>", 1)
            answer_only = parts[0].strip()
            logic_only = parts[1].split("</LOGIC>", 1)[0].strip() if "</LOGIC>" in parts[1] else parts[1].strip()
        await db.messages.insert_one({
            "session_id": req.session_id,
            "profile_id": req.profile_id,
            "role": "assistant",
            "content": full,
            "answer": answer_only,
            "logic": logic_only,
            "citations": citations_payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Bump thread updated_at
        await db.threads.update_one({"id": req.session_id}, {"$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
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


# --- Threads (multiple named conversations per profile) ---
@api_router.get("/threads")
async def list_threads(profile_id: str):
    docs = await db.threads.find({"profile_id": profile_id}, {"_id": 0}).sort("updated_at", -1).to_list(100)
    return {"threads": docs}


@api_router.post("/threads")
async def create_thread(payload: ThreadCreate):
    t = Thread(profile_id=payload.profile_id, name=payload.name)
    doc = t.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['updated_at'] = doc['updated_at'].isoformat()
    await db.threads.insert_one({**doc})  # pass a copy so Mongo doesn't mutate return dict
    doc.pop('_id', None)
    return doc


@api_router.patch("/threads/{thread_id}")
async def rename_thread(thread_id: str, payload: ThreadRename):
    res = await db.threads.update_one(
        {"id": thread_id},
        {"$set": {"name": payload.name, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if not res.matched_count:
        raise HTTPException(404, "Thread not found")
    return {"ok": True}


@api_router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str):
    await db.threads.delete_one({"id": thread_id})
    await db.messages.delete_many({"session_id": thread_id})
    return {"ok": True}


# --- Attachment upload for chat vision ---
@api_router.post("/chat/attachment")
async def upload_attachment(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(400, "Only JPG/PNG/WEBP images are supported")
    fname = f"{uuid.uuid4().hex}{ext}"
    dest = ATTACH_DIR / fname
    content = await file.read()
    dest.write_bytes(content)
    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else ("image/png" if ext == ".png" else "image/webp")
    return {"url": f"/api/attachments/{fname}", "filename": file.filename, "mime_type": mime, "size": len(content)}


@api_router.get("/attachments/{fname}")
async def serve_attachment(fname: str):
    from fastapi.responses import FileResponse
    fp = ATTACH_DIR / fname
    if not fp.exists():
        raise HTTPException(404, "Not found")
    return FileResponse(str(fp))


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
