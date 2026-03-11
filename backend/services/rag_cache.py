"""
rag_cache.py — In-memory LRU cache for RAG answers.

Caches (question, document_id) → (answer, sources) pairs to avoid
repeated LLM calls for identical questions.  The cache is:
  * Process-local (not shared across uvicorn workers)
  * LRU-evicted at MAX_SIZE entries
  * Time-limited: entries expire after TTL_SECONDS

Usage
-----
    from services.rag_cache import get_cached, set_cached, cache_stats

    hit = get_cached(question, document_id)
    if hit:
        answer, chunks = hit["answer"], hit["chunks"]
    else:
        ...
        set_cached(question, document_id, answer, chunks)
"""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

# Maximum number of entries before LRU eviction.
MAX_SIZE: int = 256

# Seconds before a cache entry is considered stale.
TTL_SECONDS: int = 3600  # 1 hour

# The cache: key → {"answer": str, "chunks": List[Document], "ts": float}
_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()

# Counters for observability.
_hits: int = 0
_misses: int = 0


def _make_key(question: str, document_id: Optional[str]) -> str:
    """Stable, compact cache key from question + document scope."""
    raw = f"{question.strip().lower()}||{document_id or '__all__'}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_cached(
    question: str,
    document_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    Return the cached entry for (question, document_id), or None on miss.

    Side-effects:
      * On hit — promotes entry to MRU position; increments _hits.
      * On expired entry — removes it; falls through to None.
      * On miss — increments _misses.
    """
    global _hits, _misses
    key = _make_key(question, document_id)

    if key not in _cache:
        _misses += 1
        return None

    entry = _cache[key]
    if time.monotonic() - entry["ts"] > TTL_SECONDS:
        del _cache[key]
        _misses += 1
        return None

    # Promote to MRU.
    _cache.move_to_end(key)
    _hits += 1
    return entry


def set_cached(
    question: str,
    document_id: Optional[str],
    answer: str,
    sources: List,
    extra: Optional[dict] = None,
) -> None:
    """
    Store an answer in the cache, evicting the LRU entry if needed.

    Args:
        question:    User's question (used as part of cache key).
        document_id: Document scope (None = all documents).
        answer:      LLM-generated answer string.
        sources:     SourceChunk list for re-serving cached responses.
        extra:       Optional dict of additional fields (e.g. documents_searched,
                     retrieved_chunks, eval_metrics) to store alongside the answer.
    """
    key = _make_key(question, document_id)

    entry: Dict[str, Any] = {
        "answer": answer,
        "sources": sources,
        "ts": time.monotonic(),
        **(extra or {}),
    }

    if key in _cache:
        _cache.move_to_end(key)
    elif len(_cache) >= MAX_SIZE:
        _cache.popitem(last=False)  # evict LRU

    _cache[key] = entry


def cache_stats() -> Dict[str, Any]:
    """Return a snapshot of cache health for the /health or admin endpoint."""
    total = _hits + _misses
    return {
        "size": len(_cache),
        "max_size": MAX_SIZE,
        "hits": _hits,
        "misses": _misses,
        "hit_rate": round(_hits / total, 4) if total else 0.0,
        "ttl_seconds": TTL_SECONDS,
    }


def invalidate(question: str, document_id: Optional[str] = None) -> bool:
    """Remove a specific entry. Returns True if it was present."""
    key = _make_key(question, document_id)
    if key in _cache:
        del _cache[key]
        return True
    return False


def clear() -> None:
    """Flush the entire cache (useful in tests)."""
    global _hits, _misses
    _cache.clear()
    _hits = 0
    _misses = 0
