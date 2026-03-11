import os
import pickle
from typing import List

import faiss
import numpy as np

from services.embedding_service import embed_texts, embed_query

VECTOR_STORE_DIR = "vector_stores"


def create_and_save_index(document_id: str, chunks: List[str]) -> None:
    """Embed chunks, build a cosine-similarity FAISS index, and persist it."""
    embeddings = embed_texts(chunks).astype(np.float32)
    faiss.normalize_L2(embeddings)  # enables cosine similarity via inner product

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    doc_dir = os.path.join(VECTOR_STORE_DIR, document_id)
    os.makedirs(doc_dir, exist_ok=True)

    faiss.write_index(index, os.path.join(doc_dir, "index.faiss"))
    with open(os.path.join(doc_dir, "chunks.pkl"), "wb") as f:
        pickle.dump(chunks, f)


def search_similar_chunks(
    document_id: str, query: str, top_k: int = 5
) -> List[str]:
    """Return the top-k document chunks most similar to the query."""
    doc_dir = os.path.join(VECTOR_STORE_DIR, document_id)
    index = faiss.read_index(os.path.join(doc_dir, "index.faiss"))

    with open(os.path.join(doc_dir, "chunks.pkl"), "rb") as f:
        chunks: List[str] = pickle.load(f)

    query_vec = embed_query(query).astype(np.float32).reshape(1, -1)
    faiss.normalize_L2(query_vec)

    k = min(top_k, len(chunks))
    _, indices = index.search(query_vec, k)

    return [chunks[i] for i in indices[0] if 0 <= i < len(chunks)]


def document_index_exists(document_id: str) -> bool:
    """Return True if the vector index for this document_id is on disk."""
    doc_dir = os.path.join(VECTOR_STORE_DIR, document_id)
    return os.path.exists(os.path.join(doc_dir, "index.faiss")) and os.path.exists(
        os.path.join(doc_dir, "chunks.pkl")
    )
