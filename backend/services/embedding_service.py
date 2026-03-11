import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List

# Singleton model — loaded once and reused across requests
_model: SentenceTransformer = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_texts(texts: List[str]) -> np.ndarray:
    """Return embeddings for a list of text strings."""
    return get_model().encode(texts, convert_to_numpy=True, show_progress_bar=False)


def embed_query(query: str) -> np.ndarray:
    """Return the embedding for a single query string."""
    return get_model().encode([query], convert_to_numpy=True)[0]
