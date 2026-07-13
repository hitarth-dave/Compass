"""Compass Astro (iteration 6) backend tests — user-scoped endpoints, auth,
threads (with auto-name), library seed vs custom, per-message book scoping,
chart/transits regression, chat SSE citations+deltas+done."""
import os
import io
import json
import time
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"


# ---------- Seed helper ----------
def _mongo():
    return MongoClient(os.environ.get('MONGO_URL', 'mongodb://localhost:27017'))[os.environ.get('DB_NAME', 'test_database')]


# Worker-unique prefix so parallel xdist workers don't clean each other's data
_WORKER = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
_RUN_ID = f"{_WORKER}_{uuid.uuid4().hex[:6]}"
_CREATED_USER_IDS = []


def _seed_user(prefix: str):
    db = _mongo()
    uid = f"TEST_{_RUN_ID}_{prefix}_{uuid.uuid4().hex[:6]}"
    tok = f"TEST_{_RUN_ID}_tok_{prefix}_{uuid.uuid4().hex[:8]}"
    from datetime import datetime, timezone, timedelta
    db.users.insert_one({
        "user_id": uid,
        "email": f"TEST_{_RUN_ID}_{prefix}_{uid[-6:]}@ex.com",
        "name": f"User {prefix}",
        "picture": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    db.user_sessions.insert_one({
        "user_id": uid,
        "session_token": tok,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _CREATED_USER_IDS.append(uid)
    return uid, tok


def _bearer(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# Shared session-level users A & B
@pytest.fixture(scope="session")
def user_a():
    uid, tok = _seed_user("A")
    yield {"uid": uid, "tok": tok}


@pytest.fixture(scope="session")
def user_b():
    uid, tok = _seed_user("B")
    yield {"uid": uid, "tok": tok}


@pytest.fixture(scope="session")
def profile_a(user_a):
    """Seed a profile for user A so chart/chat endpoints work."""
    payload = {
        "name": "Arjuna",
        "dob": "1990-05-15",
        "tob": "14:30",
        "tz_offset": 5.5,
        "lat": 25.32,
        "lon": 83.0,
        "place": "Varanasi, India",
    }
    r = requests.post(f"{API}/profile", json=payload, headers=_bearer(user_a["tok"]), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ---------- 1. AUTH ----------
class TestAuth:
    def test_root_ok(self):
        r = requests.get(f"{API}/", timeout=15)
        assert r.status_code == 200
        assert "Compass" in r.json().get("message", "") or "compass" in r.json().get("message", "").lower()

    def test_me_no_auth_401(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401

    def test_me_with_bearer_returns_user(self, user_a):
        r = requests.get(f"{API}/auth/me", headers=_bearer(user_a["tok"]), timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("user_id", "email", "name"):
            assert k in d
        assert d["user_id"] == user_a["uid"]

    def test_me_invalid_token_401(self):
        r = requests.get(f"{API}/auth/me", headers=_bearer("garbage_token_xyz"), timeout=10)
        assert r.status_code == 401

    def test_protected_endpoints_all_401_without_auth(self):
        for path in ("/profile", "/threads", "/books", "/profile/chart", "/transits"):
            r = requests.get(f"{API}{path}", timeout=10)
            assert r.status_code == 401, f"{path} did not require auth (got {r.status_code})"


# ---------- 2. PROFILE + CHART + TRANSITS (user-scoped) ----------
class TestProfileChart:
    def test_profile_get_before_create(self, user_b):
        # user_b has no profile yet
        r = requests.get(f"{API}/profile", headers=_bearer(user_b["tok"]), timeout=10)
        assert r.status_code == 200
        assert r.json() is None

    def test_profile_upsert_and_chart(self, user_a, profile_a):
        # profile_a fixture created it. Verify
        r = requests.get(f"{API}/profile", headers=_bearer(user_a["tok"]), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d and d["name"] == "Arjuna"
        assert d["user_id"] == user_a["uid"]

    def test_chart_full_shape(self, user_a, profile_a):
        r = requests.get(f"{API}/profile/chart", headers=_bearer(user_a["tok"]), timeout=30)
        assert r.status_code == 200, r.text
        chart = r.json()
        for k in ("ascendant", "planets", "current_dasha", "current_antardasha", "house_lords", "navamsa", "yogas"):
            assert k in chart, f"chart.{k} missing"
        assert chart["ascendant"]["sign_en"] == "Virgo"
        assert len(chart["house_lords"]) == 12
        assert len(chart["navamsa"]["planets"]) == 9
        assert chart["current_antardasha"] is not None

    def test_transits_with_natal(self, user_a, profile_a):
        r = requests.get(f"{API}/transits", headers=_bearer(user_a["tok"]), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert len(d["planets"]) == 9
        for p in d["planets"]:
            assert "house_from_lagna" in p and 1 <= p["house_from_lagna"] <= 12


# ---------- 3. USER SCOPING (A cannot see B's data) ----------
class TestUserScoping:
    def test_b_cannot_read_a_profile(self, user_a, user_b, profile_a):
        # B's profile is null even though A has one
        r = requests.get(f"{API}/profile", headers=_bearer(user_b["tok"]), timeout=10)
        assert r.status_code == 200
        assert r.json() is None

    def test_b_cannot_see_a_thread(self, user_a, user_b, profile_a):
        # A creates a thread
        cr = requests.post(f"{API}/threads", json={"name": "TEST_A_thread"}, headers=_bearer(user_a["tok"]))
        assert cr.status_code == 200
        tid = cr.json()["id"]
        # B lists threads: must not contain tid
        lr = requests.get(f"{API}/threads", headers=_bearer(user_b["tok"]))
        assert lr.status_code == 200
        b_ids = [t["id"] for t in lr.json().get("threads", [])]
        assert tid not in b_ids
        # B fetches history: 404
        hr = requests.get(f"{API}/chat/{tid}/history", headers=_bearer(user_b["tok"]))
        assert hr.status_code == 404
        # B cannot rename/delete
        pr = requests.patch(f"{API}/threads/{tid}", json={"name": "hacked"}, headers=_bearer(user_b["tok"]))
        assert pr.status_code == 404
        dr = requests.delete(f"{API}/threads/{tid}", headers=_bearer(user_b["tok"]))
        assert dr.status_code == 404
        # cleanup
        requests.delete(f"{API}/threads/{tid}", headers=_bearer(user_a["tok"]))


# ---------- 4. LIBRARY (seed vs custom) ----------
class TestLibrary:
    def test_books_list_seed_shape(self, user_a):
        r = requests.get(f"{API}/books", headers=_bearer(user_a["tok"]), timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "seed" in d and "custom" in d
        assert isinstance(d["seed"], list) and isinstance(d["custom"], list)
        assert len(d["seed"]) == 12, f"expected 12 seed books, got {len(d['seed'])}"
        for b in d["seed"]:
            assert b["is_seed"] is True
            assert b["book_id"] == "seed"
            assert "book" in b and "chunk_count" in b

    def test_delete_seed_returns_400(self, user_a):
        r = requests.delete(f"{API}/books/seed", headers=_bearer(user_a["tok"]))
        assert r.status_code == 400

    def test_upload_custom_pdf_appears_in_custom(self, user_a):
        # Prefer a real PDF fixture if present; else construct with fpdf2
        try:
            from pypdf import PdfWriter  # noqa: F401
        except Exception:
            pytest.skip("pypdf not installed")
        fx = "/app/test_fixtures/test.pdf"
        if not os.path.exists(fx):
            try:
                from fpdf import FPDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Helvetica", size=12)
                pdf.multi_cell(0, 8, (
                    "Test scripture excerpt: The Sun rules the tenth house of Karma and grants "
                    "authority when strong. This is a small custom book uploaded for automated "
                    "testing purposes only. It should be searchable and deletable by the uploading user only."
                ))
                os.makedirs("/app/test_fixtures", exist_ok=True)
                pdf.output(fx)
            except Exception as e:
                pytest.skip(f"Cannot construct PDF fixture: {e}")
        pdf_bytes = open(fx, "rb").read()

        files = {"file": ("TEST_custom_book.pdf", pdf_bytes, "application/pdf")}
        r = requests.post(f"{API}/books/upload", files=files, headers=_bearer(user_a["tok"]), timeout=30)
        assert r.status_code == 200, r.text
        up = r.json()
        assert up.get("chunks_added", 0) >= 1, f"expected chunks_added >=1, got {up}"
        book_id = up["book_id"]
        assert book_id and book_id != "seed"

        # It appears in /books custom
        lr = requests.get(f"{API}/books", headers=_bearer(user_a["tok"]))
        custom = lr.json()["custom"]
        assert any(b["book_id"] == book_id for b in custom), f"uploaded book not in custom: {custom}"
        c = next(b for b in custom if b["book_id"] == book_id)
        assert c["is_seed"] is False

        # It is user-scoped (B does NOT see it)
        lr_b = _bearer_get_books = requests.get(f"{API}/books", headers=_bearer(TestLibrary._user_b_tok))
        assert lr_b.status_code == 200
        assert not any(b["book_id"] == book_id for b in lr_b.json()["custom"])

        # /books/search returns the custom chunk
        sr = requests.get(f"{API}/books/search", params={"q": "custom book uploaded testing"},
                          headers=_bearer(user_a["tok"]))
        assert sr.status_code == 200
        results = sr.json().get("results", [])
        assert any(not r.get("is_seed", True) for r in results), f"no custom chunk returned in search: {results[:2]}"

        # Delete the custom book — chunks removed
        dr = requests.delete(f"{API}/books/{book_id}", headers=_bearer(user_a["tok"]))
        assert dr.status_code == 200
        assert dr.json().get("deleted_chunks", 0) >= 1

        # After delete: not in /books
        lr2 = requests.get(f"{API}/books", headers=_bearer(user_a["tok"]))
        assert not any(b["book_id"] == book_id for b in lr2.json()["custom"])
        # /books/search does not return the deleted chunk
        sr2 = requests.get(f"{API}/books/search", params={"q": "custom book uploaded testing"},
                           headers=_bearer(user_a["tok"]))
        for res in sr2.json().get("results", []):
            assert res.get("is_seed", True) is True or res.get("book") != "TEST_custom_book.pdf", \
                f"deleted chunk still returned: {res}"


# Inject user_b token into TestLibrary class before running (set from a fixture)
@pytest.fixture(autouse=True, scope="session")
def _inject_userb(user_b):
    TestLibrary._user_b_tok = user_b["tok"]


# ---------- 5. SSE helper ----------
def _read_sse(response, max_seconds=90):
    events = []
    buf = ""
    deadline = time.time() + max_seconds
    for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
        if not chunk:
            continue
        buf += chunk
        while "\n\n" in buf:
            block, buf = buf.split("\n\n", 1)
            lines = block.split("\n")
            evt = next((l[6:].strip() for l in lines if l.startswith("event:")), None)
            data_line = next((l[5:].strip() for l in lines if l.startswith("data:")), None)
            if data_line is None:
                continue
            try:
                data = json.loads(data_line)
            except Exception:
                data = data_line
            events.append((evt, data))
            if evt == "done":
                return events
        if time.time() > deadline:
            break
    return events


# ---------- 6. AUTO-NAME THREAD ----------
class TestAutoName:
    def test_first_message_renames_thread(self, user_a, profile_a):
        # Create a "Chat 1" (default-name) thread
        cr = requests.post(f"{API}/threads", json={"name": "Chat 1"}, headers=_bearer(user_a["tok"]))
        assert cr.status_code == 200, f"create thread failed: {cr.status_code} {cr.text}"
        tid = cr.json()["id"]
        # Send a chat message
        payload = {"session_id": tid, "message": "What does my chart say about my career direction?"}
        with requests.post(f"{API}/chat", json=payload, headers=_bearer(user_a["tok"]), stream=True, timeout=180) as r:
            assert r.status_code == 200, f"chat failed: {r.status_code} {r.text[:200]}"
            events = _read_sse(r, max_seconds=180)
        assert any(e == "done" for e, _ in events)
        # Poll /threads for up to 20s to see the name change
        deadline = time.time() + 20
        final_name = None
        while time.time() < deadline:
            lr = requests.get(f"{API}/threads", headers=_bearer(user_a["tok"]))
            assert lr.status_code == 200, f"threads GET failed: {lr.status_code} {lr.text[:200]}"
            match = next((t for t in lr.json().get("threads", []) if t["id"] == tid), None)
            if match and match["name"] and match["name"].lower() not in ("chat 1", "new chat", "general"):
                final_name = match["name"]
                break
            time.sleep(1)
        assert final_name, f"thread name did not auto-rename from 'Chat 1' within 20s"
        # 2-5 words heuristic (allow up to 8 for lenience)
        assert 1 <= len(final_name.split()) <= 8, f"auto-name unexpected length: {final_name!r}"
        # cleanup
        requests.delete(f"{API}/threads/{tid}", headers=_bearer(user_a["tok"]))


# ---------- 7. MANUAL RENAME ----------
class TestManualRename:
    def test_rename_persists(self, user_a):
        cr = requests.post(f"{API}/threads", json={"name": "TEST_orig"}, headers=_bearer(user_a["tok"]))
        tid = cr.json()["id"]
        pr = requests.patch(f"{API}/threads/{tid}", json={"name": "My Career"}, headers=_bearer(user_a["tok"]))
        assert pr.status_code == 200
        lr = requests.get(f"{API}/threads", headers=_bearer(user_a["tok"]))
        row = next(t for t in lr.json()["threads"] if t["id"] == tid)
        assert row["name"] == "My Career"
        requests.delete(f"{API}/threads/{tid}", headers=_bearer(user_a["tok"]))

    def test_rename_missing_404(self, user_a):
        r = requests.patch(f"{API}/threads/nonexistent-xyz", json={"name": "x"}, headers=_bearer(user_a["tok"]))
        assert r.status_code == 404


# ---------- 8. PER-MESSAGE BOOK SCOPING ----------
class TestBookScoping:
    def test_scoped_msg_emits_scope_event_then_followup_does_not(self, user_a, profile_a):
        # Create fresh thread (default name so auto-name won't interfere with test flow)
        cr = requests.post(f"{API}/threads", json={"name": "TEST_scope"}, headers=_bearer(user_a["tok"]))
        assert cr.status_code == 200, f"create thread failed: {cr.status_code} {cr.text}"
        tid = cr.json()["id"]

        # (a) Scoped message
        payload1 = {"session_id": tid, "message": "Answer from Phaladeepika: what shapes my career?"}
        events1 = []
        deltas1 = ""
        citations1 = []
        with requests.post(f"{API}/chat", json=payload1, headers=_bearer(user_a["tok"]), stream=True, timeout=180) as r:
            assert r.status_code == 200
            events1 = _read_sse(r, max_seconds=180)
        assert any(e == "done" for e, _ in events1)

        # scope must appear
        evt_names = [e for e, _ in events1]
        assert "scope" in evt_names, f"no 'scope' event emitted for scoped message. events={evt_names[:10]}"

        # scope must appear BEFORE any delta
        first_delta_idx = next((i for i, (e, _) in enumerate(events1) if e == "delta"), -1)
        first_scope_idx = next((i for i, (e, _) in enumerate(events1) if e == "scope"), -1)
        assert first_scope_idx >= 0 and (first_delta_idx == -1 or first_scope_idx < first_delta_idx), (
            f"scope event did not precede deltas; scope={first_scope_idx} delta={first_delta_idx}"
        )

        # scope payload must include Phaladeepika
        scope_evt = next(d for e, d in events1 if e == "scope")
        assert "books" in scope_evt
        assert any("Phaladeepika" in b for b in scope_evt["books"]), f"scope books = {scope_evt['books']}"

        # FIX (a): citations must be non-empty for tiny-pool BM25 (Phaladeepika has 2 chunks).
        # All citations must be from Phaladeepika.
        cits1 = next((d for e, d in events1 if e == "citations"), [])
        assert isinstance(cits1, list)
        assert len(cits1) >= 1, f"FIX (a) BM25 tiny-pool: expected ≥1 citation on scoped msg, got 0"
        for c in cits1:
            assert "Phaladeepika" in c["book"], f"non-Phaladeepika citation leaked: {c['book']}"

        # (b) Follow-up (no scope trigger) — scope MUST NOT emit
        payload2 = {"session_id": tid, "message": "And what about my relationships?"}
        with requests.post(f"{API}/chat", json=payload2, headers=_bearer(user_a["tok"]), stream=True, timeout=180) as r2:
            assert r2.status_code == 200
            events2 = _read_sse(r2, max_seconds=180)
        assert any(e == "done" for e, _ in events2)
        evt2_names = [e for e, _ in events2]
        assert "scope" not in evt2_names, f"scope leaked to follow-up! events={evt2_names[:10]}"
        # citations may come from any book — just assert we got some
        cits2 = next(d for e, d in events2 if e == "citations")
        assert isinstance(cits2, list) and len(cits2) > 0

        # cleanup
        requests.delete(f"{API}/threads/{tid}", headers=_bearer(user_a["tok"]))


# ---------- 9. CHAT SSE REGRESSION (citations + deltas + done + logic) ----------
class TestChatSSE:
    def test_chat_streams_citations_deltas_done(self, user_a, profile_a):
        cr = requests.post(f"{API}/threads", json={"name": "TEST_chat_sse"}, headers=_bearer(user_a["tok"]))
        tid = cr.json()["id"]
        payload = {"session_id": tid, "message": "Why is my career stuck?"}
        with requests.post(f"{API}/chat", json=payload, headers=_bearer(user_a["tok"]), stream=True, timeout=180) as r:
            assert r.status_code == 200, r.text
            events = _read_sse(r, max_seconds=180)
        evt_names = [e for e, _ in events]
        assert "citations" in evt_names
        assert "delta" in evt_names
        assert "done" in evt_names
        full = "".join(d.get("text", "") for e, d in events if e == "delta")
        assert len(full) > 100
        assert "<LOGIC>" in full
        # History persists
        hr = requests.get(f"{API}/chat/{tid}/history", headers=_bearer(user_a["tok"]))
        assert hr.status_code == 200
        msgs = hr.json()["messages"]
        assert any(m["role"] == "assistant" and (m.get("logic") or "") for m in msgs)
        requests.delete(f"{API}/threads/{tid}", headers=_bearer(user_a["tok"]))


# ---------- 10. FIX (a) BM25 tiny-pool floor (unit-level test via public API) ----------
class TestBM25TinyPool:
    def test_scoped_search_returns_results_from_tiny_book(self, user_a, profile_a):
        """FIX (a): search_for_user with book_names={'Phaladeepika (Mantreswara)'}
        must return ≥1 chunk for 'career' or 'marriage' even though Phaladeepika
        has only 2 seed chunks (BM25 IDF collapses).
        We exercise via /api/chat SSE 'citations' event with an explicit scope trigger.
        """
        for msg in (
            "As per Phaladeepika, what shapes my career?",
            "According to Phaladeepika, when is marriage timing best?",
        ):
            cr = requests.post(f"{API}/threads", json={"name": "TEST_bm25_tiny"}, headers=_bearer(user_a["tok"]))
            tid = cr.json()["id"]
            try:
                with requests.post(f"{API}/chat", json={"session_id": tid, "message": msg},
                                    headers=_bearer(user_a["tok"]), stream=True, timeout=180) as r:
                    assert r.status_code == 200
                    events = _read_sse(r, max_seconds=180)
                evt_names = [e for e, _ in events]
                assert "scope" in evt_names, f"expected 'scope' for msg={msg!r}, got events={evt_names[:8]}"
                cits = next((d for e, d in events if e == "citations"), [])
                assert isinstance(cits, list) and len(cits) >= 1, (
                    f"FIX (a) failed: expected ≥1 Phaladeepika citation for msg={msg!r}, got {len(cits)}"
                )
                for c in cits:
                    assert "Phaladeepika" in c["book"], f"non-Phaladeepika citation leaked: {c['book']}"
            finally:
                requests.delete(f"{API}/threads/{tid}", headers=_bearer(user_a["tok"]))


# ---------- 11. FIX (c) Persist on client disconnect ----------
class TestPersistOnDisconnect:
    def test_assistant_msg_persists_when_client_aborts_mid_stream(self, user_a, profile_a):
        """FIX (c): kill the SSE mid-stream (after 2-3 deltas, BEFORE 'done').
        Poll /api/chat/{tid}/history within 10s — assistant message MUST be persisted
        (content non-empty). Auto-name (if 'Chat N') should still fire eventually.
        """
        cr = requests.post(f"{API}/threads", json={"name": "Chat 1"}, headers=_bearer(user_a["tok"]))
        tid = cr.json()["id"]
        try:
            payload = {"session_id": tid, "message": "What does my career look like this year?"}
            deltas_seen = 0
            with requests.post(f"{API}/chat", json=payload, headers=_bearer(user_a["tok"]),
                                stream=True, timeout=60) as r:
                assert r.status_code == 200
                buf = ""
                for chunk in r.iter_content(chunk_size=None, decode_unicode=True):
                    if not chunk:
                        continue
                    buf += chunk
                    while "\n\n" in buf:
                        block, buf = buf.split("\n\n", 1)
                        if "event: delta" in block:
                            deltas_seen += 1
                        if deltas_seen >= 2:
                            break
                    if deltas_seen >= 2:
                        r.close()
                        break
            assert deltas_seen >= 2, f"could not observe ≥2 deltas before abort (saw {deltas_seen})"

            # Poll history for up to 15s
            deadline = time.time() + 15
            persisted = None
            while time.time() < deadline:
                hr = requests.get(f"{API}/chat/{tid}/history", headers=_bearer(user_a["tok"]))
                assert hr.status_code == 200
                msgs = hr.json().get("messages", [])
                assistant = [m for m in msgs if m["role"] == "assistant"]
                if assistant and (assistant[-1].get("content") or "").strip():
                    persisted = assistant[-1]
                    break
                time.sleep(1)
            assert persisted is not None, (
                "FIX (c) failed: assistant message was NOT persisted after client disconnected mid-stream"
            )
            assert len(persisted.get("content", "")) > 0
        finally:
            requests.delete(f"{API}/threads/{tid}", headers=_bearer(user_a["tok"]))


# ---------- 12. FIX (e) Tightened detect_book_scope regex ----------
class TestScopeRegexTightened:
    def _events(self, tok, tid, msg):
        with requests.post(f"{API}/chat", json={"session_id": tid, "message": msg},
                            headers=_bearer(tok), stream=True, timeout=180) as r:
            assert r.status_code == 200
            return _read_sse(r, max_seconds=180)

    def test_in_and_per_no_longer_trigger_scope(self, user_a, profile_a):
        cr = requests.post(f"{API}/threads", json={"name": "TEST_regex"}, headers=_bearer(user_a["tok"]))
        tid = cr.json()["id"]
        try:
            for msg in ("What is happening in my career?", "Guide me per my mahadasha"):
                events = self._events(user_a["tok"], tid, msg)
                evt_names = [e for e, _ in events]
                assert "scope" not in evt_names, (
                    f"FIX (e) failed: msg={msg!r} triggered scope. events={evt_names[:8]}"
                )
                assert "done" in evt_names
        finally:
            requests.delete(f"{API}/threads/{tid}", headers=_bearer(user_a["tok"]))

    def test_as_per_still_triggers_scope(self, user_a, profile_a):
        cr = requests.post(f"{API}/threads", json={"name": "TEST_regex2"}, headers=_bearer(user_a["tok"]))
        tid = cr.json()["id"]
        try:
            events = self._events(user_a["tok"], tid, "As per Phaladeepika, what shapes my career?")
            evt_names = [e for e, _ in events]
            assert "scope" in evt_names, "FIX (e) regression: 'as per <book>' must still trigger scope"
            scope_evt = next(d for e, d in events if e == "scope")
            assert any("Phaladeepika" in b for b in scope_evt["books"])
        finally:
            requests.delete(f"{API}/threads/{tid}", headers=_bearer(user_a["tok"]))


# ---------- Session cleanup ----------
@pytest.fixture(autouse=True, scope="session")
def _final_cleanup(request):
    yield
    db = _mongo()
    if not _CREATED_USER_IDS:
        return
    # Only delete users this worker created (safe under xdist)
    db.users.delete_many({"user_id": {"$in": _CREATED_USER_IDS}})
    db.user_sessions.delete_many({"user_id": {"$in": _CREATED_USER_IDS}})
    db.profiles.delete_many({"user_id": {"$in": _CREATED_USER_IDS}})
    db.threads.delete_many({"user_id": {"$in": _CREATED_USER_IDS}})
    db.messages.delete_many({"user_id": {"$in": _CREATED_USER_IDS}})
    db.book_chunks.delete_many({"user_id": {"$in": _CREATED_USER_IDS}})
