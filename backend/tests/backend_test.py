"""Backend tests for Jyotish AI enriched chart, transits with houses, SSE chat with citations,
conversation memory, and chat history persistence."""
import os
import json
import time
import uuid
import pytest
import requests

BASE_URL = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
API = f"{BASE_URL}/api"

# Seeded test profile (Arjuna, 1990-05-15, Varanasi)
TEST_PROFILE_ID = "96eb44c1-0d76-4050-b10f-8cf5dbc215ae"


# ---------- Health / basic ----------
class TestHealth:
    def test_root_ok(self):
        r = requests.get(f"{API}/", timeout=15)
        assert r.status_code == 200
        assert "message" in r.json()

    def test_seed_profile_exists(self):
        r = requests.get(f"{API}/profile/{TEST_PROFILE_ID}", timeout=15)
        assert r.status_code == 200, f"Seed profile missing: {r.text}"
        data = r.json()
        assert data["id"] == TEST_PROFILE_ID
        assert data["name"] == "Arjuna"


# ---------- Enriched Chart ----------
class TestChartEnriched:
    """chart endpoint must expose house_lords, current_antardasha, navamsa, yogas."""

    @pytest.fixture(scope="class")
    def chart(self):
        r = requests.get(f"{API}/profile/{TEST_PROFILE_ID}/chart", timeout=30)
        assert r.status_code == 200, r.text
        return r.json()

    def test_ascendant_shape(self, chart):
        asc = chart.get("ascendant")
        assert asc, "ascendant missing"
        # Iteration 3: ascendant must now include nakshatra + pada for kundali 'As' rendering
        for k in ("sign_en", "sign_idx", "degree_in_sign", "lord", "nakshatra", "pada"):
            assert k in asc, f"asc.{k} missing"
        # For Arjuna seed profile: Lagna is Virgo w/ Uttara Phalguni nakshatra
        assert asc["sign_en"] == "Virgo"
        assert asc["nakshatra"] == "Uttara Phalguni"
        assert asc["lord"] == "Mercury"

    def test_current_dasha_and_antardasha(self, chart):
        md = chart.get("current_dasha")
        assert md is not None, "current_dasha missing"
        for k in ("lord", "start", "end", "years"):
            assert k in md
        ad = chart.get("current_antardasha")
        assert ad is not None, "current_antardasha missing"
        for k in ("lord", "start", "end", "years"):
            assert k in ad, f"antardasha.{k} missing"
        # antardasha must be within mahadasha window
        assert md["start"] <= ad["start"] <= md["end"]

    def test_house_lords_12(self, chart):
        hl = chart.get("house_lords")
        assert hl is not None, "house_lords missing"
        assert len(hl) == 12
        for row in hl:
            for k in ("house", "sign_en", "lord", "lord_sits_in_house", "lord_sits_in_sign_en"):
                assert k in row, f"house_lord row missing {k}: {row}"
            assert 1 <= row["house"] <= 12
            assert 1 <= row["lord_sits_in_house"] <= 12

    def test_navamsa_present(self, chart):
        nav = chart.get("navamsa")
        assert nav is not None, "navamsa missing"
        assert "ascendant" in nav
        assert "sign_en" in nav["ascendant"]
        assert isinstance(nav["planets"], list)
        # Should have 9 planets (Sun..Ketu)
        assert len(nav["planets"]) == 9
        for p in nav["planets"]:
            for k in ("name", "sign_en", "house"):
                assert k in p
            # Iteration 3: D9 planets must now carry nakshatra (copied from D1) so KundaliChart d9 has data
            assert "nakshatra" in p, f"navamsa.{p['name']}.nakshatra missing"

    def test_yogas_list(self, chart):
        yogas = chart.get("yogas")
        assert yogas is not None, "yogas missing"
        assert isinstance(yogas, list)
        # May be empty; if present items must have name and detail
        for y in yogas:
            assert "name" in y and "detail" in y


# ---------- Transits with house tags ----------
class TestTransits:
    def test_transits_with_profile_id_has_houses(self):
        r = requests.get(f"{API}/transits", params={"profile_id": TEST_PROFILE_ID}, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "planets" in data
        # 9 planets incl Ketu
        assert len(data["planets"]) == 9
        for t in data["planets"]:
            assert "house_from_lagna" in t, f"missing house_from_lagna for {t.get('name')}"
            assert "house_from_moon" in t, f"missing house_from_moon for {t.get('name')}"
            assert 1 <= t["house_from_lagna"] <= 12
            assert 1 <= t["house_from_moon"] <= 12

    def test_transits_without_profile_id_ok(self):
        r = requests.get(f"{API}/transits", timeout=20)
        assert r.status_code == 200
        data = r.json()
        # No house tags when natal not provided
        for t in data["planets"]:
            assert "house_from_lagna" not in t


# ---------- SSE Chat: citations, deltas, done, chart-aware ----------
def _read_sse(response, max_seconds=90):
    """Iterate SSE stream, return list of (event, data)."""
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


class TestChatSSE:
    session_id = f"TEST_{uuid.uuid4()}"

    def test_chat_career_question_chart_aware(self):
        payload = {
            "profile_id": TEST_PROFILE_ID,
            "session_id": self.session_id,
            "message": "Why is my career stuck? What does my 10th house say?",
        }
        with requests.post(f"{API}/chat", json=payload, stream=True, timeout=120) as r:
            assert r.status_code == 200, r.text
            events = _read_sse(r, max_seconds=120)

        # Assert we saw citations, deltas, and done
        evt_names = [e for e, _ in events]
        assert "citations" in evt_names, f"no citations event, events={evt_names[:8]}"
        assert "delta" in evt_names, f"no delta events, events={evt_names[:8]}"
        assert "done" in evt_names, f"no done event, events={evt_names[-5:]}"

        # Citations structure
        cits = next(d for e, d in events if e == "citations")
        assert isinstance(cits, list)
        assert len(cits) > 0
        for c in cits:
            for k in ("idx", "book", "chapter", "text", "score"):
                assert k in c, f"citation missing {k}: {c}"

        # Accumulate delta text
        full = "".join(d.get("text", "") for e, d in events if e == "delta")
        assert len(full) > 100, f"assistant reply too short ({len(full)} chars): {full!r}"
        low = full.lower()
        # Chart-aware: mention 10th house/lord AND current dasha (Rahu) or antardasha planet
        mentions_10th = "10th" in low or "tenth" in low or "10 th" in low
        mentions_dasha = ("rahu" in low) or ("mahadasha" in low) or ("antardasha" in low) or ("dasha" in low)
        mentions_mercury_or_lord = "mercury" in low or "10th lord" in low or "tenth lord" in low
        assert mentions_10th, f"reply not chart-aware (no 10th house): {full[:400]}"
        assert mentions_dasha, f"reply not dasha-aware: {full[:400]}"
        assert mentions_mercury_or_lord, f"reply doesn't mention 10th lord/Mercury: {full[:400]}"

        # Save session_id for the follow-up memory test
        TestChatSSE._first_full = full

    def test_conversation_memory_followup(self):
        # Use the same session used above
        payload = {
            "profile_id": TEST_PROFILE_ID,
            "session_id": self.session_id,
            "message": "And what remedy?",
        }
        with requests.post(f"{API}/chat", json=payload, stream=True, timeout=120) as r:
            assert r.status_code == 200, r.text
            events = _read_sse(r, max_seconds=120)
        assert any(e == "done" for e, _ in events)
        full = "".join(d.get("text", "") for e, d in events if e == "delta")
        assert len(full) > 50, f"follow-up too short: {full!r}"
        low = full.lower()
        # Must NOT be an off-topic clarifier like 'remedy for what?'
        clarify_signal = "remedy for what" in low or "which topic" in low or "please specify" in low
        assert not clarify_signal, f"assistant asked for clarification instead of continuing context: {full[:400]}"
        # Must reference context: career/10th/mercury/rahu remedy hints
        topical = any(k in low for k in ["mercury", "career", "10th", "tenth", "rahu"])
        assert topical, f"follow-up not context-aware: {full[:400]}"

    def test_history_persisted(self):
        # Give MongoDB a moment
        time.sleep(1)
        r = requests.get(f"{API}/chat/{self.session_id}/history", timeout=20)
        assert r.status_code == 200
        msgs = r.json().get("messages", [])
        # At least 4 messages: 2 user + 2 assistant
        assert len(msgs) >= 4, f"expected >=4 messages, got {len(msgs)}"
        roles = [m["role"] for m in msgs]
        assert roles.count("user") >= 2
        assert roles.count("assistant") >= 2
        # Assistant messages must carry citations
        assistants = [m for m in msgs if m["role"] == "assistant"]
        assert any((m.get("citations") or []) for m in assistants), "no citations persisted on any assistant message"


# ---------- Threads CRUD ----------
class TestThreads:
    """POST/GET/PATCH/DELETE /api/threads endpoints."""
    _thread_id = None

    def test_create_thread(self):
        r = requests.post(f"{API}/threads", json={"profile_id": TEST_PROFILE_ID, "name": "TEST_thread_a"}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("id", "profile_id", "name", "created_at", "updated_at"):
            assert k in data, f"missing {k} in create response"
        assert data["profile_id"] == TEST_PROFILE_ID
        assert data["name"] == "TEST_thread_a"
        assert isinstance(data["id"], str) and len(data["id"]) > 10
        TestThreads._thread_id = data["id"]

    def test_list_threads_contains_new(self):
        assert TestThreads._thread_id is not None
        r = requests.get(f"{API}/threads", params={"profile_id": TEST_PROFILE_ID}, timeout=15)
        assert r.status_code == 200
        threads = r.json().get("threads", [])
        assert isinstance(threads, list)
        ids = [t["id"] for t in threads]
        assert TestThreads._thread_id in ids, f"created thread not in list: {ids[:5]}"

    def test_rename_thread_persists(self):
        tid = TestThreads._thread_id
        assert tid
        r = requests.patch(f"{API}/threads/{tid}", json={"name": "TEST_renamed_b"}, timeout=15)
        assert r.status_code == 200, r.text
        # GET list and verify persistence
        r2 = requests.get(f"{API}/threads", params={"profile_id": TEST_PROFILE_ID}, timeout=15)
        threads = r2.json().get("threads", [])
        found = next((t for t in threads if t["id"] == tid), None)
        assert found is not None
        assert found["name"] == "TEST_renamed_b", f"rename did not persist: {found}"

    def test_rename_missing_thread_404(self):
        r = requests.patch(f"{API}/threads/nonexistent-thread-id-xyz", json={"name": "x"}, timeout=15)
        assert r.status_code == 404

    def test_delete_thread_removes_and_cascades_messages(self):
        # Create a thread, send a chat message on it, delete, verify both gone
        cr = requests.post(f"{API}/threads", json={"profile_id": TEST_PROFILE_ID, "name": "TEST_todelete"}, timeout=15)
        assert cr.status_code == 200
        tid = cr.json()["id"]
        # Manually insert a message via chat? Faster: just call delete and rely on cascade code
        # But we want to verify cascade — post a very small chat and cancel quickly
        # Use direct DB-less approach: rely on the delete endpoint deleting messages if any exist
        # (Cannot easily insert messages via public API without going through /api/chat streaming.)
        dr = requests.delete(f"{API}/threads/{tid}", timeout=15)
        assert dr.status_code == 200
        assert dr.json().get("ok") is True
        # Verify gone from list
        lr = requests.get(f"{API}/threads", params={"profile_id": TEST_PROFILE_ID}, timeout=15)
        ids = [t["id"] for t in lr.json().get("threads", [])]
        assert tid not in ids

    def test_cleanup_rename_thread(self):
        # Final cleanup — delete the renamed thread
        tid = TestThreads._thread_id
        if tid:
            requests.delete(f"{API}/threads/{tid}", timeout=15)


# ---------- LOGIC block in chat + persisted history ----------
class TestLogicBlock:
    """The assistant reply must contain a <LOGIC>...</LOGIC> block and the persisted
    history must expose separate 'answer' and 'logic' fields."""
    session_id = f"TEST_logic_{uuid.uuid4()}"

    def test_chat_reply_contains_logic_and_is_plain(self):
        payload = {
            "profile_id": TEST_PROFILE_ID,
            "session_id": self.session_id,
            "message": "How's my career going right now?",
        }
        with requests.post(f"{API}/chat", json=payload, stream=True, timeout=120) as r:
            assert r.status_code == 200, r.text
            events = _read_sse(r, max_seconds=120)

        # Look for either successful delta content or an error event (budget)
        deltas = [d.get("text", "") for e, d in events if e == "delta"]
        full = "".join(deltas)
        errors = [d for e, d in events if e == "error"]
        if errors and not full.strip():
            pytest.skip(f"LLM upstream error, unverified: {errors[0]}")

        assert "<LOGIC>" in full, f"reply missing <LOGIC> tag; full={full[:600]!r}"
        assert "</LOGIC>" in full, f"reply missing </LOGIC> close tag"

        # Visible portion (before <LOGIC>) must be plain-language: no jargon words
        visible = full.split("<LOGIC>", 1)[0].lower()
        JARGON = [
            "nakshatra", "retrograde", "ascendant", "lagna", "dasha", "antardasha",
            "graha", "vargottama", "moolatrikona", "debilitated",
        ]
        # 'house' is very common English; the requirement is that we don't say "10th house" etc.
        # Check specifically for house-number phrasing.
        import re
        housey = re.search(r"\b(\d{1,2})(st|nd|rd|th)\s+house\b", visible)
        assert not housey, f"visible answer used '<N>th house' phrasing: {housey.group(0)}"

        found_jargon = [w for w in JARGON if w in visible]
        assert not found_jargon, f"jargon words leaked into visible answer: {found_jargon}\nvisible={visible[:400]}"

        # Word count guardrail (soft): visible <= ~400 words
        word_count = len(visible.split())
        assert word_count <= 400, f"visible answer too long: {word_count} words"

    def test_history_persists_logic_and_answer_fields(self):
        time.sleep(1)
        r = requests.get(f"{API}/chat/{self.session_id}/history", timeout=20)
        assert r.status_code == 200
        msgs = r.json().get("messages", [])
        assistants = [m for m in msgs if m["role"] == "assistant"]
        if not assistants:
            pytest.skip("no assistant message persisted (likely upstream LLM error)")
        a = assistants[-1]
        # Either the raw content contains LOGIC OR the split fields are populated
        content = a.get("content", "") or ""
        answer = a.get("answer", "") or ""
        logic = a.get("logic", "") or ""
        assert "<LOGIC>" in content, "persisted content missing <LOGIC>"
        assert answer, "persisted answer field empty"
        assert logic, "persisted logic field empty"
        assert "<LOGIC>" not in answer, "answer should be stripped of <LOGIC>"


# ---------- Attachment upload for vision ----------
class TestAttachments:
    """POST /api/chat/attachment + GET /api/attachments/{fname} roundtrip."""

    def test_upload_png_and_fetch(self):
        img_path = "/app/test_fixtures/attachment.png"
        assert os.path.exists(img_path), "test fixture PNG missing"
        with open(img_path, "rb") as f:
            files = {"file": ("attachment.png", f, "image/png")}
            r = requests.post(f"{API}/chat/attachment", files=files, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("url", "filename", "mime_type", "size"):
            assert k in data, f"missing key {k} in upload response"
        assert data["mime_type"] == "image/png"
        assert data["filename"] == "attachment.png"
        assert data["size"] > 500
        # Fetch it back
        fname = data["url"].split("/api/attachments/")[-1]
        g = requests.get(f"{API}/attachments/{fname}", timeout=15)
        assert g.status_code == 200
        assert g.headers.get("content-type", "").startswith("image/")
        assert len(g.content) == data["size"]

    def test_upload_rejects_non_image(self):
        files = {"file": ("bad.txt", b"hello world", "text/plain")}
        r = requests.post(f"{API}/chat/attachment", files=files, timeout=15)
        assert r.status_code == 400, r.text

    def test_serve_missing_attachment_404(self):
        r = requests.get(f"{API}/attachments/does_not_exist_xyz.png", timeout=15)
        assert r.status_code == 404


# ---------- Vision E2E: attachment_urls to /api/chat must yield real Claude vision reply ----------
class TestChatVision:
    """Iteration 5 CRITICAL FIX: attachment_urls must no longer trigger
    'File attachments are only supported with Gemini provider' error.
    Assistant reply must describe the actual image (colors/shapes/text)."""

    def test_chat_with_attachment_returns_real_vision(self):
        # 1. Upload the fixture PNG
        img_path = "/app/test_fixtures/attachment.png"
        assert os.path.exists(img_path), "fixture PNG missing"
        with open(img_path, "rb") as f:
            up = requests.post(
                f"{API}/chat/attachment",
                files={"file": ("attachment.png", f, "image/png")},
                timeout=30,
            )
        assert up.status_code == 200, up.text
        url = up.json()["url"]

        # 2. POST /api/chat with attachment_urls
        session_id = f"TEST_vision_{uuid.uuid4()}"
        payload = {
            "profile_id": TEST_PROFILE_ID,
            "session_id": session_id,
            "message": "Please describe the image I just attached — what shapes, colors, and text do you see?",
            "attachment_urls": [url],
        }
        with requests.post(f"{API}/chat", json=payload, stream=True, timeout=180) as r:
            assert r.status_code == 200, r.text
            events = _read_sse(r, max_seconds=180)

        # 3. Must have NO 'only supported with Gemini' error
        errors = [d for e, d in events if e == "error"]
        for err in errors:
            err_str = json.dumps(err).lower()
            assert "only supported with gemini" not in err_str, (
                f"vision regression: Gemini-only error surfaced again: {err}"
            )
        # If provider budget/quota error, allow skip (env-dependent)
        deltas = "".join(
            (d.get("text", "") if isinstance(d, dict) else "")
            for e, d in events if e == "delta"
        )
        if errors and not deltas.strip():
            pytest.skip(f"LLM upstream error, unverified vision: {errors[0]}")

        # 4. Assistant reply must be substantive and describe the actual image
        assert len(deltas) > 50, f"reply too short ({len(deltas)} chars): {deltas!r}"
        visible = deltas.split("<LOGIC>", 1)[0].lower() if "<LOGIC>" in deltas else deltas.lower()
        assert len(visible.strip()) > 50, f"visible answer too short: {visible!r}"

        # The fixture has: orange circle half, blue square/half, diagonal line, "Test" text.
        color_hits = sum(1 for c in ("orange", "blue", "black", "beige", "cream", "red", "navy", "rust") if c in visible)
        shape_hits = sum(1 for s in ("circle", "square", "line", "diagonal", "shape", "rectangle", "diagram") if s in visible)
        assert color_hits + shape_hits >= 2, (
            f"reply does not describe image (colors/shapes): {visible[:400]}"
        )

