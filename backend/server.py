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
import secrets
import asyncio
import httpx
import bcrypt
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, BeforeValidator
from typing import List, Optional, Annotated, Any
from datetime import datetime, timezone, timedelta
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from astrology import (
    compute_chart, current_transits, current_dasha, current_antardasha,
    compute_antardashas, build_navamsa, build_dasamsa,
    build_varga, EXTRA_VARGAS, sun_rise_set, sun_moon_longitudes,
    current_utc_offset_hours, estimate_tob_from_sunrise_period,
    find_upcoming_stations, ashtakavarga_transit_strength, find_sign_ingress,
    DOMAIN_SIGNIFICATORS, compute_domain_verdict,
)
from chartcard import generate_chart_card_pdf, generate_chart_card_png
from muhurta import find_best_windows, ACTIVITY_HOUSES, detect_activity_intent
from panchang import compute_panchang, compute_daily_muhurta
_KNOWLEDGE_SOURCE = os.environ.get('KNOWLEDGE_SOURCE', 'original')
if _KNOWLEDGE_SOURCE == 'v2':
    from knowledge_v2 import (
        SEED_CORPUS, search_for_user, list_books_for_user, add_pdf_for_user,
        delete_book_for_user, detect_book_scope,
    )
elif _KNOWLEDGE_SOURCE == 'v1':
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
GOOGLE_CLIENT_ID = os.environ['GOOGLE_CLIENT_ID']
RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
RESEND_FROM_EMAIL = os.environ.get('RESEND_FROM_EMAIL', 'Compass Astro <onboarding@resend.dev>')
# Where contact-form submissions land. Set CONTACT_TO_EMAIL in Render's env
# vars once you have a domain email — no code change needed to update it.
CONTACT_TO_EMAIL = os.environ.get('CONTACT_TO_EMAIL', 'daveastroanalyst@gmail.com')
ADMIN_SECRET = os.environ.get('ADMIN_SECRET')  # required to call /admin/set-plan

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
    plan: str = "basic"  # "basic" | "standard" | "advanced" — no billing yet, so
    # this only ever changes via /admin/set-plan until checkout exists.
    language: str = "en"  # ISO 639-1 code. Drives both the UI locale (frontend
    # reads this to pick a translation file) and the chat system prompt (see
    # LANGUAGE_NAMES / chat_stream below) — one setting, two effects, since
    # someone who wants a Gujarati interface almost certainly wants Gujarati
    # chat replies by default too. They can still just ask in a different
    # language mid-chat and Claude will follow that instead.
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    language: Optional[str] = None


class AdminPlanUpdate(BaseModel):
    email: str
    plan: str  # "basic" | "standard" | "advanced"


class LocationUpdate(BaseModel):
    lat: float
    lon: float
    place: str


class GoogleAuthRequest(BaseModel):
    credential: str  # Google Identity Services ID token (JWT), verified against Google's own public keys


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


class ResendCodeRequest(BaseModel):
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


class ContactRequest(BaseModel):
    name: str
    email: str
    message: str


class WaitlistRequest(BaseModel):
    email: str
    tier: str


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


# ---------- Auth helpers (shared by Google + email/password flows) ----------
def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def _send_verification_email(to_email: str, code: str, name: str = "") -> None:
    """Send a 6-digit signup verification code via Resend. If RESEND_API_KEY
    isn't configured yet, log the code instead of failing outright, so local/
    early testing isn't blocked on having the email provider wired up."""
    if not RESEND_API_KEY:
        logging.warning("RESEND_API_KEY not set — verification code for %s is %s", to_email, code)
        return
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": "Your Compass Astro verification code",
                "html": (
                    f"<p>Hi{f' {name}' if name else ''},</p>"
                    f"<p>Your Compass Astro verification code is:</p>"
                    f"<h2 style='letter-spacing:4px'>{code}</h2>"
                    f"<p>This code expires in 10 minutes. If you didn't request this, you can ignore this email.</p>"
                ),
            },
        )
    if r.status_code >= 400:
        logging.error("Resend send failed (%s): %s", r.status_code, r.text)
        raise HTTPException(status_code=502, detail="Could not send verification email. Please try again.")


async def _send_password_reset_email(to_email: str, code: str, name: str = "", has_password: bool = True) -> None:
    """Send a 6-digit password reset/set code via Resend. Copy is worded
    slightly differently for accounts that don't have a password yet (i.e.
    Google-only accounts using this flow to add one) vs. a genuine reset."""
    if not RESEND_API_KEY:
        logging.warning("RESEND_API_KEY not set — password reset code for %s is %s", to_email, code)
        return
    action_word = "reset" if has_password else "set"
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": f"{action_word.capitalize()} your Compass Astro password",
                "html": (
                    f"<p>Hi{f' {name}' if name else ''},</p>"
                    f"<p>Use this code to {action_word} your Compass Astro password:</p>"
                    f"<h2 style='letter-spacing:4px'>{code}</h2>"
                    f"<p>This code expires in 15 minutes. If you didn't request this, you can ignore this email — your account is unaffected.</p>"
                ),
            },
        )
    if r.status_code >= 400:
        logging.error("Resend send failed (%s): %s", r.status_code, r.text)
        raise HTTPException(status_code=502, detail="Could not send the password reset email. Please try again.")


async def _send_contact_email(name: str, from_email: str, message: str) -> None:
    """Send a contact-form submission to CONTACT_TO_EMAIL via Resend, with
    reply-to set to the submitter so a reply goes straight to them. Falls
    back to logging (not failing) if RESEND_API_KEY isn't set, matching the
    pattern used for verification/reset emails."""
    if not RESEND_API_KEY:
        logging.warning("RESEND_API_KEY not set — contact message from %s (%s): %s", name, from_email, message)
        return
    async with httpx.AsyncClient(timeout=15) as h:
        r = await h.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": RESEND_FROM_EMAIL,
                "to": [CONTACT_TO_EMAIL],
                "reply_to": from_email,
                "subject": f"Compass Astro contact — {name}",
                "html": (
                    f"<p><strong>From:</strong> {name} ({from_email})</p>"
                    f"<p>{message}</p>"
                ),
            },
        )
    if r.status_code >= 400:
        logging.error("Resend send failed (%s): %s", r.status_code, r.text)
        raise HTTPException(status_code=502, detail="Could not send your message. Please try again shortly.")


async def _find_or_create_user(email: str, name: str, picture: Optional[str] = None) -> str:
    """Find-or-create by email — the same identity rule the old Emergent flow
    used, so existing Google users are matched to their existing account with
    no migration needed."""
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        updates = {}
        if name and name != existing.get("name"):
            updates["name"] = name
        if picture and picture != existing.get("picture"):
            updates["picture"] = picture
        if updates:
            await db.users.update_one({"user_id": user_id}, {"$set": updates})
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id, "email": email, "name": name, "picture": picture,
            "plan": "basic",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    return user_id


async def _create_session(user_id: str, response: Response, remember_me: bool = False) -> str:
    """Mint our own opaque session token (previously supplied by Emergent) and
    set it as an httpOnly cookie. `remember_me` extends the session from the
    usual 7 days to 30."""
    session_token = secrets.token_urlsafe(32)
    days = 30 if remember_me else 7
    expires_at = datetime.now(timezone.utc) + timedelta(days=days)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    response.set_cookie(
        key="session_token", value=session_token, httponly=True, secure=True,
        samesite="none", path="/", max_age=days * 24 * 3600,
    )
    return session_token


# ---------- Domain models ----------
class BirthProfileCreate(BaseModel):
    name: str
    dob: str
    tob: Optional[str] = None
    tz_offset: float
    lat: float
    lon: float
    place: str
    # If the user isn't sure of their exact birth time, tob is estimated
    # server-side from the classical before/after-sunrise distinction
    # instead — tob_period is required in that case.
    tob_unknown: bool = False
    tob_period: Optional[str] = None  # "before_sunrise" | "after_sunrise"


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
    tob_unknown: bool = False
    tob_period: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatRequest(BaseModel):
    session_id: str
    message: str
    attachment_urls: Optional[List[str]] = None


class ThreadCreate(BaseModel):
    name: str = "New chat"
    project_key: Optional[str] = None


class ThreadRename(BaseModel):
    name: str


class CustomProjectCreate(BaseModel):
    name: str


class DashaSubdivideRequest(BaseModel):
    lord: str
    start: str
    years: float


class MuhurtaAskRequest(BaseModel):
    message: str


# ---------- Routes ----------
@api_router.get("/")
async def root():
    return {"message": "Compass Astro is listening. Ask the stars."}


# ---------- Auth endpoints ----------
@api_router.post("/auth/google")
async def google_auth(payload: GoogleAuthRequest, response: Response):
    """Verify a Google Identity Services ID token directly against Google's
    public keys — no third-party auth proxy involved. Same find-or-create-by-
    email + session creation as every other login path below."""
    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.credential, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google credential")

    email = idinfo.get("email")
    if not email or not idinfo.get("email_verified", False):
        raise HTTPException(status_code=401, detail="Google account email is not verified")
    email = email.strip().lower()
    name = idinfo.get("name") or email.split("@")[0]
    picture = idinfo.get("picture")

    user_id = await _find_or_create_user(email, name, picture)
    session_token = await _create_session(user_id, response)
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {**user_doc, "session_token": session_token}


@api_router.post("/auth/signup")
async def signup(payload: SignupRequest):
    """Start email/password signup. Nothing permanent is created yet — the
    email + hashed password sit in `pending_signups` until the 6-digit code
    is confirmed via /auth/verify, so an unclaimed email never occupies a
    real account."""
    email = payload.email.strip().lower()
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists. Try signing in instead.")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    code = _generate_verification_code()
    await db.pending_signups.update_one(
        {"email": email},
        {"$set": {
            "email": email,
            "name": payload.name.strip() or email.split("@")[0],
            "password_hash": _hash_password(payload.password),
            "code": code,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    await _send_verification_email(email, code, payload.name)
    return {"ok": True, "email": email}


@api_router.post("/auth/resend-code")
async def resend_code(payload: ResendCodeRequest):
    email = payload.email.strip().lower()
    pending = await db.pending_signups.find_one({"email": email}, {"_id": 0})
    if not pending:
        raise HTTPException(status_code=404, detail="No pending signup found for this email.")
    code = _generate_verification_code()
    await db.pending_signups.update_one(
        {"email": email},
        {"$set": {"code": code, "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}},
    )
    await _send_verification_email(email, code, pending.get("name", ""))
    return {"ok": True}


@api_router.post("/auth/verify")
async def verify_signup(payload: VerifyCodeRequest, response: Response):
    """Confirm the emailed code and turn a pending signup into a real account."""
    email = payload.email.strip().lower()
    pending = await db.pending_signups.find_one({"email": email}, {"_id": 0})
    if not pending:
        raise HTTPException(status_code=404, detail="No pending signup found for this email. Please sign up again.")

    expires_at = pending.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This code has expired. Request a new one.")

    if payload.code.strip() != pending["code"]:
        raise HTTPException(status_code=400, detail="Incorrect code.")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]  # race-condition guard: account already exists somehow
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": pending["name"],
            "picture": None,
            "password_hash": pending["password_hash"],
            "plan": "basic",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    await db.pending_signups.delete_one({"email": email})
    session_token = await _create_session(user_id, response)
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return {**user_doc, "session_token": session_token}


@api_router.post("/auth/login")
async def login(payload: LoginRequest, response: Response):
    email = payload.email.strip().lower()
    user_doc = await db.users.find_one({"email": email}, {"_id": 0})
    if not user_doc or not user_doc.get("password_hash"):
        raise HTTPException(status_code=401, detail="No password-based account found for this email. Try Google sign-in instead.")
    if not _verify_password(payload.password, user_doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    session_token = await _create_session(user_doc["user_id"], response, remember_me=payload.remember_me)
    user_doc.pop("password_hash", None)
    return {**user_doc, "session_token": session_token}


@api_router.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    """Start a password reset. This also doubles as 'set a password' for
    accounts that only have Google sign-in — the code and reset step are
    identical either way, only the email copy changes. Always returns {"ok":
    true} regardless of whether the email is registered, so this endpoint
    can't be used to probe which emails have accounts."""
    email = payload.email.strip().lower()
    user_doc = await db.users.find_one({"email": email}, {"_id": 0})
    if user_doc:
        code = _generate_verification_code()
        await db.password_resets.update_one(
            {"email": email},
            {"$set": {
                "email": email,
                "code": code,
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
        await _send_password_reset_email(
            email, code, user_doc.get("name", ""), has_password=bool(user_doc.get("password_hash"))
        )
    return {"ok": True}


@api_router.post("/auth/reset-password")
async def reset_password(payload: ResetPasswordRequest, response: Response):
    """Confirm the emailed code and set the account's password — whether
    that's a genuine reset or the first password a Google-only account has
    ever had. Logs the user in immediately afterward, same as /auth/verify."""
    email = payload.email.strip().lower()
    reset_doc = await db.password_resets.find_one({"email": email}, {"_id": 0})
    if not reset_doc:
        raise HTTPException(status_code=404, detail="No password reset requested for this email. Please request a new code.")

    expires_at = reset_doc.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This code has expired. Request a new one.")

    if payload.code.strip() != reset_doc["code"]:
        raise HTTPException(status_code=400, detail="Incorrect code.")

    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    user_doc = await db.users.find_one({"email": email}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="No account found for this email.")

    update_result = await db.users.update_one(
        {"user_id": user_doc["user_id"]},
        {"$set": {"password_hash": _hash_password(payload.new_password)}},
    )
    if update_result.matched_count == 0:
        logging.error(
            "reset-password: update matched 0 documents for user_id=%s email=%s — password NOT saved",
            user_doc["user_id"], email,
        )
        raise HTTPException(status_code=500, detail="Could not save your new password. Please try again or contact support.")

    # Verify the write actually took, rather than trusting update_one's report —
    # a previous version of this endpoint created the session regardless of
    # whether the password was really saved, which silently masked failures.
    verify_doc = await db.users.find_one({"user_id": user_doc["user_id"]}, {"_id": 0, "password_hash": 1})
    if not verify_doc or not verify_doc.get("password_hash"):
        logging.error(
            "reset-password: password_hash still missing after update for user_id=%s email=%s",
            user_doc["user_id"], email,
        )
        raise HTTPException(status_code=500, detail="Could not save your new password. Please try again or contact support.")

    await db.password_resets.delete_one({"email": email})

    session_token = await _create_session(user_doc["user_id"], response)
    user_doc.pop("password_hash", None)
    return {**user_doc, "session_token": session_token}


@api_router.get("/auth/me", response_model=User)
async def me(user: User = Depends(get_current_user)):
    return user


@api_router.post("/admin/set-plan")
async def admin_set_plan(payload: AdminPlanUpdate, x_admin_secret: Optional[str] = Header(default=None)):
    """Manually sets a user's plan. There's no billing/checkout yet, so this
    is the only way a plan ever changes — gate it behind ADMIN_SECRET (set
    on Render) rather than building a full admin panel before there's
    anything for it to actually manage. Call it yourself with curl:
        curl -X POST https://<backend>/api/admin/set-plan \\
             -H "X-Admin-Secret: <ADMIN_SECRET>" \\
             -H "Content-Type: application/json" \\
             -d '{"email":"you@example.com","plan":"advanced"}'
    """
    if not ADMIN_SECRET or x_admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Not authorized")
    if payload.plan not in ("basic", "standard", "advanced"):
        raise HTTPException(status_code=400, detail="plan must be basic, standard, or advanced")
    email = payload.email.strip().lower()
    res = await db.users.update_one({"email": email}, {"$set": {"plan": payload.plan}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="No user with that email")
    return {"ok": True, "email": email, "plan": payload.plan}


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
    data = payload.model_dump()
    if data.get("tob_unknown"):
        if data.get("tob_period") not in ("before_sunrise", "after_sunrise"):
            raise HTTPException(400, "Choose whether you were born before or after sunrise.")
        data["tob"] = estimate_tob_from_sunrise_period(
            data["dob"], data["tz_offset"], data["lat"], data["lon"], data["tob_period"]
        )
    elif not data.get("tob"):
        raise HTTPException(400, "Time of birth is required, or mark it as unknown.")

    existing = await db.profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    if existing:
        update = {**data}
        await db.profiles.update_one({"user_id": user.user_id}, {"$set": update})
        merged = {**existing, **update}
        if isinstance(merged.get('created_at'), str):
            merged['created_at'] = datetime.fromisoformat(merged['created_at'])
        return BirthProfile(**merged)
    profile = BirthProfile(user_id=user.user_id, **data)
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
        chart['current_pratyantardasha'] = (
            current_antardasha(chart['current_antardasha']) if chart['current_antardasha'] else None
        )
    else:
        chart['antardashas'] = []
        chart['current_antardasha'] = None
        chart['current_pratyantardasha'] = None
    chart['navamsa'] = build_navamsa(chart['planets'], chart['ascendant']['longitude'])
    chart['dasamsa'] = build_dasamsa(chart['planets'], chart['ascendant']['longitude'])
    # D2/D4/D6/D7/D16/D24/D60 — Advanced-mode-only divisional charts. Built
    # from the same natal planets, one per entry in EXTRA_VARGAS.
    chart['extra_vargas'] = {
        key: {
            **build_varga(chart['planets'], chart['ascendant']['longitude'], sign_fn),
            'label': label,
        }
        for key, (sign_fn, label) in EXTRA_VARGAS.items()
    }
    chart['profile'] = {
        'name': doc['name'], 'dob': doc['dob'], 'tob': doc['tob'], 'place': doc['place'],
        'tob_unknown': doc.get('tob_unknown', False), 'tob_period': doc.get('tob_period'),
    }
    return chart


async def _chart_card_about_lines(chart: dict, name: str) -> List[str]:
    """Seven short lines describing the chart in plain language, for the
    card — covering characteristics, life approach, likely professional
    direction, and health tendencies, alongside temperament and strengths.
    Deliberately framed as what the classical texts say about these
    configurations rather than flat assertions about the person — it's more
    honest, and it's the framing the rest of the product already uses."""
    asc = chart["ascendant"]
    by_name = {p["name"]: p for p in chart["planets"]}
    moon = by_name.get("Moon", {})
    house_lords = chart.get("house_lords") or []
    lord_by_house = {hl.get("house"): hl for hl in house_lords}

    facts = [
        f"Lagna: {asc.get('sign_en')} (lord {asc.get('lord')})",
        f"Moon: {moon.get('sign_en')} in {moon.get('nakshatra')} pada {moon.get('pada')}",
    ]
    tenth = lord_by_house.get(10)
    if tenth:
        facts.append(
            f"10th house (career/profession) lord {tenth.get('lord')} sits in "
            f"{tenth.get('lord_sits_in_sign_en')} (house {tenth.get('lord_sits_in_house')})"
        )
    sixth = lord_by_house.get(6)
    if sixth:
        facts.append(
            f"6th house (health/daily discipline) lord {sixth.get('lord')} sits in "
            f"{sixth.get('lord_sits_in_sign_en')} (house {sixth.get('lord_sits_in_house')})"
        )
    for p in chart["planets"]:
        tags = p.get("dignity") or []
        if tags:
            facts.append(f"{p['name']} in {p.get('sign_en')} (house {p.get('house')}) — {', '.join(tags)}")
    for yg in (chart.get("yogas") or [])[:3]:
        facts.append(f"Yoga: {yg.get('name')} — {yg.get('detail')}")

    prompt = (
        "You are writing 7 short lines for a one-page birth-chart card that "
        "someone will show to friends or hand to an astrologer.\n\n"
        "Chart facts:\n- " + "\n- ".join(facts[:16]) + "\n\n"
        "Write exactly 7 lines, each covering a DIFFERENT one of these "
        "angles (in roughly this order, one line per angle, skip an angle "
        "only if the facts truly don't support it):\n"
        "1. Core personality/characteristics (from the Lagna and its lord)\n"
        "2. Emotional nature and inner life (from the Moon)\n"
        "3. General life approach or temperament\n"
        "4. Likely professional direction or working style (from the 10th "
        "house lord's placement)\n"
        "5. Health tendencies or constitution (from the 6th house lord's "
        "placement) — general constitution only, never diagnostic or "
        "alarming\n"
        "6. A natural strength (from a yoga or a well-placed/dignified "
        "planet)\n"
        "7. Where the chart suggests friction or a growth edge\n\n"
        "Each line must be under 110 characters, a complete sentence, and "
        "reference a real placement from the facts above. Be specific and "
        "warm, never generic or flattering. Do not predict events, give "
        "medical advice, or make diagnostic claims.\n\n"
        "Respond with ONLY a JSON array of 7 strings, no other text."
    )
    try:
        resp = await anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        arr = json.loads(text)
        if isinstance(arr, list):
            return [str(s).strip() for s in arr[:7] if str(s).strip()]
    except Exception:
        pass
    # Deterministic fallback so the card never renders with an empty section.
    return [
        f"{asc.get('sign_en')} Lagna, ruled by {asc.get('lord')} — the lens the whole chart is read through.",
        f"Moon in {moon.get('sign_en')}, {moon.get('nakshatra')} pada {moon.get('pada')} — the classical seat of the mind.",
    ]


@api_router.get("/profile/share-card")
async def profile_share_card(format: str = "png", user: User = Depends(get_current_user)):
    """One-page birth-chart card — D1 + D9 charts, full planetary table,
    Shadbala strengths, yogas, Ashtakavarga and a short written summary.

    Access is gated on the frontend's Simple/Advanced view toggle, not an
    account plan, so this endpoint itself is open to any authenticated user
    — the same as every other chart-data endpoint. (The `plan` field on
    User and /admin/set-plan are left in place for whenever real billing
    exists; nothing currently reads `plan` to restrict this feature.)

    Defaults to PNG so it saves to the camera roll and shares like a photo.
    The layout is drawn as vector and only rasterized at the last step, so
    it stays sharp — unlike the old card, which was drawn straight to a
    low-resolution bitmap. `?format=pdf` returns the vector original, which
    is the better choice for printing or emailing to an astrologer."""
    doc = await db.profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Set up your birth details first")

    chart = compute_chart(doc['dob'], doc['tob'], doc['tz_offset'], doc['lat'], doc['lon'])
    navamsa = build_navamsa(chart['planets'], chart['ascendant']['longitude'])

    md = current_dasha(chart['dashas'])
    dasha_parts = []
    if md:
        dasha_parts.append(f"{md['lord']} Mahadasha ({str(md.get('start'))[:10]} to {str(md.get('end'))[:10]})")
        ad = current_antardasha(md)
        if ad:
            dasha_parts.append(f"{ad['lord']} Antardasha until {str(ad.get('end'))[:10]}")
            pd = current_antardasha(ad)
            if pd:
                dasha_parts.append(f"{pd['lord']} Pratyantardasha")
    dasha_line = "  \u00b7  ".join(dasha_parts) if dasha_parts else "\u2014"

    tob_txt = doc.get('tob') or "time unknown"
    if doc.get('tob_unknown'):
        tob_txt += " (approx.)"
    place = doc.get('place', '')
    if place.count(",") > 2:
        parts = [p.strip() for p in place.split(",") if p.strip() and not p.strip().isdigit()]
        place = ", ".join(parts[-3:])
    birth_line = f"{doc.get('dob', '')}  \u00b7  {tob_txt}  \u00b7  {place}"

    about_lines = await _chart_card_about_lines(chart, doc['name'])

    card_kwargs = dict(
        name=doc['name'],
        birth_line=birth_line,
        chart=chart,
        navamsa=navamsa,
        dasha_line=dasha_line,
        about_lines=about_lines,
    )
    base_name = f"{doc['name'].replace(' ', '-')}-compass-astro-chart"

    if format.lower() == "pdf":
        return Response(
            content=generate_chart_card_pdf(**card_kwargs),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{base_name}.pdf"'},
        )
    return Response(
        content=generate_chart_card_png(**card_kwargs),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{base_name}.png"'},
    )


@api_router.get("/transits")
async def get_transits(user: User = Depends(get_current_user)):
    doc = await db.profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    natal = None
    if doc:
        natal = compute_chart(doc['dob'], doc['tob'], doc['tz_offset'], doc['lat'], doc['lon'])
    return current_transits(natal)


@api_router.post("/dasha/subdivide")
async def subdivide_dasha(payload: DashaSubdivideRequest, user: User = Depends(get_current_user)):
    """Given any dasha period (Mahadasha, Antardasha, or Pratyantardasha), return
    its 9 sub-periods one level deeper. The subdivision math is identical at every
    level of the Vimshottari system, so this single endpoint serves the whole
    Maha → Antar → Pratyantar → Sookshma drill-down."""
    subs = compute_antardashas({"lord": payload.lord, "start": payload.start, "years": payload.years})
    return {"subs": subs}


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
    if not result.get("chunks_added"):
        # This is the real, honest failure mode: the PDF parsed without error but
        # yielded no extractable text — almost always a scanned/image-only PDF,
        # which our text extraction can't read (no OCR). Silently "succeeding"
        # with 0 chunks and no visible book is confusing; a clear error is better.
        raise HTTPException(
            400,
            "No readable text found in this PDF. This usually means it's a scanned "
            "or image-based PDF rather than a text PDF — try a different file, or a "
            "text-searchable version of this one."
        )
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


@api_router.get("/yogas/citations")
async def yoga_citations(name: str, user: User = Depends(get_current_user)):
    """Yogas are detected algorithmically (see astrology.py) with no source
    field attached — the Yogas panel showed a name and a plain-language
    explanation with nothing behind it. This looks the yoga name up against
    the same classical-text search the chat's Why panel already uses, so
    the frontend can show the same citation UI here too."""
    results = await search_for_user(db, user.user_id, name, k=3)
    citations = [
        {"idx": i + 1, "book": r["book"], "chapter": r.get("chapter", ""), "text": r["text"]}
        for i, r in enumerate(results)
    ]
    return {"citations": citations}


# ---------- Projects (life-area chat scopes) ----------
# A fixed set rather than free-form user-created projects — keeps the chart
# lens mapping (which houses/varga charts to foreground) well-defined and
# classically grounded instead of guessed per user-typed label. Custom
# (user-created) projects are layered on top in the /projects endpoints below.
# ---------- Languages ----------
# ISO 639-1 code -> the name Claude should be told to respond in. Tier 1 is
# closest to the core audience (Indic languages), Tier 2 is nearby South
# Asian markets, Tier 3 is broader global reach. Adding a language here does
# NOT require a code change anywhere else in this file — chat_stream just
# looks up user.language against this dict.
LANGUAGES = {
    "en": "English",
    # Tier 1 — Indic
    "hi": "Hindi", "gu": "Gujarati", "mr": "Marathi", "ta": "Tamil",
    "te": "Telugu", "kn": "Kannada", "bn": "Bengali", "pa": "Punjabi",
    # Tier 2 — nearby South Asian
    "ur": "Urdu", "ne": "Nepali", "si": "Sinhala",
    # Tier 3 — broader global
    "es": "Spanish", "pt": "Portuguese", "fr": "French", "id": "Indonesian",
}


PROJECTS = {
    "marriage": {
        "label": "Marriage & Relationships",
        "lens": (
            "Foreground the 7th house (marriage/partnership) and its lord, "
            "Venus and Jupiter's condition, and the Navamsa (D9) chart — the "
            "classical chart of marriage. Note the 7th lord's dasha/antardasha "
            "windows and any transits touching the 7th house or its lord."
        ),
    },
    "career": {
        "label": "Career & Job",
        "lens": (
            "Foreground the 10th house (career) and 6th house (service/job), "
            "their lords, and the Dasamsa (D10) chart — the classical chart "
            "of profession. Note the 10th lord's dasha/antardasha and any "
            "transits touching the 10th house."
        ),
    },
    "business": {
        "label": "Business",
        "lens": (
            "Foreground the 10th house (profession), 3rd house (initiative/"
            "self-effort) and 11th house (gains), plus the Dasamsa (D10) "
            "chart. Weigh the dasha/antardasha of these house lords and any "
            "transits touching them."
        ),
    },
    "finance": {
        "label": "Finance & Wealth",
        "lens": (
            "Foreground the 2nd house (accumulated wealth) and 11th house "
            "(income/gains), their lords, and any yogas involving them. Note "
            "dasha/antardasha and transits touching these houses."
        ),
    },
    "family": {
        "label": "Family & Home",
        "lens": (
            "Foreground the 4th house (home, mother, domestic peace) and "
            "2nd house (family), their lords, and the Moon's condition. Note "
            "dasha/antardasha and transits touching the 4th house."
        ),
    },
    "mental_health": {
        "label": "Mental Health",
        "lens": (
            "Foreground the Moon's condition (the mind), the 6th house "
            "(struggles) and 12th house (isolation/rest), and any afflictions "
            "from Saturn, Rahu or Ketu. Note dasha/antardasha and transits "
            "affecting the Moon or these houses."
        ),
    },
}


# ---------- Chat (with per-message book scoping, auto-name, memory) ----------
SYSTEM_PROMPT = """You are Compass Astro — a warm, calm Vedic astrology guide. You speak like a wise friend, not a scholar.

## HARD RULES FOR THE ANSWER YOU SHOW THE USER
1. Everyday, plain English. Assume the user has ZERO astrology knowledge.
2. NO jargon in the visible answer. Never use these words in the main reply: nakshatra, retrograde, house (as in 10th house), dasha, antardasha, lagna, ascendant, graha, kendra, trikona, moolatrikona, vargottama, sign lord, planet lord, transit, aspect, degree, exalted, debilitated, ayanamsa. Translate them to natural language ("this phase of your life", "your career area", "the friend/planet guiding you now", "an important shift").
3. Length: 350–450 words. Short paragraphs, no headers, minimal bullets.
4. Direct answer to the question first. Then 2–4 sentences of grounded insight.
5. A practical suggestion or remedy is OPTIONAL, not automatic. Only include one if the chart genuinely points to a real challenge, imbalance, or something actionable (in plain words, e.g. "chant on Tuesday mornings" instead of "Mangal beej mantra"). If the question is neutral, informational, or the placement is already strong, end on the insight — do not manufacture a remedy just to have one. Never include a remedy in more than roughly half of your replies across a conversation; if you notice you've given one recently, lean toward skipping it this time unless clearly warranted.
6. Avoid repeating the same planet or dasha-lord's name more than necessary within a short span of text — refer back with "it", "this planet", or similar once you've named it, rather than restating the name every sentence.
7. Never mention "as per BPHS [1]", "shastra", "citations", or reference numbers to the user. That reasoning lives ONLY in the LOGIC block below.
8. If the context below includes a "CALCULATED MUHURTA WINDOWS" section, use those exact date ranges as your recommended timing — do not compute or invent different dates yourself. If that section is absent, answer timing questions from the chart context as you already do.
9. If the context below includes an "UPCOMING RETROGRADE/DIRECT STATIONS" section, you MUST use those exact dates for any question about when a planet will turn retrograde or direct — this overrides anything you think you remember about typical retrograde timing. Your training data does not contain reliable future ephemeris dates; the section below does. Never estimate, recall from memory, or guess a date yourself when this section is present — copy the date directly. If asked about a planet not listed there (Sun, Moon, Rahu, Ketu, or one outside the computed window), say plainly that you don't have a computed date for that rather than guessing one.
10. If the context below includes a "COMPUTED [DOMAIN] ASSESSMENT" section, treat its verdict and five signals as the analysis to explain, not raw material to independently re-derive. Weave the strong/weak signals into your answer in plain language (e.g. a "strong convergence" with dasha alignment true becomes "this is a genuinely active period for this" — never say "convergence" or "signals" to the user). If your own reading of the chart disagrees with a specific signal, say so explicitly in the LOGIC block rather than silently contradicting it in the visible answer.
11. If the context below includes "KNOWN ABOUT THIS PERSON" or "PAST PREDICTION OUTCOMES", weave these in naturally where relevant (e.g. "since you started that new role..." rather than re-asking what they already told you) — but don't force a reference to them into every answer, and never recite them back as a list. If a past prediction was confirmed wrong, don't repeat the same claim.

## SAFETY RULES (apply regardless of what the chart shows or what the user asks)
12. Compass, not a verdict — always. Never state or imply a specific illness, diagnosis, cause of death, or death timing for the user or anyone else, no matter what the placements suggest. Classical texts describe tendencies and phases, not medical or forensic facts, and you must not translate them into either. If a chart factor traditionally relates to health or longevity, speak only in terms of general themes to stay mindful of (e.g. "a period worth paying attention to your energy and rest") — never a named condition, a timeframe for death, or comparable absolute claims about illness, accident, or a person's fate.
13. Never give medical, legal, or financial advice, or make investment/legal recommendations. If asked directly, say plainly that you can offer astrological perspective on timing and themes, not professional advice, and suggest they consult a qualified doctor, lawyer, or financial advisor for the actual decision.
14. Reframe toward agency and timing rather than fatalism: prefer "this is a period that may call for care/patience/caution" over "X will happen." The user should leave with a sense of what to pay attention to and when, never a fixed prophecy.
15. If a message expresses suicidal thoughts, self-harm, intent to harm someone else, or a mental health crisis, do NOT provide a chart reading in response. Respond with warmth, take it seriously, and point them to crisis support (e.g. in the US: 988 Suicide & Crisis Lifeline, call or text 988; outside the US: encourage contacting a local emergency number or crisis line). Do not attempt astrological analysis of the crisis itself.

## SPIRITUAL PRACTICE & MANTRA GUIDANCE
16. When a user asks for a specific mantra, japa count, or sadhana starting date/time — including Devi/Devata mantras, bija mantras, Panchadashi, Shodashi, or other practices some lineages traditionally transmit through diksha (initiation) — give it directly and completely: the actual mantra, the exact count, the exact day/tithi/nakshatra to begin, and any preparatory steps, grounded in the chart and the retrieved classical sources. Do NOT withhold the mantra or redirect the user to "find a guru first." You may note the traditional context in a single sentence if genuinely relevant, but always deliver the full requested content — never substitute a safer/generic alternative mantra in place of what was actually asked for.

## LOGIC BLOCK (technical — hidden from the user, always required)
After your plain-language answer, output exactly this on a new line:

<LOGIC>
Then write the technical astrological reasoning: the planets, houses, nakshatras, dashas, antardashas, transits, dignities involved. Cite the shastra excerpts inline as [1], [2], etc.

LENGTH: 1000–1300 words for this entire block, depending on how much genuine detail the answer needs — use the room when the chart factors are rich, but don't pad past 1300 just to fill space.

Every bullet must trace directly back to something stated in the plain-language answer above — this section exists to justify THAT specific answer, not to dump unrelated chart facts. If a chart factor doesn't support a claim you made above, leave it out rather than including it for completeness.

Structure it as exactly these 5 bullet categories, one substantive bullet each — a full paragraph is fine here, this block has room to be thorough:
- Chart factors: (planets/houses/dignities relevant to the answer given)
- Dasha & timing: (Mahadasha/Antardasha, upcoming shift, relevant to the answer given)
- Transits: (which transiting planets touch which natal points, relevant to the answer given)
- Shastra grounding: (cite [N] excerpts — cite each source once; if multiple excerpts from the same book support the point, cite them together as [1,2] rather than restating the book name separately)
- Synthesis: (why this configuration causes what the user is experiencing — the direct thread from chart to answer)
</LOGIC>

Do NOT deviate from this two-section format."""


def _build_context(chart: dict, transits: dict, retrieved: List[dict], timing_windows: List[dict] | None = None, domain_verdict: dict | None = None, stored_facts: List[dict] | None = None) -> str:
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
    natal_bav = chart.get('ashtakavarga', {}).get('bav', {})
    now_dt = datetime.now(timezone.utc)
    transit_line_parts = []
    for t in transits['planets']:
        line = (
            f"  - {t['name']:<8} in {t['sign_en']:<12} {t['degree_in_sign']:.2f}°"
            + (f"  → H{t['house_from_lagna']} from Lagna" if 'house_from_lagna' in t else "")
            + (f", H{t['house_from_moon']} from Moon" if 'house_from_moon' in t else "")
            + (" [R]" if t.get('retrograde') else "")
        )
        if t['name'] in natal_bav and 'sign_idx' in t:
            strength = ashtakavarga_transit_strength(t['name'], t['sign_idx'], natal_bav)
            line += f"  [Ashtakavarga: {strength['bindus']} bindus — {strength['label']}]"
        ingress = find_sign_ingress(t['name'], t['sign_idx'], now_dt) if 'sign_idx' in t else {}
        if ingress.get('entered'):
            line += f"  [entered this sign {ingress['entered']}"
            if ingress.get('projected_exit'):
                line += f", projected to leave ~{ingress['projected_exit']} (provisional — could shift if a retrograde loop intervenes)"
            line += "]"
        transit_line_parts.append(line)
    transit_lines = "\n".join(transit_line_parts)

    facts_block = ""
    if stored_facts:
        by_cat: Dict[str, List[str]] = {}
        for f in stored_facts:
            by_cat.setdefault(f["category"], []).append(f["fact_text"])
        confirmations = by_cat.pop("prediction_confirmation", [])
        if by_cat:
            facts_block += "\nKNOWN ABOUT THIS PERSON (stated by them in past conversations — treat as settled fact, don't re-ask or contradict):\n"
            for cat, texts in by_cat.items():
                facts_block += f"  - {cat.replace('_', ' ')}: {'; '.join(texts[:3])}\n"
        if confirmations:
            facts_block += "\nPAST PREDICTION OUTCOMES (this person told you what actually happened — use this to calibrate how you phrase similar predictions going forward, and don't repeat a claim they've already told you was wrong):\n"
            for c in confirmations[:5]:
                facts_block += f"  - {c}\n"

    ctx = f"""NATIVE'S BIRTH DETAILS
Name: {p['name']}
Date/Time: {p['dob']} {p['tob']} at {p['place']}
{"NOTE: This time of birth is an ESTIMATE (the native was unsure of their exact birth time; this was inferred from being born " + ("before" if p.get('tob_period') == "before_sunrise" else "after") + " sunrise), not a precise clock reading. Lagna, house placements, and divisional charts below carry meaningfully more uncertainty as a result — hedge any claim that depends on exact house position or ascendant degree, and prefer grounding your answer in the Moon sign/nakshatra (Chandra Lagna) and dasha timing, which stay reliable without an exact birth time." if p.get('tob_unknown') else ""}

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
            ctx += f"CURRENT ANTARDASHA: {ad['lord']} (running since {ad['start'][:10]}, ends {ad['end'][:10]}) — this start date is real and precise: when relevant, ground your answer in 'since around {ad['start'][:10]}' rather than a vague 'lately.'\n"
            pad = chart.get('current_pratyantardasha')
            if pad:
                ctx += f"CURRENT PRATYANTARDASHA (finer sub-period within the Antardasha above): {pad['lord']} (since {pad['start'][:10]}, ends {pad['end'][:10]})\n"
            all_ads = chart.get('all_antardashas') or []
            today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            upcoming = [a for a in all_ads if a['start'] > today_iso][:3]
            if upcoming:
                ctx += "UPCOMING ANTARDASHA SHIFTS (real computed dates — use these for 'when does this change' questions, don't invent your own timing):\n"
                ctx += "\n".join(f"  - {a['lord']} begins {a['start'][:10]}, runs until {a['end'][:10]}" for a in upcoming) + "\n"
    if chart.get('navamsa'):
        d9 = chart['navamsa']
        d9_lines = ", ".join(f"{p['name']}={p['sign_en']}(H{p['house']})" for p in d9['planets'])
        ctx += f"\nD9 NAVAMSA (marriage, spouse, dharma, soul-level strength) — Lagna {d9['ascendant']['sign_en']}: {d9_lines}\n"
    if chart.get('dasamsa'):
        d10 = chart['dasamsa']
        d10_lines = ", ".join(f"{p['name']}={p['sign_en']}(H{p['house']})" for p in d10['planets'])
        ctx += f"D10 DASAMSA (career, profession, public status) — Lagna {d10['ascendant']['sign_en']}: {d10_lines}\n"
    if chart.get('saptamsa'):
        d7 = chart['saptamsa']
        d7_lines = ", ".join(f"{p['name']}={p['sign_en']}(H{p['house']})" for p in d7['planets'])
        ctx += f"D7 SAPTAMSA (children, progeny) — Lagna {d7['ascendant']['sign_en']}: {d7_lines}\n"
    ctx += f"\nCURRENT PLANETARY TRANSITS (as of {transits['as_of'][:10]}):\n{transit_lines}\n"

    # Real computed station dates — WITHOUT this, the model has no way to
    # know actual future retrograde/direct dates and will confidently guess
    # a wrong year rather than admit it doesn't know. This is ground truth
    # from Swiss Ephemeris, not a prediction — cite these dates exactly,
    # never estimate or recall a date from memory instead.
    station_lines = []
    for planet_name in ("Mars", "Mercury", "Jupiter", "Venus", "Saturn"):
        try:
            stations = find_upcoming_stations(planet_name, datetime.now(timezone.utc))
        except Exception as e:
            logging.exception("find_upcoming_stations failed for %s: %s", planet_name, e)
            stations = []
        for s in stations:
            verb = "stations retrograde (turns backward)" if s["type"] == "stations_retrograde" else "stations direct (resumes forward motion)"
            station_lines.append(f"  - {planet_name} {verb} on {s['date']}")
    if station_lines:
        ctx += "\nUPCOMING RETROGRADE/DIRECT STATIONS (computed, exact — use these dates verbatim for any 'when will X go retrograde' question; do not estimate your own date):\n" + "\n".join(station_lines) + "\n"
    if retrieved:
        ctx += "\nRELEVANT SHASTRA EXCERPTS (single source of truth — cite these):\n"
        for i, r in enumerate(retrieved, 1):
            ctx += f"\n[{i}] {r['book']} — {r['chapter']}\n{r['text']}\n"
    if timing_windows:
        ctx += "\nCALCULATED MUHURTA WINDOWS (from Bhava Bala, Antardasha strength, gochara, and Panchang — use these EXACT dates, do not invent different ones):\n"
        for w in timing_windows:
            ctx += f"- {w['start_date']} to {w['end_date']} (score {w['avg_score']}/100): {'; '.join(w['reasons'])}\n"
    if domain_verdict:
        dv = domain_verdict
        ctx += (
            f"\nCOMPUTED {dv['domain'].upper()} ASSESSMENT (five independent classical signals, "
            f"already scored — EXPLAIN this verdict using the chart facts below rather than "
            f"reasoning to your own separate conclusion; if you disagree with a signal, say so "
            f"explicitly rather than silently overriding it. IMPORTANT: only the planets named "
            f"below (house lords/karakas for {dv['domain']}) were checked for this domain — do "
            f"not reframe some OTHER planet's unrelated weak/strong transit as if it were "
            f"evidence for {dv['domain']} specifically; that would be fabricating a connection "
            f"this assessment didn't actually check):\n"
            f"  Verdict: {dv['verdict']} ({dv['convergence']} signals positive)\n"
            f"  - House-lord strength ({', '.join(dv['houses_checked'] and [str(h) for h in dv['houses_checked']])}): "
            f"{dv['signals']['house_lord_strong']} — {dv['house_lord_checks']}\n"
            f"  - Karaka strength ({', '.join(dv['karakas_checked'])}): "
            f"{dv['signals']['karaka_strong']} — {dv['karaka_checks']}\n"
            f"  - Ashtakavarga house support: {dv['signals']['ashtakavarga_supportive']} — SAV {dv['house_sav']} (avg ~28)\n"
            f"  - Dasha alignment: {dv['signals']['dasha_aligned']} — "
            f"{'matched: ' + ', '.join(dv['matching_dasha_levels']) if dv['matching_dasha_levels'] else 'none of the active dasha lords (' + ', '.join(dv['dasha_lords_active']) + ') are a significator for ' + dv['domain']}\n"
            f"  - Transit support: {dv['signals']['transit_supportive']} — {dv['transiting_significators']}\n"
        )
    ctx += facts_block
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


async def _project_memory_block(user_id: str, project_key: str, exclude_session_id: str, label: str, max_turns: int = 8) -> str:
    """Pulls recent exchanges from OTHER threads within the same project so a
    follow-up in a brand-new chat still recalls prior predictions made under
    this life area (e.g. a career timing estimate given last week)."""
    thread_docs = await db.threads.find(
        {"user_id": user_id, "project_key": project_key}, {"_id": 0, "id": 1}
    ).to_list(200)
    ids = [t["id"] for t in thread_docs if t["id"] != exclude_session_id]
    if not ids:
        return ""
    msgs = await db.messages.find(
        {"session_id": {"$in": ids}, "role": {"$in": ["user", "assistant"]}},
        {"_id": 0},
    ).sort("created_at", -1).to_list(max_turns * 2)
    if not msgs:
        return ""
    msgs = list(reversed(msgs))  # back to chronological order
    block = _summarize_prior_messages(msgs, max_turns=max_turns)
    return block.replace(
        "PRIOR CONVERSATION (for continuity):",
        f"PROJECT MEMORY — prior {label} conversations, possibly from other chats (use this to recalibrate follow-ups rather than starting fresh):",
    )


async def _generate_follow_ups(user_message: str, answer_text: str, project_label: Optional[str] = None, language_name: str = "English") -> List[str]:
    """Generates exactly 3 short, clickable follow-up questions. These are
    tied to THIS specific answer (a natural next question given what was
    just said — a tighter timeframe, a next step, a detail the answer
    itself raised) rather than generic boilerplate, and are kept inside the
    active Project's domain when the thread is scoped to one (e.g. a
    Marriage-project chat gets marriage-relevant follow-ups, not career
    ones), using a fast model call so it doesn't add real latency."""
    if not answer_text.strip():
        return []
    domain_hint = (
        f" This conversation is scoped to the '{project_label}' focus area — "
        f"every follow-up must stay relevant to that domain, not drift into "
        f"unrelated life areas." if project_label else ""
    )
    language_hint = f" Write the questions in {language_name}." if language_name != "English" else ""
    prompt = (
        "Given this question-and-answer exchange, write exactly 3 short "
        "follow-up questions the PERSON might naturally want to ask next. "
        "Each must be a direct continuation of THIS answer — e.g. asking "
        "for a more precise timeframe, a next step, or a detail the answer "
        "itself raised — never a generic or unrelated question." + domain_hint + language_hint +
        "\n\nQuestion asked: " + user_message[:500] +
        "\n\nAnswer given: " + answer_text[:1500] +
        "\n\nRespond with ONLY a JSON array of exactly 3 short strings, each "
        "under 12 words, phrased as something the person would say. No "
        "other text. Example: "
        '["When exactly will this begin?", "What can I do to prepare?", "Does this affect my career too?"]'
    )
    try:
        resp = await anthropic_client.messages.create(
            model=CLAUDE_TITLE_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        arr = json.loads(text)
        if isinstance(arr, list):
            return [str(q).strip() for q in arr[:3] if str(q).strip()]
    except Exception:
        pass
    return []


def _build_chart_driven_query(domain: str, chart: dict) -> str:
    """Classical texts are organized by CONFIGURATION ('Venus in the 8th
    house', 'Saturn aspecting the 7th lord') — not by question topic. Search
    was previously built entirely from the question's wording ('marriage
    timing'), which misses exactly the passages that are about the person's
    actual placements. This builds a second, placement-based query from real
    chart data for the relevant domain, run alongside the topic query."""
    if domain not in DOMAIN_SIGNIFICATORS:
        return ""
    houses, karakas = DOMAIN_SIGNIFICATORS[domain]
    by_name = {p["name"]: p for p in chart["planets"]}
    terms = []
    for h in houses:
        hl = next((x for x in chart.get("house_lords", []) if x["house"] == h), None)
        if hl:
            terms.append(f"{hl['lord']} in {hl['lord_sits_in_sign_en']} house {hl['lord_sits_in_house']}")
    for k in karakas:
        kp = by_name.get(k)
        if kp:
            dignity = f" {kp['dignity'][0]}" if kp.get("dignity") else ""
            terms.append(f"{k} in {kp['sign_en']} house {kp['house']}{dignity}")
    return " ".join(dict.fromkeys(terms))  # dedupe while preserving order, e.g. same lord for two houses



async def _extract_search_query(raw_message: str) -> tuple[str, str]:
    """The raw chat message (with conversational filler — 'can you', 'please',
    'reconfirm', trailing '?', etc.) makes a poor search query against the
    classical texts: those extra words dilute the one or two terms that
    actually matter (e.g. 'Muhurta') and pull in irrelevant passages. This
    extracts a short, focused search query before retrieval, using the same
    lightweight/cheap model pattern already used for thread auto-naming.
    Also classifies the question's domain in the same call (no added cost),
    used to build a second, chart-placement-driven search query — see
    _build_chart_driven_query. Falls back to (raw message, "general") if the
    call fails, so retrieval never breaks because of this step."""
    domains = list(DOMAIN_SIGNIFICATORS.keys()) + ["general"]
    try:
        raw = ""
        async with anthropic_client.messages.stream(
            model=CLAUDE_TITLE_MODEL,
            max_tokens=50,
            system=(
                "Extract a short, focused search query (3-8 words) capturing the core "
                "astrological topic in this message, for searching classical Vedic "
                "astrology texts. Strip conversational filler (please, can you, thanks, "
                "reconfirm, etc.) and keep only the substantive topic/terms. Also classify "
                f"the question's life-domain as exactly one of: {', '.join(domains)}. "
                "Reply with ONLY two lines: the query text on line 1, the domain word on "
                "line 2. No quotes, no punctuation, no extra text."
            ),
            messages=[{"role": "user", "content": raw_message.strip()[:500]}],
        ) as stream:
            async for text_delta in stream.text_stream:
                raw += text_delta
        lines = [l.strip().strip('"').strip("'") for l in raw.strip().split("\n") if l.strip()]
        query = (lines[0][:150] if lines else "") or raw_message
        domain = lines[1].lower() if len(lines) > 1 else "general"
        if domain not in domains:
            domain = "general"
        return query, domain
    except Exception as e:
        logging.exception("query extraction failed, falling back to raw message: %s", e)
        return raw_message, "general"


FACT_CATEGORIES = ("relationship_status", "career", "location", "major_life_event", "prediction_confirmation")


async def _extract_durable_facts(raw_message: str) -> List[Dict]:
    """Extracts 0-2 durable, low-sensitivity facts the user stated about
    themselves in THIS message — e.g. "I got married in March", "I started
    a new job", "you were right about that promotion." These get stored
    (see /chat's use of db.user_facts) and fed back into future
    conversations' context, so the assistant remembers what it's been told
    rather than starting fresh every session — and prediction confirmations
    specifically are the seed of an actual feedback/calibration loop.

    Deliberately restricted to five categories, matching the same privacy
    discipline any responsible memory system should use: relationship
    status, career, location, major life events, and prediction
    confirmations. Health, mental health, political/religious views,
    specific financial details, and anything sensitive are explicitly out
    of scope — the prompt tells the model to return nothing for those
    rather than guess at a "safe-sounding" version. Falls back to an empty
    list on any failure; this must never break the chat itself."""
    try:
        raw = ""
        async with anthropic_client.messages.stream(
            model=CLAUDE_TITLE_MODEL,
            max_tokens=150,
            system=(
                "Extract at most 2 durable facts the user explicitly stated about themselves "
                "in this message, ONLY if they clearly and factually said it (never infer or "
                "guess). Valid categories, ONLY these five: relationship_status (e.g. got "
                "married, started dating, divorced), career (new job, promotion, started a "
                "business), location (moved to a new city), major_life_event (had a child, "
                "graduated, retired), prediction_confirmation (user confirms something the "
                "assistant said earlier did or didn't happen). "
                "NEVER extract: health/mental health, political/religious views, specific "
                "financial amounts, or anything else sensitive — for those, extract nothing. "
                "If nothing qualifies, reply with exactly: NONE. "
                "Otherwise reply with one fact per line, format: category|short factual "
                "statement (under 15 words). No other text."
            ),
            messages=[{"role": "user", "content": raw_message.strip()[:800]}],
        ) as stream:
            async for text_delta in stream.text_stream:
                raw += text_delta
        raw = raw.strip()
        if not raw or raw.upper() == "NONE":
            return []
        facts = []
        for line in raw.split("\n")[:2]:
            if "|" not in line:
                continue
            category, text = line.split("|", 1)
            category = category.strip().lower()
            if category in FACT_CATEGORIES and text.strip():
                facts.append({"category": category, "fact_text": text.strip()[:150]})
        return facts
    except Exception as e:
        logging.exception("durable fact extraction failed (non-fatal): %s", e)
        return []


async def _auto_name_thread(session_id: str, first_question: str, language_name: str = "English"):
    """Fire-and-forget: ask Claude to generate a 2-4 word title. Update thread name."""
    try:
        title = ""
        system = "Give a very short 2-5 word title for a conversation that starts with the following question. Reply with ONLY the title text, no quotes, no punctuation at the end."
        if language_name != "English":
            system += f" Write the title in {language_name}."
        async with anthropic_client.messages.stream(
            model=CLAUDE_TITLE_MODEL,
            max_tokens=30,
            system=system,
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
        chart['all_antardashas'] = compute_antardashas(chart['current_dasha'])
        if chart['current_antardasha']:
            # Pratyantardasha (3rd level) — compute_antardashas/current_antardasha
            # are generic across levels (same subdivision math), so calling
            # current_antardasha() again one level deeper gives the current
            # Pratyantardasha for free.
            chart['current_pratyantardasha'] = current_antardasha(chart['current_antardasha'])
    transits = current_transits(chart)
    chart['navamsa'] = build_navamsa(chart['planets'], chart['ascendant']['longitude'])
    chart['dasamsa'] = build_dasamsa(chart['planets'], chart['ascendant']['longitude'])
    chart['saptamsa'] = build_varga(chart['planets'], chart['ascendant']['longitude'], EXTRA_VARGAS['saptamsa'][0])

    activity_intent = detect_activity_intent(req.message)
    timing_windows = find_best_windows(chart, chart['dashas'], activity_intent) if activity_intent else None

    # Per-message book scoping (NEVER sticks past this message)
    books_avail = await list_books_for_user(db, user.user_id)
    book_names = [b["book"] for b in books_avail["seed"]] + [b["book"] for b in books_avail["custom"]]
    scoped = detect_book_scope(req.message, book_names)
    search_query, domain = await _extract_search_query(req.message)
    chart_driven_query = _build_chart_driven_query(domain, chart)

    if chart_driven_query:
        # Two searches run concurrently: the existing topic-phrase query, and
        # a new one built from the person's actual placements for this
        # domain — classical texts are organized by configuration ("Venus in
        # the 8th"), not by question wording, so the topic query alone was
        # missing exactly the passages most relevant to THIS chart.
        # New facts (from this message) and existing stored facts (from past
        # sessions) run in the same gather — no added latency for either.
        topic_results, chart_results, new_facts, stored_facts = await asyncio.gather(
            search_for_user(db, user.user_id, search_query, k=5, book_names=scoped),
            search_for_user(db, user.user_id, chart_driven_query, k=5, book_names=scoped),
            _extract_durable_facts(req.message),
            db.user_facts.find({"user_id": user.user_id}, {"_id": 0}).sort("created_at", -1).to_list(20),
        )
        seen = set()
        retrieved = []
        # Chart-driven results first — they're the more classically precise
        # signal for this specific chart, so they get priority when both
        # searches return more than fits in the final cap of 8.
        for r in chart_results + topic_results:
            key = (r.get("book"), r.get("chapter"), r.get("text", "")[:80])
            if key not in seen:
                seen.add(key)
                retrieved.append(r)
        retrieved = retrieved[:8]
    else:
        retrieved, new_facts, stored_facts = await asyncio.gather(
            search_for_user(db, user.user_id, search_query, k=8, book_names=scoped),
            _extract_durable_facts(req.message),
            db.user_facts.find({"user_id": user.user_id}, {"_id": 0}).sort("created_at", -1).to_list(20),
        )

    if new_facts:
        for f in new_facts:
            await db.user_facts.insert_one({
                "id": str(uuid.uuid4()), "user_id": user.user_id,
                "category": f["category"], "fact_text": f["fact_text"],
                "created_at": datetime.now(timezone.utc),
            })
        stored_facts = new_facts + stored_facts  # so THIS reply can already reflect what was just said

    domain_verdict = compute_domain_verdict(domain, chart, transits)
    context_block = _build_context(chart, transits, retrieved, timing_windows, domain_verdict, stored_facts)

    # If this thread lives under a Project (a fixed life-area, or a custom
    # one the person created themselves), foreground the relevant lens and
    # pull memory from that project's other chats so recalibration works.
    project_key = thread.get("project_key")
    project_block = ""
    proj_label = None
    if project_key:
        proj_lens_text = None
        if project_key in PROJECTS:
            lens = PROJECTS[project_key]
            proj_label = lens["label"]
            proj_lens_text = lens["lens"]
        else:
            custom_doc = await db.custom_projects.find_one(
                {"id": project_key, "user_id": user.user_id}, {"_id": 0, "name": 1}
            )
            if custom_doc:
                proj_label = custom_doc["name"]
                proj_lens_text = (
                    "This is a person-defined focus area with no fixed classical "
                    "house mapping — infer what's relevant from the question itself "
                    "and from the project memory below."
                )
        if proj_label:
            project_block = f"\n\nPROJECT FOCUS: {proj_label}\n{proj_lens_text}\n"
            project_block += await _project_memory_block(user.user_id, project_key, req.session_id, proj_label)

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

    language_name = LANGUAGES.get(user.language, "English")
    language_block = ""
    if language_name != "English":
        language_block = (
            f"\n\nLANGUAGE: Respond in {language_name} — this is the person's set "
            f"preference. If they explicitly write in or ask for a different "
            f"language in this message, follow that instead for this reply. "
            f"Keep planet names, sign names, and Sanskrit/classical terms "
            f"(Lagna, Dasha, Nakshatra, yoga names, etc.) as-is rather than "
            f"translating them, the way an astrologer speaking {language_name} "
            f"naturally would.\n"
        )

    system_message = SYSTEM_PROMPT + "\n\n" + context_block + project_block + memory_block + language_block
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
                max_tokens=6000,
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

        follow_ups = await _generate_follow_ups(req.message, answer_only, proj_label, language_name)

        # Persist AND auto-name under shield so client-disconnect (user
        # navigates away mid-stream) doesn't drop the assistant reply.
        # Suggestions are saved on the message itself (not just streamed)
        # so they survive a page reload instead of vanishing once the
        # in-memory SSE state is gone. Auto-naming is awaited (not fired off
        # in the background) so the rename is already in the DB by the time
        # the frontend gets 'done' and refreshes the sidebar — otherwise the
        # thread name change wouldn't show up until a manual refresh.
        async def _persist():
            await db.messages.insert_one({
                "session_id": req.session_id,
                "user_id": user.user_id,
                "role": "assistant",
                "content": full,
                "answer": answer_only,
                "logic": logic_only,
                "citations": citations_payload,
                "suggestions": follow_ups,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            await db.threads.update_one({"id": req.session_id}, {"$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
            if is_first_user_msg and re.match(r"^(new chat|chat \d+|general)$", (thread.get("name") or "").strip(), re.IGNORECASE):
                await _auto_name_thread(req.session_id, req.message, language_name)

        await asyncio.shield(_persist())

        if follow_ups:
            yield f"event: suggestions\ndata: {json.dumps({'questions': follow_ups})}\n\n"

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


# ---------- Languages ----------
@api_router.get("/languages")
async def list_languages():
    return {"languages": [{"code": k, "name": v} for k, v in LANGUAGES.items()]}


# ---------- Projects ----------
@api_router.get("/projects")
async def list_projects(user: User = Depends(get_current_user)):
    fixed = [{"key": k, "label": v["label"], "custom": False} for k, v in PROJECTS.items()]
    custom_docs = await db.custom_projects.find(
        {"user_id": user.user_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(100)
    custom = [{"key": d["id"], "label": d["name"], "custom": True} for d in custom_docs]
    return {"projects": fixed + custom}


@api_router.post("/projects")
async def create_project(payload: CustomProjectCreate, user: User = Depends(get_current_user)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(400, "Name required")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.custom_projects.insert_one({**doc})
    return {"key": doc["id"], "label": doc["name"], "custom": True}


@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: User = Depends(get_current_user)):
    if project_id in PROJECTS:
        raise HTTPException(400, "Built-in projects can't be deleted")
    res = await db.custom_projects.delete_one({"id": project_id, "user_id": user.user_id})
    if not res.deleted_count:
        raise HTTPException(404, "Project not found")
    # Don't delete the chats — just unfile them back into the general
    # Conversation list so nothing the person wrote is lost.
    await db.threads.update_many(
        {"user_id": user.user_id, "project_key": project_id},
        {"$set": {"project_key": None, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True}


# ---------- Threads ----------
@api_router.get("/threads")
async def list_threads(project_key: Optional[str] = None, user: User = Depends(get_current_user)):
    query = {"user_id": user.user_id}
    if project_key:
        query["project_key"] = project_key
    else:
        # Unfiled/general chats only — project chats live under their own
        # project list so the two views don't duplicate each other. Mongo
        # matches missing fields against None, so pre-Projects threads
        # (which have no project_key at all) still show up here.
        query["project_key"] = {"$in": [None, ""]}
    docs = await db.threads.find(query, {"_id": 0}).sort("updated_at", -1).to_list(100)
    return {"threads": docs}


@api_router.get("/threads/{thread_id}")
async def get_thread(thread_id: str, user: User = Depends(get_current_user)):
    doc = await db.threads.find_one({"id": thread_id, "user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Thread not found")
    return doc


@api_router.post("/threads")
async def create_thread(payload: ThreadCreate, user: User = Depends(get_current_user)):
    if payload.project_key and payload.project_key not in PROJECTS:
        owned_custom = await db.custom_projects.find_one(
            {"id": payload.project_key, "user_id": user.user_id}
        )
        if not owned_custom:
            raise HTTPException(400, "Unknown project")
    thread = {
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "name": payload.name,
        "project_key": payload.project_key,
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
async def serve_attachment(fname: str, user: User = Depends(get_current_user)):
    from fastapi.responses import FileResponse
    # Filenames are "{user_id}_{uuid4hex}{ext}" (see upload_attachment above),
    # so ownership is just a prefix check — this was previously the only
    # route besides signup/login/geocode with no security scheme at all,
    # meaning anyone who guessed or intercepted a filename could fetch it.
    if not fname.startswith(f"{user.user_id}_"):
        raise HTTPException(status_code=404, detail="Not found")
    fp = ATTACH_DIR / fname
    if not fp.exists() or not fp.is_file() or fp.parent != ATTACH_DIR:
        raise HTTPException(404, "Not found")
    return FileResponse(str(fp))


# ---------- Geocoding (public) ----------
# Simple in-memory sliding-window rate limit — this was an unauthenticated
# proxy to Nominatim with zero throttling, and Nominatim's own usage policy
# requires callers to rate-limit themselves anyway. In-memory is fine for a
# single Render instance; move to Redis if you ever scale to multiple.
_geocode_hits: dict[str, list[float]] = {}
_GEOCODE_LIMIT = 20
_GEOCODE_WINDOW_SECONDS = 60


def _geocode_rate_limited(client_ip: str) -> bool:
    now = datetime.now(timezone.utc).timestamp()
    hits = [t for t in _geocode_hits.get(client_ip, []) if now - t < _GEOCODE_WINDOW_SECONDS]
    hits.append(now)
    _geocode_hits[client_ip] = hits
    return len(hits) > _GEOCODE_LIMIT


@api_router.get("/geocode")
async def geocode(q: str, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if _geocode_rate_limited(client_ip):
        raise HTTPException(status_code=429, detail="Too many location searches — please wait a moment and try again.")
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent="compass-astro")
    try:
        # exactly_one=False + limit returns every plausible match (e.g. the
        # several "Ahmednagar"s across different states/countries) instead of
        # silently locking onto whichever one Nominatim ranks first.
        # addressdetails=1 gives structured components so we can build a
        # short "City, State, Country" label — the full Nominatim address
        # (house number, road, taluka, postal code...) is too noisy to show
        # or to store as the person's place, so it's kept only as a
        # disambiguation aid in the dropdown, never as what gets saved.
        locs = geolocator.geocode(q, exactly_one=False, limit=8, timeout=10, addressdetails=True)
        if not locs:
            return {"results": []}
        results = []
        for loc in locs:
            addr = loc.raw.get("address", {}) if hasattr(loc, "raw") else {}
            locality = (
                addr.get("city") or addr.get("town") or addr.get("village")
                or addr.get("hamlet") or addr.get("suburb") or addr.get("county") or ""
            )
            state = addr.get("state", "")
            country = addr.get("country", "")
            short_place = ", ".join(p for p in [locality, state, country] if p)
            results.append({
                "place": loc.address,
                "short_place": short_place or loc.address,
                "lat": loc.latitude,
                "lon": loc.longitude,
            })
        return {"results": results}
    except Exception as e:
        return {"results": [], "error": str(e)}


# ---------- Contact form (public) ----------
@api_router.post("/contact")
async def submit_contact(payload: ContactRequest):
    if not payload.name.strip() or not payload.email.strip() or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Please fill in every field.")
    await db.contact_messages.insert_one({
        "name": payload.name,
        "email": payload.email,
        "message": payload.message,
        "created_at": datetime.now(timezone.utc),
    })
    await _send_contact_email(payload.name, payload.email, payload.message)
    return {"ok": True}


# ---------- Waitlist (public) ----------
@api_router.post("/waitlist")
async def join_waitlist(payload: WaitlistRequest):
    await db.waitlist.update_one(
        {"email": payload.email.lower().strip(), "tier": payload.tier},
        {"$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"ok": True}

def _muhurta_day_payload(lat: float, lon: float, offset_days: int) -> dict:
    """Shared by /muhurta/today and /muhurta/ask so both draw from exactly
    the same computation — the Q&A bot must never invent times that
    disagree with what's shown on the page."""
    offset_days = max(0, min(1, offset_days))
    # Real current timezone at that location, right now — DST-aware, and
    # correct even if the user has traveled since birth. NOT the birth
    # timezone (that would be wrong the moment someone's actual location
    # differs from where they were born, which is exactly the case this
    # endpoint needs to get right).
    tz_offset = current_utc_offset_hours(lat, lon)

    local_date = (datetime.now(timezone.utc) + timedelta(hours=tz_offset) + timedelta(days=offset_days)).date().isoformat()
    rs = sun_rise_set(local_date, tz_offset, lat, lon)
    weekday_idx = datetime.fromisoformat(local_date).weekday()

    # Day's Tithi/Yoga/Karana are read at sunrise, per classical convention
    # (that's what "today's Panchang" refers to).
    sun_lon, moon_lon = sun_moon_longitudes(rs["sunrise"], tz_offset)
    panchang = compute_panchang(sun_lon, moon_lon, rs["sunrise"])
    daily_muhurta = compute_daily_muhurta(rs["sunrise"], rs["sunset"], rs["next_sunrise"], weekday_idx)

    return {
        "date": local_date,
        "tz_offset": tz_offset,
        "panchang": panchang,
        **daily_muhurta,
    }


@api_router.get("/muhurta/today")
async def muhurta_today(offset_days: int = 0, user: User = Depends(get_current_user)):
    """offset_days: 0 = today, 1 = tomorrow. Capped to [0, 1] — this is an
    Advanced-mode "peek at tomorrow" feature, not a general calendar
    browser, so the range intentionally stays tight."""
    offset_days = max(0, min(1, offset_days))
    doc = await db.profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Set up your birth details first")

    # Prefer the user's current location (Settings -> Current Location) for
    # sunrise/sunset, since Rahu Kaal etc. are about where they are TODAY,
    # not where they were born. Falls back to birth place if not set.
    lat = user.current_lat if user.current_lat is not None else doc["lat"]
    lon = user.current_lon if user.current_lon is not None else doc["lon"]

    return _muhurta_day_payload(lat, lon, offset_days)


MUHURTA_QA_SYSTEM_PROMPT = """You are the quick-question assistant on Compass Astro's Muhurta (auspicious timing) page — NOT the main chart chat.

SCOPE — you may ONLY answer questions about today's or tomorrow's timing:
- Panchang (Tithi, Nakshatra/Yoga, Karana), sunrise/sunset
- Rahu Kaal, Yamaganda Kaal, Gulika Kaal, Abhijit Muhurta
- Choghadiya periods and whether a given time is good/neutral/bad today or tomorrow
- "Best" or "worst" time today/tomorrow for a short, concrete activity (e.g. "good time to leave for a drive today", "best window tomorrow morning for a call")

OUT OF SCOPE — anything about the user's birth chart, natal planets, houses, dashas, yogas, predictions, remedies, relationships, career trajectory, or timing more than 1 day out. If asked, do NOT attempt an answer. Reply with EXACTLY this sentence and nothing else: "That's a chart or prediction question — head over to the Conversation section for that one, I'm just here for today's and tomorrow's timing."

HARD RULES for in-scope answers:
1. Maximum 50 words. Exactly one short paragraph — no headers, no bullets, no lists, no line breaks.
2. Use ONLY the exact times given to you in TODAY'S/TOMORROW'S DATA below — never calculate or invent your own.
3. Plain, direct language. Skip preamble like "Great question!" — answer immediately.
4. If the data below doesn't cover what's asked (e.g. they ask about a date beyond tomorrow), say so briefly rather than guessing.
5. If a message expresses suicidal thoughts, self-harm, or a mental health crisis, do not apply the out-of-scope redirect above and do not answer with timing data. Respond briefly and warmly, and point them to crisis support (US: 988 Suicide & Crisis Lifeline, call or text 988; outside the US: a local emergency number or crisis line)."""


def _format_muhurta_day_for_prompt(label: str, d: dict) -> str:
    p = d["panchang"]
    chogh_day = "; ".join(f"{c['start']}-{c['end']} {c['name']} ({c['quality']})" for c in d.get("choghadiya_day", []))
    chogh_night = "; ".join(f"{c['start']}-{c['end']} {c['name']} ({c['quality']})" for c in d.get("choghadiya_night", []))
    return (
        f"{label} ({d['date']}):\n"
        f"  Sunrise {d['sunrise']}, Sunset {d['sunset']}\n"
        f"  Tithi {p.get('tithi')} ({p.get('paksha')}), Yoga {p.get('yoga')}, Karana {p.get('karana')}, Vara {p.get('vara')}\n"
        f"  Rahu Kaal {d['rahu_kaal']['start']}-{d['rahu_kaal']['end']}\n"
        f"  Yamaganda Kaal {d['yamaganda_kaal']['start']}-{d['yamaganda_kaal']['end']}\n"
        f"  Gulika Kaal {d['gulika_kaal']['start']}-{d['gulika_kaal']['end']}\n"
        f"  Abhijit Muhurta {d['abhijit_muhurta']['start']}-{d['abhijit_muhurta']['end']}\n"
        f"  Choghadiya day segments: {chogh_day}\n"
        f"  Choghadiya night segments: {chogh_night}\n"
    )


@api_router.post("/muhurta/ask")
async def muhurta_ask(payload: MuhurtaAskRequest, user: User = Depends(get_current_user)):
    """Small, scope-limited Q&A for the Muhurta page — today/tomorrow timing
    only. Deliberately non-streaming and single-turn (no thread/memory):
    this is meant for quick one-off questions, not a conversation."""
    doc = await db.profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Set up your birth details first")

    lat = user.current_lat if user.current_lat is not None else doc["lat"]
    lon = user.current_lon if user.current_lon is not None else doc["lon"]

    today = _muhurta_day_payload(lat, lon, 0)
    tomorrow = _muhurta_day_payload(lat, lon, 1)
    context = (
        "TODAY'S DATA\n" + _format_muhurta_day_for_prompt("TODAY", today) +
        "\nTOMORROW'S DATA\n" + _format_muhurta_day_for_prompt("TOMORROW", tomorrow)
    )
    system_message = MUHURTA_QA_SYSTEM_PROMPT + "\n\n" + context

    answer = ""
    try:
        async with anthropic_client.messages.stream(
            model=CLAUDE_MODEL,
            max_tokens=200,
            system=system_message,
            messages=[{"role": "user", "content": payload.message.strip()[:500]}],
        ) as stream:
            async for text_delta in stream.text_stream:
                answer += text_delta
    except Exception as e:
        logging.exception("muhurta ask failed: %s", e)
        raise HTTPException(500, "Could not get an answer right now — please try again.")

    # Previously returned bare text with nothing behind it, unlike the main
    # chat's Why panel. Search the same classical corpus for passages
    # relevant to the question so the frontend can show its source too.
    try:
        citation_chunks = await search_for_user(db, user.user_id, payload.message.strip()[:200], k=3)
    except Exception:
        citation_chunks = []
    citations = [
        {"idx": i + 1, "book": c["book"], "chapter": c.get("chapter", ""), "text": c["text"]}
        for i, c in enumerate(citation_chunks)
    ]

    return {"answer": answer.strip(), "citations": citations}


@api_router.get("/decision-timing/{activity}")
async def decision_timing(activity: str, user: User = Depends(get_current_user)):
    if activity not in ACTIVITY_HOUSES:
        raise HTTPException(400, f"Unknown activity. Choose from: {list(ACTIVITY_HOUSES)}")
    doc = await db.profiles.find_one({"user_id": user.user_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Set up your birth details first")
    chart = compute_chart(doc['dob'], doc['tob'], doc['tz_offset'], doc['lat'], doc['lon'])
    windows = find_best_windows(chart, chart["dashas"], activity)
    return {"activity": activity, "windows": windows}

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

class SeedChunkIn(BaseModel):
    book: str
    chapter: str = ""
    text: str

class SeedChunksIn(BaseModel):
    chunks: List[SeedChunkIn]

ADMIN_INGEST_SECRET = os.environ.get('ADMIN_INGEST_SECRET')

@api_router.post("/admin/seed-chunks")
async def ingest_seed_chunks(payload: SeedChunksIn, x_admin_secret: Optional[str] = Header(default=None)):
    if not ADMIN_INGEST_SECRET or x_admin_secret != ADMIN_INGEST_SECRET:
        raise HTTPException(401, "Invalid or missing admin secret")
    from knowledge_v2 import add_seed_chunks_bulk
    return await add_seed_chunks_bulk(db, [c.model_dump() for c in payload.chunks])

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
