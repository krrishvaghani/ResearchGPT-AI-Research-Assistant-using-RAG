"""
research_search.py — arXiv paper search and AI summarization service.

Provides:
- search_arxiv(query, max_results)  → list of paper dicts
- summarize_paper(text)             → AI-generated summary string
"""

import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI

# ── Constants ─────────────────────────────────────────────────────────────────

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = "http://www.w3.org/2005/Atom"

# Prompt asking the LLM to produce a structured summary
_SUMMARIZE_PROMPT = PromptTemplate.from_template(
    """You are an expert research assistant. Read the following research paper content and produce a concise, structured summary.

Include:
1. **Key Contributions** – What are the main contributions of this work?
2. **Methods** – What approach or technique is used?
3. **Results** – What are the key findings or outcomes?
4. **Simple Explanation** – Explain the core idea in plain language for a non-specialist.

Paper content:
{text}

Summary:"""
)


# ── arXiv search ──────────────────────────────────────────────────────────────

def search_arxiv(query: str, max_results: int = 10) -> List[Dict]:
    """
    Query the arXiv Atom API and return a list of paper dicts.

    Each dict has: title, authors (list), summary (abstract), pdf_url.
    Raises urllib.error.URLError on network failure.
    """
    params = urllib.parse.urlencode(
        {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
    )
    url = f"{ARXIV_API_URL}?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": "AI-PDF-Chat-Platform/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        xml_bytes = resp.read()

    root = ET.fromstring(xml_bytes)
    papers: List[Dict] = []

    for entry in root.findall(f"{{{ATOM_NS}}}entry"):
        title_el = entry.find(f"{{{ATOM_NS}}}title")
        summary_el = entry.find(f"{{{ATOM_NS}}}summary")

        title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
        abstract = (summary_el.text or "").strip().replace("\n", " ") if summary_el is not None else ""

        authors = [
            name_el.text.strip()
            for author in entry.findall(f"{{{ATOM_NS}}}author")
            if (name_el := author.find(f"{{{ATOM_NS}}}name")) is not None
            and name_el.text
        ]

        # Prefer the explicit PDF link; fall back to the HTML abstract page
        pdf_url = ""
        for link in entry.findall(f"{{{ATOM_NS}}}link"):
            if link.get("title") == "pdf":
                href = link.get("href", "")
                # Ensure HTTPS
                pdf_url = href.replace("http://", "https://")
                break
        if not pdf_url:
            id_el = entry.find(f"{{{ATOM_NS}}}id")
            if id_el is not None and id_el.text:
                pdf_url = id_el.text.strip().replace("abs", "pdf")

        if title:  # skip malformed entries
            papers.append(
                {
                    "title": title,
                    "authors": authors,
                    "summary": abstract,
                    "pdf_url": pdf_url,
                }
            )

    return papers


# ── AI summarization ──────────────────────────────────────────────────────────

def summarize_paper(text: str) -> str:
    """
    Use an LLM to generate a structured summary of the provided text.

    Args:
        text: Raw research paper text or abstract (truncated to 6 000 chars).

    Returns:
        A markdown-formatted summary string.

    Raises:
        EnvironmentError: OPENAI_API_KEY is not set.
        Exception: Any LLM or network failure.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. Cannot generate summary."
        )

    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.3, max_output_tokens=600, google_api_key=api_key)
    chain = _SUMMARIZE_PROMPT | llm | StrOutputParser()

    # Truncate to stay well within the model's context window
    truncated = text.strip()[:6000]
    return chain.invoke({"text": truncated})
