"""
ask.py — POST /ask endpoint for the RAG question-answering pipeline.

Accepts a plain question (and an optional document_id), retrieves the most
relevant chunks from the FAISS vector database, and returns an LLM-generated
answer together with source excerpts (filename + page citations), timing data,
retrieval metrics, and a cache-hit indicator.
"""

import os
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import ChatHistory, Document as DBDocument, User
from models.schemas import AskRequest, AskResponse, EvalMetrics, SourceChunk
from services.evaluation import build_eval_snapshot
from services.rag_cache import get_cached, set_cached
from services.rag_monitor import log_error, log_request
from services.rag_pipeline import (
    generate_rag_answer,
    get_available_document_ids,
    retrieve_with_scores,
)

router = APIRouter()

# Clamp user-supplied top_k to this range.
_TOP_K_DEFAULT = 5
_TOP_K_MIN = 1
_TOP_K_MAX = 20


@router.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Answer a question about one or more uploaded PDFs.

    - If **document_id** is provided, only that document is searched.
    - If **document_id** is omitted, all uploaded documents are searched.
    - **top_k** (1–20) controls how many chunks are retrieved (default 5).

    Response includes:
    - answer, sources, documents_searched
    - response_time (seconds), retrieved_chunks, cache_hit
    - eval_metrics (retrieval precision, similarity scores, answer quality signals)

    Raises:
    - **400** — question is empty or top_k out of range.
    - **404** — no documents uploaded, or the specified document_id was not found.
    - **503** — OpenAI API key is not configured.
    - **500** — unexpected server error.
    """
    start = time.perf_counter()

    # --- Validate question ---
    if not request.question or not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # --- Clamp top_k ---
    top_k = request.top_k if request.top_k is not None else _TOP_K_DEFAULT
    if not (_TOP_K_MIN <= top_k <= _TOP_K_MAX):
        raise HTTPException(
            status_code=400,
            detail=f"top_k must be between {_TOP_K_MIN} and {_TOP_K_MAX}.",
        )

    # --- Resolve this user's accessible document IDs (DB ∩ on-disk) ---
    user_doc_rows = (
        db.query(DBDocument)
        .filter(DBDocument.user_id == current_user.id)
        .all()
    )
    user_doc_ids = {row.document_id for row in user_doc_rows}
    on_disk = set(get_available_document_ids())
    available_ids = list(user_doc_ids & on_disk)

    if not available_ids:
        raise HTTPException(
            status_code=404,
            detail="No documents found. Please upload a PDF first.",
        )

    if request.document_id and request.document_id not in available_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{request.document_id}' not found or not accessible.",
        )

    # --- Cache lookup (skip LLM + retrieval for repeated questions) ---
    cached = get_cached(request.question, request.document_id)
    if cached:
        elapsed = time.perf_counter() - start
        cached_eval = cached.get("eval_metrics") or {}
        cached_eval_model = EvalMetrics(**{
            k: cached_eval[k] for k in EvalMetrics.model_fields if k in cached_eval
        }) if cached_eval else None

        return AskResponse(
            answer=cached["answer"],
            sources=cached["sources"],
            documents_searched=cached.get("documents_searched", 0),
            response_time=round(elapsed, 3),
            retrieved_chunks=cached.get("retrieved_chunks", 0),
            cache_hit=True,
            eval_metrics=cached_eval_model,
        )

    # --- Retrieval + generation ---
    try:
        scored_chunks = await run_in_threadpool(
            retrieve_with_scores,
            request.question,
            request.document_id,
            top_k,
            None if request.document_id else available_ids,
        )

        if not scored_chunks:
            raise HTTPException(
                status_code=404,
                detail="No relevant content found for this question.",
            )

        chunks = [doc for _score, doc in scored_chunks]
        answer = await run_in_threadpool(generate_rag_answer, request.question, chunks)

    except HTTPException:
        raise
    except EnvironmentError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log_error(
            user_id=current_user.id,
            question=request.question,
            error=str(exc),
            latency_ms=elapsed_ms,
        )
        raise HTTPException(status_code=503, detail=str(exc))
    except (FileNotFoundError, RuntimeError) as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log_error(
            user_id=current_user.id,
            question=request.question,
            error=str(exc),
            latency_ms=elapsed_ms,
        )
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log_error(
            user_id=current_user.id,
            question=request.question,
            error=str(exc),
            latency_ms=elapsed_ms,
        )
        raise HTTPException(status_code=500, detail=f"Error generating answer: {exc}")

    elapsed = time.perf_counter() - start
    elapsed_ms = elapsed * 1000

    # --- Evaluation metrics ---
    eval_snapshot = build_eval_snapshot(
        question=request.question,
        answer=answer,
        scored_chunks=scored_chunks,
        top_k=top_k,
        latency_ms=elapsed_ms,
    )
    eval_metrics = EvalMetrics(
        retrieved_count=eval_snapshot["retrieved_count"],
        relevant_count=eval_snapshot["relevant_count"],
        retrieval_precision=eval_snapshot["retrieval_precision"],
        mean_score=eval_snapshot["mean_score"],
        max_score=eval_snapshot["max_score"],
        is_fallback=eval_snapshot["is_fallback"],
        keyword_overlap=eval_snapshot["keyword_overlap"],
        answer_length_words=eval_snapshot["answer_length_words"],
        appears_relevant=eval_snapshot["appears_relevant"],
        latency_ms=eval_snapshot["latency_ms"],
    )

    # --- Build source citations (top 3 shown to the user) ---
    sources: list[SourceChunk] = []
    for i, doc in enumerate(chunks[:3]):
        meta = doc.metadata or {}
        raw_filename = meta.get("filename", meta.get("source", None))
        filename = os.path.basename(str(raw_filename)) if raw_filename else None
        page = meta.get("page")  # 0-based; frontend adds 1 for display
        sources.append(
            SourceChunk(content=doc.page_content, index=i, filename=filename, page=page)
        )

    docs_searched = len(available_ids) if not request.document_id else 1
    response = AskResponse(
        answer=answer,
        sources=sources,
        documents_searched=docs_searched,
        response_time=round(elapsed, 3),
        retrieved_chunks=len(chunks),
        cache_hit=False,
        eval_metrics=eval_metrics,
    )

    # --- Store in cache for repeat questions ---
    set_cached(
        request.question,
        request.document_id,
        answer,
        sources,
        extra={
            "documents_searched": docs_searched,
            "retrieved_chunks": len(chunks),
            "eval_metrics": eval_snapshot,
        },
    )

    # --- Structured log entry ---
    log_request(
        user_id=current_user.id,
        question=request.question,
        document_id=request.document_id,
        eval_metrics=eval_snapshot,
        from_cache=False,
    )

    # --- Persist to chat history (best-effort) ---
    try:
        db.add(
            ChatHistory(
                user_id=current_user.id,
                document_id=request.document_id,
                question=request.question,
                answer=answer,
            )
        )
        db.commit()
    except Exception:
        pass

    return response
