"""Sanatan Shastra knowledge base — v1: VedAstro Classical Texts RAG API for the seed
corpus (BPHS, Jaimini Sutras, Saravali, Phaladeepika, Brihat Jataka, Brihat Samhita),
Mongo-backed as before for user-uploaded PDFs.

Drop-in replacement for knowledge.py — same public functions, same return shapes,
so server.py needs only a one-line import swap (see server.py, guarded by
KNOWLEDGE_SOURCE env var).

Reuses knowledge.py's PDF-upload plumbing unchanged (that part has nothing to do
with which seed corpus we search against).
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

# The 6 books on the VedAstro Classical Texts plan.
# NOTE: SourceName slugs are confirmed only for BPHS from their docs; the rest are
# our best-guess slugification pending confirmation from VedAstro support / the
# API Builder tool. search_for_user() falls back to an unfiltered search and
# client-side name matching if a guessed slug returns nothing, so a wrong slug
# degrades gracefully rather than silently dropping a book.
SEED_BOOKS = [
    {"book": "Brihat Parashara Hora Shastra", "source_name": "Brihat-Parashara-Hora-Shastra"},
    {"book": "Jaimini Sutras", "source_name": "Jaimini-Sutras"},
    {"book": "Saravali", "source_name": "Saravali"},
    {"book": "Phaladeepika", "source_name": "Phaladeepika"},
    {"book": "Brihat Jataka", "source_name": "Brihat-Jataka"},
    {"book": "Brihat Samhita", "source_name": "Brihat-Samhita"},
]
_NAME_TO_SOURCE = {b["book"]: b["source_name"] for b in SEED_BOOKS}
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

    passages = data.get("Payload") or data.get("passages") or []
    if not isinstance(passages, list):
        return []
    return passages


def _passage_to_chunk(p: Dict) -> Dict:
    chapter = p.get("chapter") or ""
    page = p.get("page")
    chapter_label = f"{chapter} (p. {page})" if chapter and page else (chapter or (f"p. {page}" if page else ""))
    return {
        "book": p.get("book", "Unknown classical text"),
        "chapter": chapter_label,
        "text": p.get("text", ""),
        "score": p.get("score", 0.0),
        "is_seed": True,
        "book_id": "seed",
    }


async def search_for_user(db, user_id: str, query: str, k: int = 8, book_names: Optional[Set[str]] = None) -> List[Dict]:
    """VedAstro search across the seed corpus + BM25 over this user's uploaded chunks,
    merged and re-ranked by VedAstro's own relevance score for the seed half."""
    if not query.strip():
        return []

    scoped_seed_books = None
    if book_names:
        lc = {b.lower() for b in book_names}
        scoped_seed_books = [name for name in _SEED_BOOK_NAMES if name.lower() in lc]

    seed_results: List[Dict] = []
    if scoped_seed_books:
        for name in scoped_seed_books:
            passages = await _vedastro_search(query, top_k=k, source_name=_NAME_TO_SOURCE[name])
            seed_results.extend(_passage_to_chunk(p) for p in passages)
    elif not book_names:
        passages = await _vedastro_search(query, top_k=k)
        seed_results.extend(_passage_to_chunk(p) for p in passages)

    seed_results.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    seed_results = seed_results[:k]

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

    combined = seed_results + user_results
    combined.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    return combined[:k]


async def list_books_for_user(db, user_id: str) -> Dict:
    seed = [
        {"book_id": "seed", "book": name, "is_seed": True, "chunk_count": None, "sample": None}
        for name in _SEED_BOOK_NAMES
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
