"""Sanatan Shastra knowledge base — v1: VedAstro Classical Texts RAG API for the seed
corpus, Mongo-backed as before for user-uploaded PDFs.

Drop-in replacement for knowledge.py — same public functions, same return shapes,
so server.py needs only a one-line import swap (see server.py, guarded by
KNOWLEDGE_SOURCE env var).

Reuses knowledge.py's PDF-upload plumbing unchanged (that part has nothing to do
with which seed corpus we search against).

Field mapping note (verified against the live API on 2026-07-16): VedAstro's
SearchSourceText returns {sourceName, pageNumber, chunkIndex, text, score} per
passage — NOT {book, chapter, page, score} as originally assumed. There is no
chapter field at all; page number is the only locator, so citations are shown
as "Page N" rather than a chapter name.
"""
from __future__ import annotations
from typing import List, Dict, Optional, Set
import os
import logging
import httpx

# Reuse the parts that have nothing to do with seed-book retrieval.
from knowledge import (
    extract_pdf_chunks, add_pdf_for_user, delete_book_for_user,
    detect_book_scope, _tokenize,
)
from rank_bm25 import BM25Okapi

VEDASTRO_API_KEY = os.environ.get("VEDASTRO_API_KEY", "FreeAPIUser")
VEDASTRO_BASE_URL = "https://api.vedastro.org/api/Calculate/SearchSourceText"
VEDASTRO_TIMEOUT = 8.0  # seconds — don't let a slow external call stall a chat reply

# Verified 2026-07-16 by live-querying the API directly (NOT just the marketing
# page, which lists Saravali/Brihat Samhita — those two slugs returned empty
# results in testing and are excluded until VedAstro confirms the correct slug).
# page_count is real, extracted from "page X of Y" markers embedded in the OCR
# text where available; None means not yet confirmed (shown as "Live searchable"
# rather than a guessed number).
SEED_BOOKS = [
    {"book": "Brihat Parashara Hora Shastra", "source_name": "Brihat-Parashara-Hora-Shastra", "page_count": 482},
    {"book": "Brihat Jataka", "source_name": "Brihat-Jataka", "page_count": 294},
    {"book": "Jaimini Sutras", "source_name": "Jaimini-Sutras", "page_count": 219},
    {"book": "Phaladeepika", "source_name": "Phaladeepika", "page_count": None},
    {"book": "Hindu Predictive Astrology", "source_name": "Hindu-Predictive-Astrology", "page_count": None},
    {"book": "Uttara Kalamrita", "source_name": "Uttara-Kalamrita", "page_count": None},
]
_NAME_TO_SOURCE = {b["book"]: b["source_name"] for b in SEED_BOOKS}
_SOURCE_TO_NAME = {b["source_name"]: b["book"] for b in SEED_BOOKS}
_SEED_BOOK_NAMES = [b["book"] for b in SEED_BOOKS]

# kept for compatibility with any other code importing SEED_CORPUS directly
SEED_CORPUS: List[Dict] = []


async def _vedastro_search(query: str, top_k: int, source_name: Optional[str] = None) -> List[Dict]:
    """Call VedAstro's SearchSourceText endpoint. Returns [] on any failure —
    a broken external API should degrade the chat, not break it."""
    url = f"{VEDASTRO_BASE_URL}/Query/{query}/TopK/{top_k}"
    if source_name:
        url += f"/SourceName/{source_name}"
    try:
        async with httpx.AsyncClient(timeout=VEDASTRO_TIMEOUT) as client:
            resp = await client.get(url, headers={"x-api-key": VEDASTRO_API_KEY})
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        logging.exception("VedAstro search_for_user call failed for query=%r source=%r", query, source_name)
        return []

    if data.get("Status") == "Fail":
        logging.warning("VedAstro returned Fail status: %s", data.get("Payload"))
        return []

    passages = data.get("Payload") or data.get("passages") or []
    if not isinstance(passages, list):
        return []
    return passages


def _passage_to_chunk(p: Dict) -> Dict:
    source_name = p.get("sourceName", "")
    book_name = _SOURCE_TO_NAME.get(source_name, source_name or "Unknown classical text")
    page = p.get("pageNumber")
    chapter_label = f"Page {page}" if page else ""
    return {
        "book": book_name,
        "chapter": chapter_label,
        "text": p.get("text", ""),
        "score": p.get("score", 0.0) or 0.0,
        "is_seed": True,
        "book_id": "seed",
    }


async def search_for_user(db, user_id: str, query: str, k: int = 8, book_names: Optional[Set[str]] = None) -> List[Dict]:
    """VedAstro search across the seed corpus + BM25 over this user's uploaded chunks.

    IMPORTANT: seed results (VedAstro's own relevance score, roughly 0-1) and
    custom-upload results (BM25 score, unbounded and on a totally different
    scale) are NOT comparable as raw numbers. Merging them by raw score value
    silently biases every result toward whichever scoring system happens to
    produce larger numbers for a given query — which is exactly the
    "prioritizing one source over the other" behavior we want to avoid. Both
    result lists are already sorted by relevance within their own source, so
    instead of comparing incompatible raw scores, we merge by RANK using
    Reciprocal Rank Fusion (RRF) — a standard, scale-invariant technique for
    combining heterogeneous ranked lists. A result's fused score depends only
    on how relevant it was *within its own source*, not on which scoring
    system produced a bigger number."""
    if not query.strip():
        return []

    scoped_seed_books = None
    if book_names:
        lc = {b.lower() for b in book_names}
        scoped_seed_books = [name for name in _SEED_BOOK_NAMES if name.lower() in lc]

    seed_results: List[Dict] = []
    if scoped_seed_books:
        # Explicit single/few-book scope: query each requested seed book directly.
        for name in scoped_seed_books:
            passages = await _vedastro_search(query, top_k=k, source_name=_NAME_TO_SOURCE[name])
            seed_results.extend(_passage_to_chunk(p) for p in passages)
    elif not book_names:
        # No scoping at all (book_names is None) → search the whole seed corpus.
        passages = await _vedastro_search(query, top_k=k)
        seed_results.extend(_passage_to_chunk(p) for p in passages)
    # else: book_names was provided but matched none of the seed books (likely a
    # user-uploaded book instead) — skip seed search entirely, fall through to user chunks.

    seed_results.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    seed_results = seed_results[:k]

    # User's own uploaded PDFs still use local BM25, same as before.
    user_chunks = await db.book_chunks.find({"user_id": user_id}, {"_id": 0}).to_list(5000)
    if book_names:
        lc = {b.lower() for b in book_names}
        user_chunks = [c for c in user_chunks if c["book"].lower() in lc or any(b in c["book"].lower() for b in lc)]
    user_results: List[Dict] = []
    if user_chunks:
        toks = [_tokenize(c["text"]) for c in user_chunks]
        bm25 = BM25Okapi(toks)
        scores = bm25.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        user_results = [{**user_chunks[i], "score": float(scores[i])} for i in ranked[:k] if scores[i] > 0]

    # Reciprocal Rank Fusion: fuse by position within each source's own
    # ranking (rank 0 = most relevant in that source), not by raw score.
    RRF_K = 60  # standard constant from the RRF literature
    fused: List[Dict] = []
    for rank, chunk in enumerate(seed_results):
        fused.append({**chunk, "_rrf": 1.0 / (RRF_K + rank)})
    for rank, chunk in enumerate(user_results):
        fused.append({**chunk, "_rrf": 1.0 / (RRF_K + rank)})
    fused.sort(key=lambda c: c["_rrf"], reverse=True)
    for c in fused:
        c.pop("_rrf", None)
    return fused[:k]


async def list_books_for_user(db, user_id: str) -> Dict:
    """Seed list is now the static VedAstro book list. chunk_count holds a real
    page count where we've confirmed one, otherwise None (shown as "Live
    searchable" in the UI rather than a fabricated number)."""
    seed = [
        {
            "book_id": "seed", "book": b["book"], "is_seed": True,
            "chunk_count": b["page_count"], "sample": None,
        }
        for b in SEED_BOOKS
    ]

    custom_agg: Dict[str, Dict] = {}
    async for c in db.book_chunks.find({"user_id": user_id}, {"_id": 0}):
        bid = c.get("book_id", c["book"])
        if bid not in custom_agg:
            custom_agg[bid] = {
                "book_id": bid, "book": c["book"], "is_seed": False,
                "chunk_count": 0, "sample": c["text"][:180],
            }
        custom_agg[bid]["chunk_count"] += 1

    return {
        "seed": sorted(seed, key=lambda x: x["book"]),
        "custom": sorted(custom_agg.values(), key=lambda x: x["book"]),
    }
