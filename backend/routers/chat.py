import os

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from models.schemas import ChatRequest, ChatResponse, SourceChunk
from services.embeddings import generate_query_embedding
from services.vector_store import load_vector_store, vector_store_path, VECTOR_DB_DIR
from services.llm_service import generate_answer

router = APIRouter()


def _index_exists(document_id: str) -> bool:
    """Return True if a persisted vector store for document_id exists in vector_db/."""
    path = vector_store_path(document_id)
    return os.path.exists(os.path.join(path, "index.faiss")) and os.path.exists(
        os.path.join(path, "chunks.pkl")
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if not _index_exists(request.document_id):
        raise HTTPException(
            status_code=404,
            detail="Document not found. Please upload a PDF first.",
        )

    # Load the persisted FAISS index for this document.
    store = await run_in_threadpool(
        load_vector_store, vector_store_path(request.document_id)
    )

    # Embed the query and retrieve the top-5 most similar chunks.
    query_vec = await run_in_threadpool(generate_query_embedding, request.question)
    result_docs = store.search(query_vec, top_k=5)

    if not result_docs:
        raise HTTPException(
            status_code=404,
            detail="No relevant content found for this question.",
        )

    chunk_texts = [doc.page_content for doc in result_docs]

    try:
        answer = await run_in_threadpool(generate_answer, request.question, chunk_texts)
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating answer: {exc}",
        )

    sources = [
        SourceChunk(content=text, index=i) for i, text in enumerate(chunk_texts[:3])
    ]

    return ChatResponse(
        answer=answer,
        sources=sources,
        document_id=request.document_id,
    )
