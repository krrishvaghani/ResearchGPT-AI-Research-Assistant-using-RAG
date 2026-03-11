"""
research_assistant.py — REST endpoints for the agentic research assistant.

Endpoints
---------
POST /research_assistant
    Full agentic workflow: literature review + key papers + future directions.
    Request:  { "topic": str, "document_id": str | null }
    Response: { "literature_review": str, "key_papers": [...], "future_research_directions": str }

POST /literature_review
    Focused literature review for a single topic.
    Request:  { "topic": str, "document_id": str | null }
    Response: { "literature_review": str }

POST /compare_papers
    Structured comparison of two papers.
    Request:  { "paper1": {...}, "paper2": {...}, "document_id": str | null }
    Response: { "comparison": str }
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import Document as DBDocument, User
from services.rag_pipeline import get_available_document_ids
from services.research_agent import (
    compare_papers,
    generate_literature_review,
    run_research_assistant,
)

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class ResearchAssistantRequest(BaseModel):
    topic: str
    # Optionally restrict RAG retrieval to a single uploaded document.
    document_id: Optional[str] = None

    @field_validator("topic")
    @classmethod
    def topic_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("topic must not be empty")
        return v.strip()


class PaperInput(BaseModel):
    title: str
    authors: List[str] = []
    summary: str = ""
    pdf_url: str = ""


class PaperComparisonRequest(BaseModel):
    paper1: PaperInput
    paper2: PaperInput
    document_id: Optional[str] = None


class KeyPaper(BaseModel):
    title: str
    authors: List[str]
    summary: str
    pdf_url: str


class ResearchAssistantResponse(BaseModel):
    literature_review: str
    key_papers: List[KeyPaper]
    future_research_directions: str


class LiteratureReviewResponse(BaseModel):
    literature_review: str


class PaperComparisonResponse(BaseModel):
    comparison: str


# ── Shared helper ─────────────────────────────────────────────────────────────

def _resolve_doc_ids(
    document_id: Optional[str],
    current_user: User,
    db: Session,
) -> Optional[List[str]]:
    """
    Return the list of doc IDs this user can access.

    If a specific document_id is requested, validate it belongs to the user
    and exists on disk.  Returns None if the user has no uploaded documents
    (agent will skip local retrieval gracefully).
    """
    user_rows = (
        db.query(DBDocument)
        .filter(DBDocument.user_id == current_user.id)
        .all()
    )
    user_doc_ids = {row.document_id for row in user_rows}
    on_disk = set(get_available_document_ids())
    available = list(user_doc_ids & on_disk)

    if document_id:
        if document_id not in available:
            raise HTTPException(
                status_code=404,
                detail=f"Document '{document_id}' not found or not accessible.",
            )
        return [document_id]

    return available if available else None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/research_assistant", response_model=ResearchAssistantResponse)
async def research_assistant_endpoint(
    request: ResearchAssistantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Full agentic research workflow.

    Multi-step pipeline:
      1. Search arXiv for the most relevant papers
      2. Retrieve relevant sections from the user's uploaded PDFs
      3. Generate a structured literature review (LLM)
      4. Generate future research directions (LLM)

    Raises:
    - **400** — topic is empty
    - **404** — specified document_id not found or not accessible
    - **503** — OPENAI_API_KEY not configured
    - **500** — unexpected server error
    """
    doc_ids = _resolve_doc_ids(request.document_id, current_user, db)

    try:
        result = await run_in_threadpool(
            run_research_assistant, request.topic, doc_ids
        )
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Research assistant error: {exc}"
        )

    return ResearchAssistantResponse(
        literature_review=result["literature_review"],
        key_papers=[KeyPaper(**p) for p in result["key_papers"]],
        future_research_directions=result["future_research_directions"],
    )


@router.post("/literature_review", response_model=LiteratureReviewResponse)
async def literature_review_endpoint(
    request: ResearchAssistantRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a structured literature review for a given topic.

    Combines arXiv paper abstracts with relevant sections from uploaded PDFs,
    and synthesises them into a five-section Markdown review.

    Sections: Title / Background / Key Approaches / Comparison of Methods / Conclusion
    """
    doc_ids = _resolve_doc_ids(request.document_id, current_user, db)

    try:
        review = await run_in_threadpool(
            generate_literature_review, request.topic, doc_ids
        )
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Literature review error: {exc}"
        )

    return LiteratureReviewResponse(literature_review=review)


@router.post("/compare_papers", response_model=PaperComparisonResponse)
async def compare_papers_endpoint(
    request: PaperComparisonRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a structured comparison of two research papers.

    Comparison covers: Architecture · Dataset · Performance ·
    Key Differences · When to Use Each.

    The agent also queries uploaded documents for additional supporting context.
    """
    doc_ids = _resolve_doc_ids(request.document_id, current_user, db)

    try:
        comparison = await run_in_threadpool(
            compare_papers,
            request.paper1.model_dump(),
            request.paper2.model_dump(),
            doc_ids,
        )
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Paper comparison error: {exc}"
        )

    return PaperComparisonResponse(comparison=comparison)
