"""
Sanatan Shastra knowledge base — v2: self-hosted embeddings + BM25 hybrid
search. Real book content lives in Mongo (db.seed_chunks) instead of a
hardcoded 20-snippet list (knowledge.py) or a third-party API
(knowledge_v1.py's VedAstro call) — this is the first version that's
both fully owned and scalable to real book corpora.

SCALABILITY: the seed corpus is a Mongo collection, not Python code — so
adding chunk #2 or #1000 is a database insert via the admin ingestion
endpoint in server.py, never a code change or redeploy.

RETRIEVAL: BM25 (exact terminology) + cosine similarity over self-hosted
embeddings (semantic/paraphrase matching), fused by Reciprocal Rank
Fusion — same RRF technique knowledge_v1.py already used, reused here
because it's the right tool regardless of which two rankers it's fusing.

PERFORMANCE CEILING: cosine similarity is brute-forced in numpy across
every seed chunk per query. Fine through the low thousands of chunks —
a full multi-book classical corpus. Past roughly 50-100k chunks this
needs a real vector index (e.g. Mongo Atlas Vector Search) instead of
this simple approach — worth revisiting if the corpus grows that large.
"""
from __future__ import annotations
from typing import List, Dict, Optional, Set
import uuid
import numpy as np

from knowledge import extract_pdf_chunks, _tokenize, detect_book_scope
from embeddings import embed_texts, embed_query
from rank_bm25 import BM25Okapi

SEED_CORPUS: List[Dict] = []  # kept empty for import compatibility; real seed data lives in Mongo now
MIN_CHUNK_LEN = 20  # verses/phrases can be short — don't silently drop them like the 80-char PDF filter does


async def add_seed_chunk(db, book: str, chapter: str, text: str) -> Dict:
    """Add ONE chunk — a single verse, phrase, or paragraph, any granularity."""
    text = text.strip()
    if len(text) < MIN_CHUNK_LEN:
        return {"added": False, "reason": f"text shorter than {MIN_CHUNK_LEN} chars"}
    vector = embed_texts([text])[0]
    await db.seed_chunks.insert_one({
        "book": book, "chapter": chapter, "text": text,
        "embedding": vector, "is_seed": True, "book_id": "seed",
    })
    return {"added": True, "book": book, "chapter": chapter}


async def add_seed_chunks_bulk(db, chunks: List[Dict]) -> Dict:
    """chunks: [{"book":, "chapter":, "text":}, ...] — 1 to thousands.
    Embeds as one batch call (much faster than one-by-one), then one bulk insert."""
    valid = [c for c in chunks if len(c.get("text", "").strip()) >= MIN_CHUNK_LEN]
    skipped = len(chunks) - len(valid)
    if not valid:
        return {"added": 0, "skipped": skipped}
    vectors = embed_texts([c["text"].strip() for c in valid])
    docs = [
        {"book": c["book"], "chapter": c.get("chapter", ""), "text": c["text"].strip(),
         "embedding": vec, "is_seed": True, "book_id": "seed"}
        for c, vec in zip(valid, vectors)
    ]
    await db.seed_chunks.insert_many(docs)
    return {"added": len(docs), "skipped": skipped}


def _cosine_order(query_vec: List[float], chunks: List[Dict]) -> List[int]:
    if not chunks:
        return []
    mat = np.array([c["embedding"] for c in chunks])
    scores = mat @ np.array(query_vec)
    return list(np.argsort(-scores))


def _hybrid_rank(pool: List[Dict], query: str, query_vec: List[float]) -> List[Dict]:
    if not pool:
        return []
    embedded = [c for c in pool if c.get("embedding")]
    vec_order = _cosine_order(query_vec, embedded)
    vec_rank = {id(embedded[i]): rank for rank, i in enumerate(vec_order)}

    toks = [_tokenize(c["text"]) for c in pool]
    bm25 = BM25Okapi(toks)
    bm25_scores = bm25.get_scores(_tokenize(query))
    bm25_rank = {
        id(pool[i]): rank
        for rank, i in enumerate(sorted(range(len(pool)), key=lambda i: bm25_scores[i], reverse=True))
        if bm25_scores[i] > 0
    }

    RRF_K = 60
    fused = []
    for c in pool:
        score = 0.0
        if id(c) in vec_rank:
            score += 1.0 / (RRF_K + vec_rank[id(c)])
        if id(c) in bm25_rank:
            score += 1.0 / (RRF_K + bm25_rank[id(c)])
        if score > 0:
            fused.append((score, c))
    fused.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in fused]


async def search_for_user(db, user_id: str, query: str, k: int = 8, book_names: Optional[Set[str]] = None) -> List[Dict]:
    if not query.strip():
        return []

    seed_pool = await db.seed_chunks.find({}, {"_id": 0}).to_list(20000)
    user_pool = await db.book_chunks.find({"user_id": user_id}, {"_id": 0}).to_list(5000)

    if book_names:
        lc = {b.lower() for b in book_names}
        seed_pool = [c for c in seed_pool if c["book"].lower() in lc or any(b in c["book"].lower() for b in lc)]
        user_pool = [c for c in user_pool if c["book"].lower() in lc or any(b in c["book"].lower() for b in lc)]

    query_vec = embed_query(query)
    seed_ranked = _hybrid_rank(seed_pool, query, query_vec)[:k]
    user_ranked = _hybrid_rank(user_pool, query, query_vec)[:k]

    out = []
    for c in (seed_ranked + user_ranked)[:k]:
        out.append({
            "book": c["book"], "chapter": c.get("chapter", ""), "text": c["text"],
            "score": 1.0, "is_seed": c.get("is_seed", False),
        })
    return out


async def list_books_for_user(db, user_id: str) -> Dict:
    seed_agg: Dict[str, Dict] = {}
    async for c in db.seed_chunks.find({}, {"_id": 0}):
        b = c["book"]
        if b not in seed_agg:
            seed_agg[b] = {"book_id": "seed", "book": b, "is_seed": True, "chunk_count": 0, "sample": c["text"][:180]}
        seed_agg[b]["chunk_count"] += 1

    custom_agg: Dict[str, Dict] = {}
    async for c in db.book_chunks.find({"user_id": user_id}, {"_id": 0}):
        bid = c.get("book_id", c["book"])
        if bid not in custom_agg:
            custom_agg[bid] = {"book_id": bid, "book": c["book"], "is_seed": False, "chunk_count": 0, "sample": c["text"][:180]}
        custom_agg[bid]["chunk_count"] += 1

    return {"seed": sorted(seed_agg.values(), key=lambda x: x["book"]), "custom": sorted(custom_agg.values(), key=lambda x: x["book"])}


async def add_pdf_for_user(db, user_id: str, filename: str, content: bytes) -> Dict:
    """User-uploaded PDFs get embedded too now, for hybrid search parity with the seed corpus."""
    chunks = extract_pdf_chunks(filename, content)
    if not chunks:
        return {"book_id": None, "chunks_added": 0}
    book_id = uuid.uuid4().hex
    vectors = embed_texts([c["text"] for c in chunks])
    docs = [
        {"user_id": user_id, "book_id": book_id, "book": filename, "chapter": c["chapter"], "text": c["text"],
         "embedding": vec, "is_seed": False}
        for c, vec in zip(chunks, vectors)
    ]
    await db.book_chunks.insert_many(docs)
    return {"book_id": book_id, "book": filename, "chunks_added": len(docs)}


async def delete_book_for_user(db, user_id: str, book_id: str) -> int:
    res = await db.book_chunks.delete_many({"user_id": user_id, "book_id": book_id})
    return res.deleted_count
