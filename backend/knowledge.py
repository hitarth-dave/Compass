"""Sanatan Shastra knowledge base — seed corpus + user PDF uploads (Mongo-backed).
Supports per-user retrieval and optional book-name filtering (per-message scoping)."""
from __future__ import annotations
from rank_bm25 import BM25Okapi
from typing import List, Dict, Optional, Set
import re
import io
import uuid
from pypdf import PdfReader

# ---- Seed corpus (paraphrased educational excerpts from classical Vedic texts) ----
SEED_CORPUS: List[Dict] = [
    {"book": "Brihat Parashara Hora Shastra", "chapter": "Ch. 3 — Grahaguna Swarupa Adhyaya",
     "text": "The Sun (Surya) is the atma-karaka, signifying self, soul, father, government, authority, and vitality. A strong Sun in the 10th house grants royal status, leadership and public recognition; when debilitated in Libra or afflicted, one may struggle with self-worth and paternal relationships."},
    {"book": "Brihat Parashara Hora Shastra", "chapter": "Ch. 3 — Grahaguna Swarupa Adhyaya",
     "text": "The Moon (Chandra) governs the mind (manas), mother, emotions, water, and the general public. Purnima-born natives have expansive minds; those born near Amavasya may battle mental restlessness. Moon in Kendra (1,4,7,10) grants renown and comfort."},
    {"book": "Brihat Parashara Hora Shastra", "chapter": "Ch. 7 — Kalachakra Dasha",
     "text": "The Mahadasha of the Nakshatra lord at birth unfolds first. Vimshottari totals 120 years across nine lords: Ketu 7, Venus 20, Sun 6, Moon 10, Mars 7, Rahu 18, Jupiter 16, Saturn 19, Mercury 17."},
    {"book": "Brihat Parashara Hora Shastra", "chapter": "Ch. 10 — Karakas & Yogas",
     "text": "Gaja Kesari Yoga forms when Jupiter is in a Kendra from the Moon, granting eloquence, virtue and prosperity. Chandra Mangala Yoga (Moon-Mars conjunction) creates wealth through effort but with volatility of temperament."},
    {"book": "Phaladeepika (Mantreswara)", "chapter": "Ch. 6 — Bhavaphala",
     "text": "The 10th house (Karma Bhava) rules livelihood, status, and karma yoga. Its lord placed in Kendra or Trikona from lagna, with strength, ensures a rising career. Saturn as 10th lord bestows steady long-term work; Sun brings authority; Mercury commerce and communication."},
    {"book": "Phaladeepika (Mantreswara)", "chapter": "Ch. 9 — Aspects (Drishti)",
     "text": "Every planet aspects the 7th house from itself. Mars additionally aspects the 4th and 8th; Jupiter aspects the 5th and 9th; Saturn aspects the 3rd and 10th. Jupiter's aspect on lagna or Moon is a great protector."},
    {"book": "Saravali (Kalyana Varma)", "chapter": "Ch. 5 — Effects of Planets in Signs",
     "text": "Saturn in Aquarius or Capricorn (own sign) makes the native disciplined, hardworking, and long-lived, with success achieved through perseverance. Saturn in Libra (exaltation) grants justice-oriented career and public trust."},
    {"book": "Saravali (Kalyana Varma)", "chapter": "Ch. 35 — Raja Yogas",
     "text": "When the lords of a Kendra (1,4,7,10) and a Trikona (1,5,9) associate — by conjunction, mutual aspect, or exchange — a Raja Yoga is formed. Such natives rise to positions of power, respect, and material comfort."},
    {"book": "Jaimini Sutras", "chapter": "Ch. 1 — Chara Karakas",
     "text": "The Atmakaraka is the planet with the highest degree in a chart, signifying the soul's purpose. The Amatyakaraka governs career and counsel; the Darakaraka the spouse. Study the Atmakaraka's placement in the Navamsa (D9) to understand dharma."},
    {"book": "Hora Sara (Prithuyasas)", "chapter": "Ch. 4 — Yogas of Wealth",
     "text": "Dhana Yoga arises when the lords of the 2nd (kutumba, wealth) and 11th (labha, gains) are strong and connect with the 5th or 9th lord. Lakshmi Yoga forms when Venus and the 9th lord are exalted or in own signs, promising abundance."},
    {"book": "Uttara Kalamrita (Kalidasa)", "chapter": "Kanda 4 — Significations",
     "text": "Jupiter (Guru/Brihaspati) signifies wisdom, dharma, children, husband (for women), spirituality, and expansion. When Jupiter transits the 5th, 9th or 11th from natal Moon, it activates gain, learning, and progeny."},
    {"book": "Uttara Kalamrita (Kalidasa)", "chapter": "Kanda 4 — Significations",
     "text": "Rahu represents obsession, foreign lands, technology, unconventional gains, and shadowy desires. In the 10th house Rahu can grant sudden career elevation through non-traditional means; in the 12th it drives foreign settlement or spiritual dissolution."},
    {"book": "Brihat Jataka (Varahamihira)", "chapter": "Ch. 12 — Rajayoga Adhyaya",
     "text": "The exchange (Parivartana) of lords between a Kendra and Trikona house creates one of the highest Raja Yogas. Such an exchange indicates a lifetime of dignified achievement, especially when either lord is in dignity."},
    {"book": "Brihat Jataka (Varahamihira)", "chapter": "Ch. 18 — Effects of the Sub-periods",
     "text": "During the Antardasha of a benefic that is well-placed in the natal chart, the native experiences favorable results tied to that planet's significations. Conversely, an afflicted planet's Antardasha within a difficult Mahadasha requires caution and remedies."},
    {"book": "Prashna Marga", "chapter": "Ch. 2 — Timing of Events",
     "text": "Transits (Gochara) are read from the natal Moon (Chandra Lagna). Saturn's Sade Sati — its transit through the 12th, 1st and 2nd houses from Moon — spans about 7.5 years and demands restraint, karmic settling, and inner reformation."},
    {"book": "Prashna Marga", "chapter": "Ch. 3 — Remedies",
     "text": "Classical remedies (upayas) include mantra japa of the ruling planet, wearing prescribed gemstones only when the planet is a benefic yogakaraka, charity (dana) on the planet's day, and worship of the associated deity: Sun-Surya, Moon-Parvati, Mars-Hanuman, Mercury-Vishnu, Jupiter-Brihaspati/Vishnu, Venus-Lakshmi, Saturn-Shani/Hanuman, Rahu-Durga, Ketu-Ganesha."},
    {"book": "Chamatkar Chintamani (Bhatta Narayana)", "chapter": "Ch. 3 — Planets in Houses",
     "text": "Venus in the 7th house makes the native attractive, blessed with a beautiful spouse and pleasures of married life, provided Venus is unafflicted. Mars in the 7th (Kuja Dosha) can bring conflict in marriage unless matched with a similarly placed partner."},
    {"book": "Laghu Parashari (Jataka Chandrika)", "chapter": "Sutra 12 — Yogakarakas",
     "text": "For Vrishabha (Taurus) and Tula (Libra) lagnas, Saturn becomes the yogakaraka as the lord of Kendra (4/10) and Trikona (5/9). For Karka (Cancer) and Simha (Leo) lagnas, Mars is the yogakaraka. Their dashas typically bring life-changing prosperity."},
    {"book": "Muhurta Chintamani", "chapter": "Ch. 4 — Auspicious Timing",
     "text": "Begin new ventures during Shukla Paksha (waxing moon), preferably on days ruled by benefics: Thursday (Jupiter) for education/marriage, Friday (Venus) for luxury and art, Wednesday (Mercury) for business. Avoid Rahu Kala and eclipses."},
    {"book": "Nadi Jyotisha (compiled)", "chapter": "Traditional Verse",
     "text": "The Navamsa (D9) reveals the fruits of the Rasi chart in the second half of life. A planet debilitated in Rasi but exalted in Navamsa (neechabhanga) recovers strength and yields excellent results during its dasha. Marriage matters are exclusively judged from D9."},
]

# tag every seed chunk
for _c in SEED_CORPUS:
    _c["is_seed"] = True
    _c["book_id"] = "seed"


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _split_text(text: str, max_len: int) -> List[str]:
    out: List[str] = []
    buf = ""
    for para in re.split(r"\n\s*\n", text):
        if len(buf) + len(para) < max_len:
            buf += ("\n\n" if buf else "") + para
        else:
            if buf:
                out.append(buf)
            buf = para
    if buf:
        out.append(buf)
    return out


def extract_pdf_chunks(filename: str, content: bytes) -> List[Dict]:
    """Extract text chunks from a PDF. Returns list of {book, chapter, text}."""
    reader = PdfReader(io.BytesIO(content))
    out = []
    for page_no, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        for para in _split_text(text, 1200):
            if len(para) < 80:
                continue
            out.append({"book": filename, "chapter": f"Page {page_no}", "text": para})
    return out


async def search_for_user(db, user_id: str, query: str, k: int = 8, book_names: Optional[Set[str]] = None) -> List[Dict]:
    """BM25 search across seed corpus + this user's uploaded chunks.
    If book_names is provided, restrict to those book names (case-insensitive)."""
    # User custom chunks
    user_chunks = await db.book_chunks.find({"user_id": user_id}, {"_id": 0}).to_list(5000)
    pool = list(SEED_CORPUS) + user_chunks
    if book_names:
        lc = {b.lower() for b in book_names}
        pool = [c for c in pool if c["book"].lower() in lc or any(b in c["book"].lower() for b in lc)]
    if not pool or not query.strip():
        return []
    toks = [_tokenize(c["text"]) for c in pool]
    bm25 = BM25Okapi(toks)
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [{**pool[i], "score": float(scores[i])} for i in ranked[:k] if scores[i] > 0]


async def list_books_for_user(db, user_id: str) -> Dict:
    """Aggregate seed corpus books + user's uploaded books."""
    seed_agg: Dict[str, Dict] = {}
    for c in SEED_CORPUS:
        b = c["book"]
        if b not in seed_agg:
            seed_agg[b] = {"book_id": "seed", "book": b, "is_seed": True, "chunk_count": 0, "sample": c["text"][:180]}
        seed_agg[b]["chunk_count"] += 1

    custom_agg: Dict[str, Dict] = {}
    async for c in db.book_chunks.find({"user_id": user_id}, {"_id": 0}):
        bid = c.get("book_id", c["book"])
        if bid not in custom_agg:
            custom_agg[bid] = {
                "book_id": bid,
                "book": c["book"],
                "is_seed": False,
                "chunk_count": 0,
                "sample": c["text"][:180],
            }
        custom_agg[bid]["chunk_count"] += 1

    return {
        "seed": sorted(seed_agg.values(), key=lambda x: x["book"]),
        "custom": sorted(custom_agg.values(), key=lambda x: x["book"]),
    }


async def add_pdf_for_user(db, user_id: str, filename: str, content: bytes) -> Dict:
    """Extract PDF, store chunks in Mongo under this user_id."""
    chunks = extract_pdf_chunks(filename, content)
    if not chunks:
        return {"book_id": None, "chunks_added": 0}
    book_id = uuid.uuid4().hex
    docs = [{"user_id": user_id, "book_id": book_id, "book": filename, "chapter": c["chapter"], "text": c["text"], "is_seed": False} for c in chunks]
    await db.book_chunks.insert_many(docs)
    return {"book_id": book_id, "book": filename, "chunks_added": len(docs)}


async def delete_book_for_user(db, user_id: str, book_id: str) -> int:
    """Delete a user's custom book and all its indexed chunks. Returns chunks removed."""
    res = await db.book_chunks.delete_many({"user_id": user_id, "book_id": book_id})
    return res.deleted_count


def detect_book_scope(message: str, available_book_names: List[str]) -> Optional[Set[str]]:
    """Parse the user message for an explicit book reference.
    Only match if the message contains a phrase like 'from X', 'as per X', 'according to X',
    'in X', 'using X', '@X' — where X (case-insensitively) matches one of the available book names
    (full or a distinctive keyword like 'Phaladeepika', 'BPHS', 'Parashara')."""
    if not message:
        return None
    m_lower = message.lower()

    trigger_pattern = re.compile(
        r"\b(?:from|as per|according to|per|in|using|based on|only from|from the)\b\s+([A-Za-z][^,.?!\n]{2,80})",
        re.IGNORECASE,
    )
    at_pattern = re.compile(r"@([A-Za-z][A-Za-z0-9 _'-]{2,60})")

    candidates: List[str] = []
    for m in trigger_pattern.finditer(message):
        candidates.append(m.group(1).strip())
    for m in at_pattern.finditer(message):
        candidates.append(m.group(1).strip())

    if not candidates:
        return None

    # Build book keyword index (each book gets its full name + distinctive words length>=5)
    book_index: Dict[str, str] = {}
    for name in available_book_names:
        key = name.lower()
        book_index[key] = name
        for word in re.findall(r"[A-Za-z]{5,}", name):
            book_index[word.lower()] = name

    matched = set()
    for cand in candidates:
        cand_l = cand.lower().strip()
        # direct book name substring match
        for key, name in book_index.items():
            if key in cand_l or cand_l in key:
                matched.add(name)
                break
        else:
            # keyword match against candidate word-by-word
            for word in re.findall(r"[A-Za-z]{5,}", cand):
                if word.lower() in book_index:
                    matched.add(book_index[word.lower()])
                    break
    return matched or None
