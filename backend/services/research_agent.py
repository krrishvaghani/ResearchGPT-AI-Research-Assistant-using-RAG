"""
research_agent.py — Agentic AI research assistant.

Orchestrates a multi-step reasoning pipeline over research papers:

  Step 1 — Search arXiv for relevant papers           (research_search.search_arxiv)
  Step 2 — Retrieve relevant sections from uploaded   (rag_pipeline.retrieve_relevant_chunks)
            PDFs via FAISS
  Step 3 — Synthesize findings with LLM               (ChatOpenAI via LangChain LCEL)
  Step 4 — Identify future research directions        (LLM)

Public API
----------
generate_literature_review(topic, doc_ids=None)
    Generate a structured literature review with sections:
    Title / Background / Key Approaches / Comparison of Methods / Conclusion

compare_papers(paper1, paper2, doc_ids=None)
    Produce a structured comparison of two papers across:
    Architecture · Dataset · Performance · Key Differences · When to Use

run_research_assistant(topic, doc_ids=None)
    Full agentic workflow returning:
      - literature_review          (str)
      - key_papers                 (List[Dict])
      - future_research_directions (str)
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from services.rag_pipeline import (
    get_available_document_ids,
    retrieve_relevant_chunks,
)
from services.research_search import search_arxiv

load_dotenv(override=True)

logger = logging.getLogger(__name__)

# Lazy singleton LLM — shared across all agent calls.
_llm: Optional[ChatGoogleGenerativeAI] = None


def _get_llm() -> ChatGoogleGenerativeAI:
    global _llm
    # Always re-read from env so a key rotation takes effect without restart.
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. Add it to your .env file."
        )
    if _llm is None or _llm.google_api_key != api_key:
        _llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.2,
            max_output_tokens=2000,
            google_api_key=api_key,
        )
    return _llm


# ── Step 1 — Search arXiv ─────────────────────────────────────────────────────

def _search_papers(topic: str, max_results: int = 8) -> List[Dict]:
    """Return up to max_results arXiv papers relevant to topic."""
    logger.info("[Agent] Step 1 — Searching arXiv: %s", topic)
    try:
        papers = search_arxiv(query=topic, max_results=max_results)
        logger.info("[Agent] Found %d arXiv papers", len(papers))
        return papers
    except Exception as exc:
        logger.warning("[Agent] arXiv search failed (%s) — continuing without external papers", exc)
        return []


# ── Step 2 — Retrieve from uploaded PDFs ──────────────────────────────────────

def _retrieve_from_docs(
    query: str,
    doc_ids: Optional[List[str]],
    top_k: int = 10,
) -> List[Document]:
    """Retrieve relevant chunks from the user's uploaded PDFs via FAISS."""
    logger.info("[Agent] Step 2 — Retrieving chunks for: %s", query)
    available = doc_ids if doc_ids is not None else get_available_document_ids()
    if not available:
        logger.info("[Agent] No uploaded documents available — skipping local retrieval")
        return []
    try:
        chunks = retrieve_relevant_chunks(
            question=query,
            allowed_doc_ids=available,
            top_k=top_k,
        )
        logger.info("[Agent] Retrieved %d chunks from uploaded docs", len(chunks))
        return chunks
    except Exception as exc:
        logger.warning("[Agent] Local retrieval failed (%s) — continuing without doc context", exc)
        return []


# ── Context builders ──────────────────────────────────────────────────────────

def _build_arxiv_context(papers: List[Dict], max_papers: int = 5) -> str:
    """Format arXiv papers as a numbered, human-readable context block."""
    if not papers:
        return "(No external papers found for this topic.)"
    parts: List[str] = []
    for i, p in enumerate(papers[:max_papers], 1):
        authors = ", ".join(p.get("authors", [])[:3])
        abstract = (p.get("summary") or "")[:600]
        parts.append(
            f"[Paper {i}] {p.get('title', 'Untitled')}\n"
            f"Authors: {authors}\n"
            f"Abstract: {abstract}"
        )
    return "\n\n---\n\n".join(parts)


def _build_doc_context(chunks: List[Document]) -> str:
    """Format retrieved document chunks as a numbered context block."""
    if not chunks:
        return "(No relevant sections found in uploaded documents.)"
    parts: List[str] = []
    for i, doc in enumerate(chunks, 1):
        meta = doc.metadata or {}
        raw = meta.get("filename", meta.get("source", "unknown"))
        filename = os.path.basename(str(raw))
        page = meta.get("page")
        label = f"page {page + 1}" if page is not None else "unknown page"
        parts.append(
            f"[Doc Excerpt {i}] Source: {filename}, {label}\n{doc.page_content}"
        )
    return "\n\n---\n\n".join(parts)


# ── Literature Review ─────────────────────────────────────────────────────────

_LIT_REVIEW_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are an expert academic researcher. Write rigorous, structured literature reviews "
     "based solely on the provided papers and document excerpts. "
     "Do not invent citations or state facts not present in the sources."),
    ("human",
     "Write a comprehensive literature review on the topic: \"{topic}\"\n\n"
     "=== ARXIV PAPERS ===\n{arxiv_context}\n\n"
     "=== UPLOADED DOCUMENT EXCERPTS ===\n{doc_context}\n\n"
     "Structure your review EXACTLY using these five headings:\n\n"
     "## Title\n"
     "A descriptive, specific title for this literature review.\n\n"
     "## Background\n"
     "Introduce the research area, its importance, motivations, and historical context.\n\n"
     "## Key Approaches\n"
     "Describe the main methodologies, architectures, and techniques found in the literature.\n\n"
     "## Comparison of Methods\n"
     "Compare and contrast approaches — consider architecture, datasets, performance metrics, "
     "scalability, and limitations.\n\n"
     "## Conclusion\n"
     "Summarize the key findings, identify gaps, and highlight open challenges.\n\n"
     "Write the full review now:"),
])


def generate_literature_review(
    topic: str,
    doc_ids: Optional[List[str]] = None,
) -> str:
    """
    Generate a structured literature review via a 3-step agentic workflow.

    Steps:
      1. Search arXiv for relevant papers
      2. Retrieve relevant sections from uploaded PDFs
      3. Synthesize into a structured review (LLM)

    Args:
        topic:   Research topic or natural-language question.
        doc_ids: Uploaded document IDs to include (None = all available).

    Returns:
        Structured literature review string with five Markdown sections.

    Raises:
        EnvironmentError: If OPENAI_API_KEY is not configured.
    """
    logger.info("[Agent] Generating literature review for: %s", topic)
    papers = _search_papers(topic, max_results=8)
    chunks = _retrieve_from_docs(topic, doc_ids, top_k=10)

    logger.info("[Agent] Step 3 — Synthesizing literature review with LLM")
    chain = _LIT_REVIEW_PROMPT | _get_llm() | StrOutputParser()
    review = chain.invoke({
        "topic": topic,
        "arxiv_context": _build_arxiv_context(papers, max_papers=5),
        "doc_context": _build_doc_context(chunks),
    })
    logger.info("[Agent] Literature review complete (%d chars)", len(review))
    return review


# ── Paper Comparison ──────────────────────────────────────────────────────────

_COMPARE_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are an expert researcher specialising in comparative analysis of academic papers. "
     "Provide precise, objective comparisons based only on the information provided. "
     "Do not make up details that are not present in the abstracts or context."),
    ("human",
     "Compare these two research papers:\n\n"
     "=== PAPER 1 ===\n"
     "Title: {title1}\nAuthors: {authors1}\nAbstract: {summary1}\n\n"
     "=== PAPER 2 ===\n"
     "Title: {title2}\nAuthors: {authors2}\nAbstract: {summary2}\n\n"
     "{extra_context}"
     "Produce a structured comparison in this EXACT format:\n\n"
     "**Paper 1:** {title1}\n"
     "**Paper 2:** {title2}\n\n"
     "### Architecture / Approach\n"
     "- Paper 1: ...\n- Paper 2: ...\n\n"
     "### Dataset / Experimental Setup\n"
     "- Paper 1: ...\n- Paper 2: ...\n\n"
     "### Performance & Results\n"
     "- Paper 1: ...\n- Paper 2: ...\n\n"
     "### Key Differences\n"
     "List the most significant differences as bullet points.\n\n"
     "### When to Use Each\n"
     "Guidance on when each approach is most suitable and for what tasks.\n\n"
     "Write the full comparison now:"),
])


def compare_papers(
    paper1: Dict,
    paper2: Dict,
    doc_ids: Optional[List[str]] = None,
) -> str:
    """
    Generate a structured comparison of two research papers.

    Also retrieves additional supporting context from uploaded PDFs if available.

    Args:
        paper1: Dict with keys: title, authors (list), summary, pdf_url.
        paper2: Dict with keys: title, authors (list), summary, pdf_url.
        doc_ids: Uploaded document IDs to query for extra context.

    Returns:
        Structured comparison string with Markdown sections.

    Raises:
        EnvironmentError: If OPENAI_API_KEY is not configured.
    """
    logger.info(
        "[Agent] Comparing papers: '%s' vs '%s'",
        paper1.get("title", "?"),
        paper2.get("title", "?"),
    )

    # Try to enrich comparison with relevant content from uploaded docs.
    combined_query = (
        f"{paper1.get('title', '')} {paper2.get('title', '')} "
        f"{paper1.get('summary', '')[:200]} {paper2.get('summary', '')[:200]}"
    )
    chunks = _retrieve_from_docs(combined_query, doc_ids, top_k=6)
    extra_context = ""
    if chunks:
        extra_context = (
            "=== ADDITIONAL CONTEXT FROM UPLOADED DOCUMENTS ===\n"
            + _build_doc_context(chunks)
            + "\n\n"
        )

    chain = _COMPARE_PROMPT | _get_llm() | StrOutputParser()
    comparison = chain.invoke({
        "title1": paper1.get("title", "Unknown"),
        "authors1": ", ".join(paper1.get("authors", [])[:4]),
        "summary1": (paper1.get("summary") or "")[:800],
        "title2": paper2.get("title", "Unknown"),
        "authors2": ", ".join(paper2.get("authors", [])[:4]),
        "summary2": (paper2.get("summary") or "")[:800],
        "extra_context": extra_context,
    })
    logger.info("[Agent] Paper comparison complete")
    return comparison


# ── Future Research Directions ────────────────────────────────────────────────

_FUTURE_DIRECTIONS_PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a forward-looking AI research strategist. "
     "Based on the provided literature, identify concrete, actionable future research opportunities. "
     "Be specific — avoid generic statements."),
    ("human",
     "Topic: \"{topic}\"\n\n"
     "Literature sources:\n{context}\n\n"
     "Identify 5–7 specific future research directions. "
     "For each direction provide:\n"
     "1. The gap or limitation it addresses\n"
     "2. A concrete research question\n"
     "3. Potential impact\n\n"
     "Format as a numbered list with clear, specific titles for each direction."),
])


def _generate_future_directions(
    topic: str,
    papers: List[Dict],
    chunks: List[Document],
) -> str:
    """Generate future research directions from arXiv papers and doc chunks."""
    logger.info("[Agent] Step 4 — Generating future research directions")
    context = (
        _build_arxiv_context(papers, max_papers=4)
        + "\n\n"
        + _build_doc_context(chunks[:4])
    )
    chain = _FUTURE_DIRECTIONS_PROMPT | _get_llm() | StrOutputParser()
    return chain.invoke({"topic": topic, "context": context})


# ── Full Agentic Workflow ─────────────────────────────────────────────────────

def run_research_assistant(
    topic: str,
    doc_ids: Optional[List[str]] = None,
) -> Dict:
    """
    Full multi-step agentic research workflow.

    Workflow:
      Step 1 — Search arXiv for relevant papers
      Step 2 — Retrieve relevant sections from uploaded PDFs
      Step 3 — Generate structured literature review (LLM)
      Step 4 — Generate future research directions (LLM)

    Args:
        topic:   Research topic or question.
        doc_ids: Uploaded document IDs (None = all available).

    Returns:
        Dict with keys:
          literature_review          (str) — structured Markdown review
          key_papers                 (List[Dict]) — top papers from arXiv
          future_research_directions (str) — numbered research opportunities

    Raises:
        EnvironmentError: If OPENAI_API_KEY is not configured.
    """
    logger.info("[Agent] ── Starting research assistant workflow ──  topic=%s", topic)

    # Step 1 — search
    papers = _search_papers(topic, max_results=8)

    # Step 2 — retrieve
    chunks = _retrieve_from_docs(topic, doc_ids, top_k=10)

    # Step 3 — literature review
    logger.info("[Agent] Step 3 — Synthesising literature review")
    lit_chain = _LIT_REVIEW_PROMPT | _get_llm() | StrOutputParser()
    literature_review = lit_chain.invoke({
        "topic": topic,
        "arxiv_context": _build_arxiv_context(papers, max_papers=5),
        "doc_context": _build_doc_context(chunks),
    })

    # Step 4 — future directions
    future_directions = _generate_future_directions(topic, papers, chunks)

    # Key papers — top 5 from arXiv (truncated for API response)
    key_papers = [
        {
            "title": p.get("title", ""),
            "authors": p.get("authors", [])[:3],
            "summary": (p.get("summary") or "")[:400],
            "pdf_url": p.get("pdf_url", ""),
        }
        for p in papers[:5]
    ]

    logger.info("[Agent] ── Research assistant workflow complete ──")
    return {
        "literature_review": literature_review,
        "key_papers": key_papers,
        "future_research_directions": future_directions,
    }
