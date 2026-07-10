"""Seed corpus of Vedic astrology wisdom + BM25 retrieval + PDF ingestion."""
from __future__ import annotations
from rank_bm25 import BM25Okapi
from typing import List, Dict
import re
import io
from pypdf import PdfReader

# ---- Seed corpus: excerpts inspired by classical Jyotish texts ----
# Note: All excerpts are paraphrased summaries for educational context.
SEED_CORPUS: List[Dict] = [
    {
        "book": "Brihat Parashara Hora Shastra",
        "chapter": "Ch. 3 — Grahaguna Swarupa Adhyaya",
        "text": "The Sun (Surya) is the atma-karaka, signifying self, soul, father, government, authority, and vitality. A strong Sun in the 10th house grants royal status, leadership and public recognition; when debilitated in Libra or afflicted, one may struggle with self-worth and paternal relationships.",
    },
    {
        "book": "Brihat Parashara Hora Shastra",
        "chapter": "Ch. 3 — Grahaguna Swarupa Adhyaya",
        "text": "The Moon (Chandra) governs the mind (manas), mother, emotions, water, and the general public. Purnima-born natives have expansive minds; those born near Amavasya may battle mental restlessness. Moon in Kendra (1,4,7,10) grants renown and comfort.",
    },
    {
        "book": "Brihat Parashara Hora Shastra",
        "chapter": "Ch. 7 — Kalachakra Dasha",
        "text": "The Mahadasha of the Nakshatra lord at birth unfolds first. Vimshottari totals 120 years across nine lords: Ketu 7, Venus 20, Sun 6, Moon 10, Mars 7, Rahu 18, Jupiter 16, Saturn 19, Mercury 17. The Antardasha lords cycle within the Mahadasha in the same proportional order.",
    },
    {
        "book": "Brihat Parashara Hora Shastra",
        "chapter": "Ch. 10 — Karakas & Yogas",
        "text": "Gaja Kesari Yoga forms when Jupiter is in a Kendra from the Moon, granting eloquence, virtue and prosperity. Chandra Mangala Yoga (Moon-Mars conjunction) creates wealth through effort but with volatility of temperament.",
    },
    {
        "book": "Phaladeepika (Mantreswara)",
        "chapter": "Ch. 6 — Bhavaphala",
        "text": "The 10th house (Karma Bhava) rules livelihood, status, and karma yoga. Its lord placed in Kendra or Trikona from lagna, with strength, ensures a rising career. Saturn as 10th lord bestows steady long-term work; Sun brings authority; Mercury commerce and communication.",
    },
    {
        "book": "Phaladeepika (Mantreswara)",
        "chapter": "Ch. 9 — Aspects (Drishti)",
        "text": "Every planet aspects the 7th house from itself. Mars additionally aspects the 4th and 8th; Jupiter aspects the 5th and 9th; Saturn aspects the 3rd and 10th. Jupiter's aspect on lagna or Moon is a great protector, softening malefic influences.",
    },
    {
        "book": "Saravali (Kalyana Varma)",
        "chapter": "Ch. 5 — Effects of Planets in Signs",
        "text": "Saturn in Aquarius or Capricorn (own sign) makes the native disciplined, hardworking, and long-lived, with success achieved through perseverance in old age. Saturn in Libra (exaltation) grants justice-oriented career and public trust.",
    },
    {
        "book": "Saravali (Kalyana Varma)",
        "chapter": "Ch. 35 — Raja Yogas",
        "text": "When the lords of a Kendra (1,4,7,10) and a Trikona (1,5,9) associate — by conjunction, mutual aspect, or exchange — a Raja Yoga is formed. Such natives rise to positions of power, respect, and material comfort.",
    },
    {
        "book": "Jaimini Sutras",
        "chapter": "Ch. 1 — Chara Karakas",
        "text": "The Atmakaraka is the planet with the highest degree in a chart, signifying the soul's purpose. The Amatyakaraka governs career and counsel; the Darakaraka the spouse. Study the Atmakaraka's placement in the Navamsa (D9) to understand dharma.",
    },
    {
        "book": "Hora Sara (Prithuyasas)",
        "chapter": "Ch. 4 — Yogas of Wealth",
        "text": "Dhana Yoga arises when the lords of the 2nd (kutumba, wealth) and 11th (labha, gains) are strong and connect with the 5th or 9th lord. The Lakshmi Yoga forms when Venus and the 9th lord are exalted or in own signs, promising abundance.",
    },
    {
        "book": "Uttara Kalamrita (Kalidasa)",
        "chapter": "Kanda 4 — Significations",
        "text": "Jupiter (Guru/Brihaspati) signifies wisdom, dharma, children, husband (for women), spirituality, and expansion. When Jupiter transits the 5th, 9th or 11th from natal Moon, it activates gain, learning, and progeny (Sadhe Sati of Guru is auspicious).",
    },
    {
        "book": "Uttara Kalamrita (Kalidasa)",
        "chapter": "Kanda 4 — Significations",
        "text": "Rahu represents obsession, foreign lands, technology, unconventional gains, and shadowy desires. In the 10th house Rahu can grant sudden career elevation through non-traditional means; in the 12th it drives foreign settlement or spiritual dissolution.",
    },
    {
        "book": "Brihat Jataka (Varahamihira)",
        "chapter": "Ch. 12 — Rajayoga Adhyaya",
        "text": "The exchange (Parivartana) of lords between a Kendra and Trikona house creates one of the highest Raja Yogas. Such an exchange indicates a lifetime of dignified achievement, especially when either lord is in dignity.",
    },
    {
        "book": "Brihat Jataka (Varahamihira)",
        "chapter": "Ch. 18 — Effects of the Sub-periods",
        "text": "During the Antardasha of a benefic that is well-placed in the natal chart, the native experiences favorable results tied to that planet's significations. Conversely, an afflicted planet's Antardasha within a difficult Mahadasha requires caution and remedies.",
    },
    {
        "book": "Prashna Marga",
        "chapter": "Ch. 2 — Timing of Events",
        "text": "Transits (Gochara) are read from the natal Moon (Chandra Lagna). Saturn's Sade Sati — its transit through the 12th, 1st and 2nd houses from Moon — spans about 7.5 years and demands restraint, karmic settling, and inner reformation.",
    },
    {
        "book": "Prashna Marga",
        "chapter": "Ch. 3 — Remedies",
        "text": "Classical remedies (upayas) include mantra japa of the ruling planet, wearing prescribed gemstones only when the planet is a benefic yogakaraka, charity (dana) on the planet's day, and worship of the associated deity: Sun-Surya, Moon-Parvati, Mars-Hanuman, Mercury-Vishnu, Jupiter-Brihaspati/Vishnu, Venus-Lakshmi, Saturn-Shani/Hanuman, Rahu-Durga, Ketu-Ganesha.",
    },
    {
        "book": "Chamatkar Chintamani (Bhatta Narayana)",
        "chapter": "Ch. 3 — Planets in Houses",
        "text": "Venus in the 7th house makes the native attractive, blessed with a beautiful spouse and pleasures of married life, provided Venus is unafflicted. Mars in the 7th (Kuja Dosha) can bring conflict in marriage unless matched with a similarly placed partner.",
    },
    {
        "book": "Laghu Parashari (Jataka Chandrika)",
        "chapter": "Sutra 12 — Yogakarakas",
        "text": "For Vrishabha (Taurus) and Tula (Libra) lagnas, Saturn becomes the yogakaraka as the lord of Kendra (4/10) and Trikona (5/9). For Karka (Cancer) and Simha (Leo) lagnas, Mars is the yogakaraka. Their dashas typically bring life-changing prosperity.",
    },
    {
        "book": "Muhurta Chintamani",
        "chapter": "Ch. 4 — Auspicious Timing",
        "text": "Begin new ventures during Shukla Paksha (waxing moon), preferably on days ruled by benefics: Thursday (Jupiter) for education/marriage, Friday (Venus) for luxury and art, Wednesday (Mercury) for business. Avoid Rahu Kala and eclipses.",
    },
    {
        "book": "Nadi Jyotisha (compiled)",
        "chapter": "Traditional Verse",
        "text": "The Navamsa (D9) reveals the fruits of the Rasi chart in the second half of life. A planet debilitated in Rasi but exalted in Navamsa (neechabhanga) recovers strength and yields excellent results during its dasha. Marriage matters are exclusively judged from D9.",
    },
]


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class KnowledgeBase:
    def __init__(self):
        self.chunks: List[Dict] = list(SEED_CORPUS)
        self._rebuild()

    def _rebuild(self):
        self._tokens = [_tokenize(c["text"]) for c in self.chunks]
        self._bm25 = BM25Okapi(self._tokens) if self._tokens else None

    def add_pdf(self, filename: str, content: bytes) -> int:
        """Extract text from PDF and add as chunks. Returns number of chunks added."""
        reader = PdfReader(io.BytesIO(content))
        added = 0
        for page_no, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            # split large pages into ~1200-char paragraphs
            for para in _split_text(text, 1200):
                if len(para) < 80:
                    continue
                self.chunks.append({
                    "book": filename,
                    "chapter": f"Page {page_no}",
                    "text": para,
                })
                added += 1
        self._rebuild()
        return added

    def search(self, query: str, k: int = 5) -> List[Dict]:
        if not self._bm25 or not query.strip():
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [
            {**self.chunks[i], "score": float(scores[i])}
            for i in ranked[:k] if scores[i] > 0
        ]

    def list_books(self) -> List[Dict]:
        # Aggregate by book name
        agg: Dict[str, Dict] = {}
        for c in self.chunks:
            b = c["book"]
            if b not in agg:
                agg[b] = {"book": b, "chunk_count": 0, "sample": c["text"][:200]}
            agg[b]["chunk_count"] += 1
        return sorted(agg.values(), key=lambda x: x["book"])


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


# global singleton
KB = KnowledgeBase()
