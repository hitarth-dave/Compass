from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Depends, Request, Response, Cookie, Header
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
import json
import uuid
import base64
import re
import asyncio
import httpx
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator
from typing import List, Optional, Annotated, Any
from datetime import datetime, timezone, timedelta

from astrology import (
    compute_chart, current_transits, current_dasha, current_antardasha,
    compute_antardashas, build_navamsa,
)
if os.environ.get('KNOWLEDGE_SOURCE', 'original') == 'v1':
    from knowledge_v1 import (
        SEED_CORPUS, search_for_user, list_books_for_user, add_pdf_for_user,
        delete_book_for_user, detect_book_scope,
    )
else:
    from knowledge import (
        SEED_CORPUS, search_for_user, list_books_for_user, add_pdf_for_user,
        delete_book_for_user, detect_book_scope,
    )

from anthropic import AsyncAnthropic

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
CLAUDE_TITLE_MODEL = os.environ.get('CLAUDE_TITLE_MODEL', 'claude-haiku-4-5-20251001')
anthropic_client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
EMERGENT_AUTH_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

app = FastAPI(title="Compass Astro")
api_router = APIRouter(prefix="/api")


# ---------- Auth models ----------
class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    phone: Optional[str] = None
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    current_place: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


class LocationUpdate(BaseModel):
    lat: float
    lon: float
    place: str


class SessionExchange(BaseModel):
    session_id: str


# ---------- Dependency: current user ----------
async def get_current_user(
    session_token: Optional[str] = Cookie(default=None),
    authorization: Optional[str] = Header(default=None),
) -> User:
    token = session_token
    if not token and authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sess = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=401, detail="Session not found")

    expires_at = sess.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user_doc = await db.users.find_one({"user_id": sess["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    if isinstance(user_doc.get("created_at"), str):
        user_doc["created_at"] = datetime.fromisoformat(user_doc["created_at"])
    return User(**user_doc)


# ---------- Domain models ----------
class BirthProfileCreate(BaseModel):
    name: str
    dob: str
    tob: str
    tz_offset: float
    lat: float
    lon: float
    place: str


class BirthProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    dob: str
    tob: str
    tz_offset: float
    lat: float
    lon: float
    place: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    session_id: str
    message: str
    attachment_urls: Optional[List[str]] = None


class ThreadCreate(BaseModel):
    name: str = "New chat"


class ThreadRename(BaseModel):
    name: str


# ---------- Routes ----------
@api_router.get("/")
async def root():
    return {"message": "Compass Astro is listening. Ask the stars."}


# ---------- Auth endpoints ----------
@api_router.post("/auth/session")
async def create_session(payload: SessionExchange, response: Response):
    """Exchange Emergent session_id for a session_token; set httpOnly cookie."""
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.get(EMERGENT_AUTH_URL, headers={"X-Session-ID": payload.session_id})
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail=f"Auth exchange failed: {r.status_code}")
    data = r.json()
    email = data.get("email")
    name = data.get("name") or (email.split("@")[0] if email else "Seeker")
    picture = data.get("picture")
    session_token = data.get("session_token")
    if not email or not session_token:
        raise HTTPException(status_code=401, detail="Malformed auth response")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one({"user_id": user_id}, {"$set": {"name": name, "picture": picture}})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": name, "picture": picture,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    response.set_cookie(
        key="session_token", value=session_token, httponly=True, secure=True,
        samesite="none", path="/", max_age=7 * 24 * 3600,
    )
    return {"user_id": user_id, "email": email, "name": name, "picture": picture, "session_token": session_token}


@api_router.get("/auth/me", response_model=User)
async def me(user: User = Depends(get_current_user)):
    return user


@api_router.post("/auth/logout")
async def logout(response: Response, session_token: Optional[str] = Cookie(default=None)):
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie("session_token", path="/", samesite="none", secure=True)
    return {"ok": True}


# ---------- Account (profile info, current location, delete) ----------
@api_router.patch("/account", response_model=User)
async def update_account(payload: AccountUpdate, user: User = Depends(get_current_user)):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if update:
        await db.users.update_one({"user_id": user.user_id}, {"$set": update})
    doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    if isinstance(doc.get("created_at"), str):
        doc["created_at"] = datetime.fromisoformat(doc["created_at"])
    return User(**doc)


@api_router.put("/account/location", response_model=User)
async def update_current_location(payload: LocationUpdate, user: User = Depends(get_current_user)):
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {"current_lat": payload.lat, "current_lon": payload.lon, "current_place": payload.place}},
    )
    doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    if isinstance(doc.get("created_at"), str):
        doc["created_at"] = datetime.fromisoformat(doc["created_at"])
    return User(**doc)


@api_router.delete("/account")
async def delete_account(response: Response, user: User = Depends(get_current_user)):
    """Permanently deletes the user and everything tied to their account."""
    await db.users.delete_one({"user_id": user.user_id})
    await db.user_sessions.delete_many({"user_id": user.user_id})
    await db.profiles.delete_one({"user_id": user.user_id})
    await db.threads.delete_many({"user_id": user.user_id})
    await db.messages.delete_many({"user_id": user.user_id})
    await db.book_chunks.delete_many({"user_id": user.user_id})
    response.delete_cookie("session_token", path="/", samesite="none", secure=True)
    return {"ok": True}


# ---------- Profile ----------
@api_router.get("/profile")
async def get_profile(user: User = Depends(get_current_user)):
    doc = await db.profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    if not doc:
        return None
    if isinstance(doc.get('created_at'), str):
        doc['created_at'] = datetime.fromisoformat(doc['created_at'])
    return BirthProfile(**doc)


@api_router.post("/profile", response_model=BirthProfile)
async def upsert_profile(payload: BirthProfileCreate, user: User = Depends(get_current_user)):
    existing = await db.profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    if existing:
        update = {**payload.model_dump()}
        await db.profiles.update_one({"user_id": user.user_id}, {"$set": update})
        merged = {**existing, **update}
        if isinstance(merged.get('created_at'), str):
            merged['created_at'] = datetime.fromisoformat(merged['created_at'])
        return BirthProfile(**merged)
    profile = BirthProfile(user_id=user.user_id, **payload.model_dump())
    doc = profile.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.profiles.insert_one({**doc})
    return profile


@api_router.get("/profile/chart")
async def get_chart(user: User = Depends(get_current_user)):
    doc = await db.profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Set up your birth details first")
    chart = compute_chart(doc['dob'], doc['tob'], doc['tz_offset'], doc['lat'], doc['lon'])
    chart['current_dasha'] = current_dasha(chart['dashas'])
    if chart['current_dasha']:
        chart['antardashas'] = compute_antardashas(chart['current_dasha'])
        chart['current_antardasha'] = current_antardasha(chart['current_dasha'])
    else:
        chart['antardashas'] = []
        chart['current_antardasha'] = None
    chart['navamsa'] = build_navamsa(chart['planets'], chart['ascendant']['longitude'])
    chart['profile'] = {'name': doc['name'], 'dob': doc['dob'], 'tob': doc['tob'], 'place': doc['place']}
    return chart


@api_router.get("/transits")
async def get_transits(user: User = Depends(get_current_user)):
    doc = await db.profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    natal = None
    if doc:
        natal = compute_chart(doc['dob'], doc['tob'], doc['tz_offset'], doc['lat'], doc['lon'])
    return current_transits(natal)


# ---------- Books (seed vs custom, per-user upload/delete) ----------
@api_router.get("/books")
async def list_books(user: User = Depends(get_current_user)):
    return await list_books_for_user(db, user.user_id)


@api_router.post("/books/upload")
async def upload_book(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    if not (file.filename or "").lower().endswith('.pdf'):
        raise HTTPException(400, "Only PDF files are supported")
    content = await file.read()
    try:
        result = await add_pdf_for_user(db, user.user_id, file.filename, content)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse PDF: {e}")
    return result


@api_router.delete("/books/{book_id}")
async def delete_book(book_id: str, user: User = Depends(get_current_user)):
    if book_id == "seed":
        raise HTTPException(400, "Seed corpus is read-only")
    n = await delete_book_for_user(db, user.user_id, book_id)
    return {"deleted_chunks": n}


@api_router.get("/books/search")
async def search_books(q: str, k: int = 5, user: User = Depends(get_current_user)):
    results = await search_for_user(db, user.user_id, q, k=k)
    return {"results": results}


# ---------- Chat (with per-message book scoping, auto-name, memory) ----------
SYSTEM_PROMPT = """You are Compass Astro — a warm, calm Vedic astrology guide. You speak like a wise friend, not a scholar.

## HARD RULES FOR THE ANSWER YOU SHOW THE USER
1. Everyday, plain English. Assume the user has ZERO astrology knowledge.
2. NO jargon in the visible answer. Never use these words in the main reply: nakshatra, retrograde, house (as in 10th house), dasha, antardasha, lagna, ascendant, graha, kendra, trikona, moolatrikona, vargottama, sign lord, planet lord, transit, aspect, degree, exalted, debilitated, ayanamsa. Translate them to natural language ("this phase of your life", "your career area", "the friend/planet guiding you now", "an important shift").
3. Maximum 300 words. Prefer 150–200. Short paragraphs, no headers, minimal bullets.
4. Direct answer to the question first. Then 2–4 sentences of grounded insight. Then one gentle, practical suggestion or remedy (in plain words, e.g. "chant on Tuesday mornings" instead of "Mangal beej mantra").
5. Never mention "as per BPHS [1]", "shastra", "citations", or reference numbers to the user. That reasoning lives ONLY in the LOGIC block below.

## LOGIC BLOCK (technical — hidden from the user, always required)
After your plain-language answer, output exactly this on a new line:

<LOGIC>
Then write the technical astrological reasoning: the planets, houses, nakshatras, dashas, antardashas, transits, dignities involved. Cite the shastra excerpts inline as [1], [2], etc.

HARD LENGTH LIMIT: 600 words maximum for this entire block. Keep every bullet to 1-2 lines — this is a scannable technical summary, not an essay. Structure it as exactly these 5 bullet categories, one bullet each:
- Chart factors: (planets/houses/dignities relevant)
- Dasha & timing: (Mahadasha/Antardasha, upcoming shift)
- Transits: (which transiting planets touch which natal points)
- Shastra grounding: (cite [N] excerpts)
- Synthesis: (why this configuration causes what the user is experiencing)
</LOGIC>

Do NOT deviate from this two-section format."""


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
        + (f" sits in H{h['lord_sits_in_house']} ({h['lord_sits_in_sign_en']} {h['lord_degree']}°)" if h.get('lord_sits_in_house') else "")
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


def _summarize_prior_messages(prior: List[dict], max_turns: int = 6) -> str:
    if not prior:
        return ""
    tail = prior[-(max_turns * 2):]
    lines = []
    for m in tail:
        role = "User" if m["role"] == "user" else "Compass Astro"
        content = (m.get("content") or "").strip()
        if "<LOGIC>" in content:
            content = content.split("<LOGIC>", 1)[0].strip()
        if len(content) > 300:
            content = content[:300] + "…"
        lines.append(f"{role}: {content}")
    return "\n\nPRIOR CONVERSATION (for continuity):\n" + "\n".join(lines)


async def _auto_name_thread(session_id: str, first_question: str):
    """Fire-and-forget: ask Claude to generate a 2-4 word title. Update thread name."""
    try:
        title = ""
        async with anthropic_client.messages.stream(
            model=CLAUDE_TITLE_MODEL,
            max_tokens=30,
            system="Give a very short 2-5 word title for a conversation that starts with the following question. Reply with ONLY the title text, no quotes, no punctuation at the end.",
            messages=[{"role": "user", "content": first_question.strip()[:400]}],
        ) as stream:
            async for text_delta in stream.text_stream:
                title += text_delta
        title = (title or "").strip().strip('"').strip("'").split("\n")[0][:60]
        if title:
            await db.threads.update_one({"id": session_id}, {"$set": {"name": title, "updated_at": datetime.now(timezone.utc).isoformat()}})
    except Exception as e:
        logging.exception("auto-name failed: %s", e)


@api_router.post("/chat")
async def chat_stream(req: ChatRequest, user: User = Depends(get_current_user)):
    prof = await db.profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    if not prof:
        raise HTTPException(404, "Set up your birth details first")

    # Ownership check for thread
    thread = await db.threads.find_one({"id": req.session_id, "user_id": user.user_id}, {"_id": 0})
    if not thread:
        raise HTTPException(404, "Thread not found")

    chart = compute_chart(prof['dob'], prof['tob'], prof['tz_offset'], prof['lat'], prof['lon'])
    chart['profile'] = {'name': prof['name'], 'dob': prof['dob'], 'tob': prof['tob'], 'place': prof['place']}
    chart['current_dasha'] = current_dasha(chart['dashas'])
    if chart['current_dasha']:
        chart['current_antardasha'] = current_antardasha(chart['current_dasha'])
    transits = current_transits(chart)

    # Per-message book scoping (NEVER sticks past this message)
    books_avail = await list_books_for_user(db, user.user_id)
    book_names = [b["book"] for b in books_avail["seed"]] + [b["book"] for b in books_avail["custom"]]
    scoped = detect_book_scope(req.message, book_names)
    retrieved = await search_for_user(db, user.user_id, req.message, k=8, book_names=scoped)

    context_block = _build_context(chart, transits, retrieved)

    # Load prior conversation for memory
    prior = await db.messages.find(
        {"session_id": req.session_id, "role": {"$in": ["user", "assistant"]}},
        {"_id": 0}
    ).sort("created_at", 1).to_list(50)
    memory_block = _summarize_prior_messages(prior)

    # Persist user message
    is_first_user_msg = not any(m["role"] == "user" for m in prior)
    await db.messages.insert_one({
        "session_id": req.session_id,
        "user_id": user.user_id,
        "role": "user",
        "content": req.message,
        "attachment_urls": req.attachment_urls or [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    system_message = SYSTEM_PROMPT + "\n\n" + context_block + memory_block
    if scoped:
        system_message += f"\n\nBOOK SCOPE FOR THIS ANSWER ONLY: The user requested you draw exclusively from: {', '.join(scoped)}. Only cite excerpts from these books.\n"

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
        {"idx": i + 1, "book": r["book"], "chapter": r["chapter"], "text": r["text"],
         "is_seed": r.get("is_seed", True), "score": round(r.get("score", 0), 3)}
        for i, r in enumerate(retrieved)
    ]

    async def event_generator():
        yield f"event: citations\ndata: {json.dumps(citations_payload)}\n\n"
        if scoped:
            yield f"event: scope\ndata: {json.dumps({'books': list(scoped)})}\n\n"
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

        answer_only = full
        logic_only = ""
        if "<LOGIC>" in full:
            parts = full.split("<LOGIC>", 1)
            answer_only = parts[0].strip()
            logic_only = parts[1].split("</LOGIC>", 1)[0].strip() if "</LOGIC>" in parts[1] else parts[1].strip()

        # Persist AND schedule auto-name under shield so client-disconnect
        # (user navigates away mid-stream) doesn't drop the assistant reply.
        async def _persist():
            await db.messages.insert_one({
                "session_id": req.session_id,
                "user_id": user.user_id,
                "role": "assistant",
                "content": full,
                "answer": answer_only,
                "logic": logic_only,
                "citations": citations_payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            await db.threads.update_one({"id": req.session_id}, {"$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
            if is_first_user_msg and re.match(r"^(new chat|chat \d+|general)$", (thread.get("name") or "").strip(), re.IGNORECASE):
                asyncio.create_task(_auto_name_thread(req.session_id, req.message))

        await asyncio.shield(_persist())

        yield f"event: done\ndata: {json.dumps({'ok': True})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "close"},
    )


@api_router.get("/chat/{session_id}/history")
async def chat_history(session_id: str, user: User = Depends(get_current_user)):
    thread = await db.threads.find_one({"id": session_id, "user_id": user.user_id}, {"_id": 0})
    if not thread:
        raise HTTPException(404, "Thread not found")
    msgs = await db.messages.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(200)
    return {"messages": msgs}


# ---------- Threads ----------
@api_router.get("/threads")
async def list_threads(user: User = Depends(get_current_user)):
    docs = await db.threads.find({"user_id": user.user_id}, {"_id": 0}).sort("updated_at", -1).to_list(100)
    return {"threads": docs}


@api_router.post("/threads")
async def create_thread(payload: ThreadCreate, user: User = Depends(get_current_user)):
    thread = {
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "name": payload.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.threads.insert_one({**thread})
    return thread


@api_router.patch("/threads/{thread_id}")
async def rename_thread(thread_id: str, payload: ThreadRename, user: User = Depends(get_current_user)):
    res = await db.threads.update_one(
        {"id": thread_id, "user_id": user.user_id},
        {"$set": {"name": payload.name, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if not res.matched_count:
        raise HTTPException(404, "Thread not found")
    return {"ok": True}


@api_router.delete("/threads/{thread_id}")
async def delete_thread(thread_id: str, user: User = Depends(get_current_user)):
    res = await db.threads.delete_one({"id": thread_id, "user_id": user.user_id})
    if not res.deleted_count:
        raise HTTPException(404, "Thread not found")
    await db.messages.delete_many({"session_id": thread_id})
    return {"ok": True}


# ---------- Attachments ----------
@api_router.post("/chat/attachment")
async def upload_attachment(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(400, "Only JPG/PNG/WEBP images are supported")
    fname = f"{user.user_id}_{uuid.uuid4().hex}{ext}"
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


# ---------- Geocoding (public) ----------
@api_router.get("/geocode")
async def geocode(q: str):
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent="compass-astro")
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
