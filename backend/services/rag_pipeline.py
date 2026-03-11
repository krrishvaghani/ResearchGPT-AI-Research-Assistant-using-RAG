"""
rag_pipeline.py — Retrieval-Augmented Generation pipeline.

End-to-end flow:
    user question
    → query embedding  (embeddings.generate_query_embedding)
    → FAISS similarity search  (vector_store.VectorStore.search)
    → context assembly with filename + page citations
    → LangChain LCEL chain  (PromptTemplate | ChatOpenAI | StrOutputParser)
    → answer string

Public API
----------
get_available_document_ids()
    List every document that has a persisted vector store.

retrieve_relevant_chunks(question, document_id=None, top_k=5)
    Embed the question and return the most relevant Document chunks.
    If document_id is None, all available stores are searched and
    the results are merged/deduplicated.

generate_rag_answer(question, chunks)
    Build a LangChain prompt, call ChatOpenAI, and return the answer string.
    Accepts already-retrieved chunks so the router can reuse them for sources.

ask_question(question, document_id=None)
    Convenience wrapper: calls retrieve_relevant_chunks then generate_rag_answer
    and returns the answer string.
"""

import os
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from services.embeddings import generate_query_embedding
from services.vector_store import VECTOR_DB_DIR, load_vector_store, vector_store_path

load_dotenv(override=True)

# Default number of chunks to retrieve per question.
_TOP_K = 5

# Maximum allowed top_k to prevent runaway queries.
_TOP_K_MAX = 20

# Cosine-similarity threshold below which a chunk is considered off-topic.
# Chunks below this score are filtered out UNLESS they are the only results.
RELEVANCE_THRESHOLD = 0.20

# System instruction message — separated from the human turn for better
# instruction-following with chat-tuned models.
_SYSTEM_PROMPT = (
    "You are a precise AI research assistant. Your task is to answer questions "
    "based ONLY on the document excerpts provided in the user's message. "
    "If the answer is not present in the excerpts, say: "
    "\"I couldn't find this information in the provided documents.\" "
    "Do not use any knowledge outside the given context."
)

_CHAT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PROMPT),
    ("human",
     "Guidelines:\n"
     "- Use only information present in the provided context.\n"
     "- Be concise but thorough.\n"
     "- Use bullet points or numbered lists when listing multiple items.\n"
     "- Cite sources as \"According to [Excerpt N]...\" when relevant.\n\n"
     "Context:\n{context}\n\n"
     "Question: {question}\n\n"
     "Answer:"),
])


# ---------------------------------------------------------------------------
# Document discovery
# ---------------------------------------------------------------------------


def get_available_document_ids() -> List[str]:
    """
    Return a list of all document IDs that have a valid persisted vector store
    under VECTOR_DB_DIR.  Returns an empty list if the directory does not exist.
    """
    if not os.path.isdir(VECTOR_DB_DIR):
        return []
    return [
        name
        for name in os.listdir(VECTOR_DB_DIR)
        if (
            os.path.isdir(os.path.join(VECTOR_DB_DIR, name))
            and os.path.exists(os.path.join(VECTOR_DB_DIR, name, "index.faiss"))
            and os.path.exists(os.path.join(VECTOR_DB_DIR, name, "chunks.pkl"))
        )
    ]


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def retrieve_relevant_chunks(
    question: str,
    document_id: Optional[str] = None,
    top_k: int = _TOP_K,
    allowed_doc_ids: Optional[List[str]] = None,
) -> List[Document]:
    """
    Embed *question* and return the most relevant Document chunks.

    Searches each per-document FAISS store independently and selects the
    globally best *top_k* chunks by cosine similarity score so that results
    from more relevant documents naturally rank higher.

    Args:
        question:    User question to embed.
        document_id: If supplied, search only that document's store.
                     If None, search all available stores.
        top_k:       Maximum number of chunks to return.

    Returns:
        List of Document objects ranked by cosine similarity (highest first),
        deduplicated by page content, capped at *top_k*.

    Raises:
        ValueError:        If question is empty.
        RuntimeError:      If no documents are available (and document_id is None).
        FileNotFoundError: If the specified document_id has no store on disk.
    """
    if not question or not question.strip():
        raise ValueError("Question must not be empty.")

    if document_id:
        doc_ids = [document_id]
    elif allowed_doc_ids is not None:
        doc_ids = allowed_doc_ids
        if not doc_ids:
            raise RuntimeError("No documents available. Please upload a PDF first.")
    else:
        doc_ids = get_available_document_ids()
        if not doc_ids:
            raise RuntimeError(
                "No documents are available. Please upload a PDF first."
            )

    query_vec = generate_query_embedding(question)

    # Collect (score, document) pairs from every store so we can globally rank.
    scored: List[Tuple[float, Document]] = []
    for doc_id in doc_ids:
        store = load_vector_store(vector_store_path(doc_id))
        # Ask for up to top_k candidates from each store; global re-rank below.
        results_with_scores = store.search_with_scores(query_vec, top_k=top_k)
        scored.extend(results_with_scores)

    # Sort globally by descending score.
    scored.sort(key=lambda x: x[0], reverse=True)

    # Filter low-relevance chunks, but keep at least one so we never return empty
    # when there IS content (the LLM will gracefully say "not found").
    above = [(s, d) for s, d in scored if s >= RELEVANCE_THRESHOLD]
    scored_filtered = above if above else scored[:1]

    # Deduplicate by exact page_content.
    seen: set[str] = set()
    unique: List[Document] = []
    for _score, doc in scored_filtered:
        if doc.page_content not in seen:
            seen.add(doc.page_content)
            unique.append(doc)
        if len(unique) == top_k:
            break

    return unique


# ---------------------------------------------------------------------------
# LangChain generation
# ---------------------------------------------------------------------------


def retrieve_with_scores(
    question: str,
    document_id: Optional[str] = None,
    top_k: int = _TOP_K,
    allowed_doc_ids: Optional[List[str]] = None,
) -> List[Tuple[float, Document]]:
    """
    Like retrieve_relevant_chunks but returns (score, Document) pairs so the
    caller can compute retrieval quality metrics.

    The same relevance-threshold filtering and deduplication logic applies.

    Returns:
        List of (cosine_score, Document) sorted descending by score.
    """
    if not question or not question.strip():
        raise ValueError("Question must not be empty.")

    top_k = min(max(1, top_k), _TOP_K_MAX)

    if document_id:
        doc_ids = [document_id]
    elif allowed_doc_ids is not None:
        doc_ids = allowed_doc_ids
        if not doc_ids:
            raise RuntimeError("No documents available. Please upload a PDF first.")
    else:
        doc_ids = get_available_document_ids()
        if not doc_ids:
            raise RuntimeError("No documents are available. Please upload a PDF first.")

    query_vec = generate_query_embedding(question)

    scored: List[Tuple[float, Document]] = []
    for doc_id in doc_ids:
        store = load_vector_store(vector_store_path(doc_id))
        scored.extend(store.search_with_scores(query_vec, top_k=top_k))

    scored.sort(key=lambda x: x[0], reverse=True)

    above = [(s, d) for s, d in scored if s >= RELEVANCE_THRESHOLD]
    scored_filtered = above if above else scored[:1]

    seen: set[str] = set()
    unique: List[Tuple[float, Document]] = []
    for score, doc in scored_filtered:
        if doc.page_content not in seen:
            seen.add(doc.page_content)
            unique.append((score, doc))
        if len(unique) == top_k:
            break

    return unique


def generate_rag_answer(question: str, chunks: List[Document]) -> str:
    """
    Build a LangChain LCEL chain and call ChatOpenAI to answer *question*
    given the already-retrieved *chunks* as context.

    Each excerpt is labelled with its source filename and page number so the
    model can produce citations in its answer.

    Pipeline: PromptTemplate | ChatOpenAI | StrOutputParser

    Args:
        question: The user's question.
        chunks:   Document chunks retrieved by retrieve_relevant_chunks.

    Returns:
        The model's answer as a plain string.

    Raises:
        EnvironmentError: If OPENAI_API_KEY is not configured.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. Add it to your .env file."
        )

    if not chunks:
        return "I couldn't find relevant information in the document to answer your question."

    # Build citation-rich context block.
    excerpt_parts: List[str] = []
    for i, doc in enumerate(chunks):
        meta = doc.metadata or {}
        filename = meta.get("filename", meta.get("source", "unknown"))
        # page is 0-based in metadata; display as 1-based.
        page = meta.get("page")
        page_label = f"page {page + 1}" if page is not None else "unknown page"
        # Strip leading path components for readability.
        filename_label = os.path.basename(str(filename)) if filename else "unknown"
        header = f"[Excerpt {i + 1}] Source: {filename_label}, {page_label}"
        excerpt_parts.append(f"{header}\n{doc.page_content}")

    context = "\n\n---\n\n".join(excerpt_parts)

    # LangChain LCEL chain: ChatPromptTemplate → LLM → string output
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.1,
        max_output_tokens=1500,
        google_api_key=api_key,
    )
    chain = _CHAT_PROMPT | llm | StrOutputParser()

    return chain.invoke({"context": context, "question": question})


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------


def ask_question(
    question: str,
    document_id: Optional[str] = None,
) -> str:
    """
    Full RAG pipeline in a single call.

    Retrieves the most relevant chunks from the vector database and feeds them
    as context to the language model to produce an answer.

    Args:
        question:    The user's natural-language question.
        document_id: Optional — restrict retrieval to a single document.
                     If None, all available documents are searched.

    Returns:
        The language model's generated answer string.

    Raises:
        ValueError:        If question is empty.
        RuntimeError:      If no documents have been uploaded.
        EnvironmentError:  If OPENAI_API_KEY is not set.
        FileNotFoundError: If the specified document_id is not found on disk.
    """
    chunks = retrieve_relevant_chunks(question, document_id=document_id)
    return generate_rag_answer(question, chunks)
