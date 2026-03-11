from pydantic import BaseModel
from typing import List, Optional


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    pages: int
    chunks: int
    status: str
    message: str


class DocumentInfo(BaseModel):
    """Lightweight summary of an already-uploaded document."""
    document_id: str
    filename: str
    pages: int
    chunks: int


class ListDocumentsResponse(BaseModel):
    documents: List[DocumentInfo]
    total: int


class ChatRequest(BaseModel):
    document_id: str
    question: str


class SourceChunk(BaseModel):
    content: str
    index: int
    filename: Optional[str] = None
    page: Optional[int] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]
    document_id: str


class EvalMetrics(BaseModel):
    """Retrieval and response quality metrics returned with every /ask response."""
    retrieved_count: int = 0
    relevant_count: int = 0
    retrieval_precision: float = 0.0
    mean_score: float = 0.0
    max_score: float = 0.0
    # Response-quality heuristics
    is_fallback: bool = False
    keyword_overlap: float = 0.0
    answer_length_words: int = 0
    appears_relevant: bool = False
    latency_ms: float = 0.0


class AskRequest(BaseModel):
    question: str
    # Optional: restrict retrieval to a single uploaded document.
    # If omitted, all available documents are searched.
    document_id: Optional[str] = None
    # Override default top_k (1–20). Defaults to 5 on the server.
    top_k: Optional[int] = None


class AskResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]
    documents_searched: int = 0
    response_time: Optional[float] = None   # end-to-end wall-clock seconds
    retrieved_chunks: int = 0
    cache_hit: bool = False
    eval_metrics: Optional[EvalMetrics] = None


# ── Research search & summarization ──────────────────────────────────────────

class Paper(BaseModel):
    title: str
    authors: List[str]
    summary: str
    pdf_url: str


class SearchPapersResponse(BaseModel):
    papers: List[Paper]


class SummarizeRequest(BaseModel):
    text: str


class SummarizeResponse(BaseModel):
    summary: str


# ── Authentication ─────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
