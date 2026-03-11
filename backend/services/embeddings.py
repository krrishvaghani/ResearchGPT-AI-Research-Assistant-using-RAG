"""
embeddings.py — Generate vector embeddings for document chunks.

Uses the Sentence Transformers library with the all-MiniLM-L6-v2 model to
convert text chunks into dense vector representations suitable for semantic
search via a FAISS index.
"""

from typing import List

import numpy as np
from langchain_core.documents import Document
from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"

# Batch size balances throughput vs. peak memory usage.
# 64 works well up to ~100 k chunks on a typical 8 GB machine; reduce if OOM.
_BATCH_SIZE = 64

# Singleton — loaded once per process and reused across requests.
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def generate_embeddings(chunks: List[Document]) -> np.ndarray:
    """
    Convert a list of document chunks into L2-normalised vector embeddings.

    Embeddings are unit-length so that an inner-product search is equivalent
    to cosine similarity — this is the format expected by VectorStore.

    Args:
        chunks: List of Document objects produced by text_chunker.split_documents().

    Returns:
        numpy.ndarray of shape (len(chunks), 384) and dtype float32.
        Each row is the embedding for the corresponding chunk.

    Raises:
        ValueError: If chunks is empty or None.
    """
    if not chunks:
        raise ValueError("No chunks provided — cannot generate embeddings.")

    texts = [chunk.page_content for chunk in chunks]
    model = _get_model()

    embeddings: np.ndarray = model.encode(
        texts,
        batch_size=_BATCH_SIZE,
        convert_to_numpy=True,
        show_progress_bar=False,
        # Normalise to unit length so cosine similarity == inner product.
        normalize_embeddings=True,
    )

    return embeddings.astype(np.float32)


def generate_query_embedding(query: str) -> np.ndarray:
    """
    Convert a single query string into an L2-normalised vector embedding.

    This uses the same model and normalisation as generate_embeddings so that
    inner-product similarity scores are directly comparable.

    Args:
        query: The question or search string to embed.

    Returns:
        1-D numpy.ndarray of shape (384,) and dtype float32.

    Raises:
        ValueError: If query is empty or whitespace.
    """
    if not query or not query.strip():
        raise ValueError("Query string must not be empty.")

    model = _get_model()
    embedding: np.ndarray = model.encode(
        [query],
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return embedding[0].astype(np.float32)
