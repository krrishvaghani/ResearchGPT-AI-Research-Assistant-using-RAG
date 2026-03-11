"""
research.py — GET /search_papers and POST /summarize endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from auth.dependencies import get_optional_user
from db.database import get_db
from db.models import SearchHistory, User
from models.schemas import SearchPapersResponse, SummarizeRequest, SummarizeResponse
from services.research_search import search_arxiv, summarize_paper

router = APIRouter()


@router.get("/search_papers", response_model=SearchPapersResponse)
async def search_papers(
    query: str = Query(..., min_length=1, description="Keyword(s) to search on arXiv"),
    max_results: int = Query(default=10, ge=1, le=25, description="Number of results to return"),
    current_user: User = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Search arXiv for research papers matching *query*.

    Returns up to *max_results* papers with title, authors, abstract, and PDF link.

    Raises:
    - **400** — query is empty.
    - **502** — arXiv API is unreachable or returned an error.
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        papers = await run_in_threadpool(search_arxiv, query.strip(), max_results)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach arXiv API: {exc}",
        )

    # Log to search history when the user is authenticated (best-effort).
    if current_user is not None:
        try:
            db.add(
                SearchHistory(
                    user_id=current_user.id,
                    query=query.strip(),
                    results_count=len(papers),
                )
            )
            db.commit()
        except Exception:
            pass

    return SearchPapersResponse(papers=papers)


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest):
    """
    Generate an AI-powered structured summary of research paper text.

    Raises:
    - **400** — text is empty.
    - **503** — OpenAI API key is not configured.
    - **500** — LLM or unexpected error.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    try:
        summary = await run_in_threadpool(summarize_paper, request.text)
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Summarization failed: {exc}",
        )

    return SummarizeResponse(summary=summary)
