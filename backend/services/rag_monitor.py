"""
rag_monitor.py — Structured logging for the RAG pipeline.

Every /ask request produces one log entry written to:
  * logs/rag.log   (rotating JSON-lines file, kept ≤ 10 MB × 5 backups)
  * stderr         (INFO level, human-readable, for uvicorn/Docker output)

Log entry fields
----------------
timestamp       ISO-8601 UTC string
user_id         int | None
question        str
document_id     str | None
retrieved_count int
relevant_count  int
mean_score      float
max_score       float
retrieval_precision float
is_fallback     bool
keyword_overlap float
answer_length   int
appears_relevant bool
latency_ms      float
from_cache      bool
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_LOG_DIR = "logs"
_LOG_FILE = os.path.join(_LOG_DIR, "rag.log")

# ── Set up module-level loggers ───────────────────────────────────────────────

def _build_logger() -> logging.Logger:
    os.makedirs(_LOG_DIR, exist_ok=True)

    logger = logging.getLogger("rag_monitor")
    if logger.handlers:
        return logger  # already configured (e.g. on hot-reload)

    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Rotating file handler — JSON-lines format
    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)

    # Stream handler — human-readable for console / Docker logs
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s %(name)s — %(message)s",
                          datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(stream_handler)

    return logger


_logger = _build_logger()


# ── Public interface ──────────────────────────────────────────────────────────

def log_request(
    *,
    user_id: Optional[int],
    question: str,
    document_id: Optional[str],
    eval_metrics: Dict[str, Any],
    from_cache: bool = False,
) -> None:
    """
    Write one structured log entry for a completed /ask request.

    Args:
        user_id:      Authenticated user ID (None if unauthenticated path).
        question:     The user's question.
        document_id:  Target document ID, or None for all-documents search.
        eval_metrics: Dict produced by evaluation.build_eval_snapshot().
        from_cache:   True when the answer was served from the in-memory cache.
    """
    entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "question": question[:300],  # truncate for log safety
        "document_id": document_id,
        "from_cache": from_cache,
        **eval_metrics,
    }

    # Write compact JSON line to the rotating file.
    _logger.info(json.dumps(entry, ensure_ascii=False))


def log_error(
    *,
    user_id: Optional[int],
    question: str,
    error: str,
    latency_ms: float,
) -> None:
    """Log a request that ended in an error (no answer produced)."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "question": question[:300],
        "error": error,
        "latency_ms": round(latency_ms, 2),
        "from_cache": False,
    }
    _logger.error(json.dumps(entry, ensure_ascii=False))
