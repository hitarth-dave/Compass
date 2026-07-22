"""
Self-hosted sentence embeddings — no external API, no per-call cost, runs
in-process in this same backend (no separate service to deploy/maintain).

Model: sentence-transformers/all-MiniLM-L6-v2 — chosen for footprint over
quality-maximizing alternatives (~90MB, 384-dim). If this still strains
memory on deploy, the fix is upgrading the Render instance, not swapping
to a bigger model — this is already near the floor for general-purpose
embedding quality.
"""
from __future__ import annotations
from typing import List
import threading

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Batch embed. Vectors are normalized, so cosine similarity == dot product."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
    return vectors.tolist()


def embed_query(text: str) -> List[float]:
    return embed_texts([text])[0]
