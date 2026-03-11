"""
evaluation.py — RAG quality evaluation utilities.

Provides lightweight, inference-free metrics that run inside the request
cycle without requiring a secondary LLM call:

  evaluate_retrieval(question_vec, chunks, scored_chunks)
      Per-chunk and aggregate retrieval quality scores.

  evaluate_response(question, answer)
      Heuristic relevance signals for the generated answer.
"""

from __future__ import annotations

import re
import string
from typing import Dict, List, Optional, Tuple

import numpy as np
from langchain_core.documents import Document

# Minimum cosine similarity to consider a chunk "relevant".
RELEVANCE_THRESHOLD = 0.30


# ---------------------------------------------------------------------------
# Retrieval metrics
# ---------------------------------------------------------------------------

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Return cosine similarity between two 1-D vectors (already L2-normed → dot product)."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a / norm_a, b / norm_b))


def evaluate_retrieval(
    scored_chunks: List[Tuple[float, Document]],
    top_k: int,
) -> Dict:
    """
    Compute aggregate retrieval quality metrics from already-scored chunks.

    Args:
        scored_chunks: List of (cosine_score, Document) sorted descending.
        top_k:         The configured retrieval limit.

    Returns:
        dict with keys:
          - retrieved_count     int   — chunks actually returned
          - relevant_count      int   — chunks above RELEVANCE_THRESHOLD
          - retrieval_precision float — relevant / retrieved_count
          - mean_score          float — average cosine similarity
          - max_score           float — best chunk similarity
          - min_score           float — worst chunk similarity
          - above_threshold     bool  — at least one chunk is above threshold
    """
    if not scored_chunks:
        return {
            "retrieved_count": 0,
            "relevant_count": 0,
            "retrieval_precision": 0.0,
            "mean_score": 0.0,
            "max_score": 0.0,
            "min_score": 0.0,
            "above_threshold": False,
        }

    scores = [s for s, _ in scored_chunks]
    relevant = [s for s in scores if s >= RELEVANCE_THRESHOLD]

    return {
        "retrieved_count": len(scores),
        "relevant_count": len(relevant),
        "retrieval_precision": round(len(relevant) / len(scores), 4) if scores else 0.0,
        "mean_score": round(float(np.mean(scores)), 4),
        "max_score": round(float(np.max(scores)), 4),
        "min_score": round(float(np.min(scores)), 4),
        "above_threshold": len(relevant) > 0,
    }


# ---------------------------------------------------------------------------
# Response relevance heuristics
# ---------------------------------------------------------------------------

_FALLBACK_PHRASES = [
    "i couldn't find",
    "not found in",
    "no information",
    "cannot be found",
    "not mentioned",
    "not provided",
    "i don't know",
    "i do not know",
]

_STOP_WORDS = frozenset(
    "a an the is are was were be been being have has had do does did "
    "will would could should may might shall can of in on at to for "
    "with by from about into through during before after above below "
    "between out off over under again further then once".split()
)


def _keywords(text: str) -> set[str]:
    """Lower-case, remove punctuation, strip stop-words."""
    text = text.lower().translate(str.maketrans("", "", string.punctuation))
    return {w for w in text.split() if w and w not in _STOP_WORDS}


def evaluate_response(question: str, answer: str) -> Dict:
    """
    Heuristic response quality signals (no LLM call required).

    Returns:
        dict with keys:
          - is_fallback          bool  — model said it couldn't find the answer
          - keyword_overlap      float — fraction of question keywords in answer
          - answer_length_words  int   — word count of the answer
          - appears_relevant     bool  — simple relevance verdict
    """
    answer_lower = answer.lower()
    is_fallback = any(phrase in answer_lower for phrase in _FALLBACK_PHRASES)

    q_kw = _keywords(question)
    a_kw = _keywords(answer)
    if q_kw:
        overlap = round(len(q_kw & a_kw) / len(q_kw), 4)
    else:
        overlap = 0.0

    word_count = len(answer.split())
    appears_relevant = (not is_fallback) and (overlap >= 0.1) and (word_count >= 10)

    return {
        "is_fallback": is_fallback,
        "keyword_overlap": overlap,
        "answer_length_words": word_count,
        "appears_relevant": appears_relevant,
    }


# ---------------------------------------------------------------------------
# Combined evaluation snapshot
# ---------------------------------------------------------------------------

def build_eval_snapshot(
    question: str,
    answer: str,
    scored_chunks: List[Tuple[float, Document]],
    top_k: int,
    latency_ms: float,
) -> Dict:
    """
    Combine all metrics into a single serialisable dict for logging.

    Args:
        question:      The user's question.
        answer:        The LLM-generated answer.
        scored_chunks: (score, Document) pairs from the retrieval step.
        top_k:         Configured retrieval limit.
        latency_ms:    End-to-end wall-clock time in milliseconds.

    Returns:
        Flat dict suitable for JSON serialisation or DB storage.
    """
    retrieval = evaluate_retrieval(scored_chunks, top_k)
    response = evaluate_response(question, answer)
    return {
        "latency_ms": round(latency_ms, 2),
        **retrieval,
        **response,
    }
