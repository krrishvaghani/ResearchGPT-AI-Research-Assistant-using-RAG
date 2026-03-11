"""
vector_store.py — FAISS-backed vector database for document chunk embeddings.

Stores each document's index and chunk text on disk under:
    vector_db/<document_id>/index.faiss
    vector_db/<document_id>/chunks.pkl

Usage (typical upload pipeline):

    store = VectorStore()
    store.create_vector_store(chunks, embeddings)
    store.save_vector_store("vector_db/my-doc-id")

    # Later, at query time:
    store = VectorStore()
    store.load_vector_store("vector_db/my-doc-id")
    results = store.search(query_embedding, top_k=5)

Module-level helper functions (create_vector_store, save_vector_store,
load_vector_store) are also provided as thin wrappers for convenience.
"""

import os
import pickle
from typing import List

import faiss
import numpy as np
from langchain_core.documents import Document

# Root directory for all persisted vector databases.
VECTOR_DB_DIR = "vector_db"


class VectorStore:
    """
    Wraps a FAISS IndexFlatIP together with the associated Document chunks.

    IndexFlatIP performs exact inner-product search; combined with L2-normalised
    embeddings this is equivalent to cosine similarity and scales to hundreds of
    thousands of chunks without additional configuration.
    """

    def __init__(self) -> None:
        self.index: faiss.Index | None = None
        self.chunks: List[Document] | None = None

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def create_vector_store(
        self, chunks: List[Document], embeddings: np.ndarray
    ) -> None:
        """
        Build a FAISS inner-product index from pre-computed embeddings.

        Args:
            chunks:     Document objects aligned 1-to-1 with *embeddings*.
            embeddings: float32 array of shape (n, dim) — must already be
                        L2-normalised (as produced by embeddings.generate_embeddings).

        Raises:
            ValueError: If the chunk count does not match the embedding count,
                        or if either argument is empty.
        """
        if not chunks:
            raise ValueError("chunks must not be empty.")
        if embeddings.ndim != 2 or embeddings.shape[0] == 0:
            raise ValueError("embeddings must be a non-empty 2-D array.")
        if len(chunks) != embeddings.shape[0]:
            raise ValueError(
                f"Chunk count ({len(chunks)}) does not match "
                f"embedding count ({embeddings.shape[0]})."
            )

        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings.astype(np.float32))
        self.chunks = list(chunks)

    def save_vector_store(self, path: str) -> None:
        """
        Persist the FAISS index and chunk list to *path* (a directory).

        Creates the directory (and any parents) if it does not already exist.

        Raises:
            RuntimeError: If called before create_vector_store or load_vector_store.
        """
        if self.index is None or self.chunks is None:
            raise RuntimeError(
                "Vector store is empty — call create_vector_store first."
            )

        os.makedirs(path, exist_ok=True)
        faiss.write_index(self.index, os.path.join(path, "index.faiss"))
        with open(os.path.join(path, "chunks.pkl"), "wb") as fh:
            pickle.dump(self.chunks, fh)

    def load_vector_store(self, path: str) -> None:
        """
        Load a previously saved FAISS index and chunk list from *path*.

        Args:
            path: Directory that contains index.faiss and chunks.pkl.

        Raises:
            FileNotFoundError: If either expected file is missing.
        """
        index_path = os.path.join(path, "index.faiss")
        chunks_path = os.path.join(path, "chunks.pkl")

        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS index not found: {index_path!r}")
        if not os.path.exists(chunks_path):
            raise FileNotFoundError(f"Chunks file not found: {chunks_path!r}")

        self.index = faiss.read_index(index_path)
        with open(chunks_path, "rb") as fh:
            self.chunks = pickle.load(fh)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[Document]:
        """
        Return the top-k most similar Document chunks for a query embedding.

        Args:
            query_embedding: 1-D float32 array, L2-normalised.
            top_k:           Maximum number of results.

        Returns:
            List of Document objects ranked by cosine similarity (highest first).

        Raises:
            RuntimeError: If the store has not been populated yet.
        """
        if self.index is None or self.chunks is None:
            raise RuntimeError(
                "Vector store is empty — call create_vector_store or load_vector_store first."
            )

        vec = query_embedding.astype(np.float32).reshape(1, -1)
        k = min(top_k, len(self.chunks))
        _, indices = self.index.search(vec, k)
        return [self.chunks[i] for i in indices[0] if 0 <= i < len(self.chunks)]

    def search_with_scores(
        self, query_embedding: np.ndarray, top_k: int = 5
    ) -> List[tuple]:
        """
        Return (score, Document) pairs for the top-k most similar chunks.

        Scores are inner-product values in [0, 1] when embeddings are
        L2-normalised (equivalent to cosine similarity).

        Args:
            query_embedding: 1-D float32 array, L2-normalised.
            top_k:           Maximum number of results.

        Returns:
            List of (float, Document) tuples sorted by score descending.

        Raises:
            RuntimeError: If the store has not been populated yet.
        """
        if self.index is None or self.chunks is None:
            raise RuntimeError(
                "Vector store is empty — call create_vector_store or load_vector_store first."
            )

        vec = query_embedding.astype(np.float32).reshape(1, -1)
        k = min(top_k, len(self.chunks))
        scores, indices = self.index.search(vec, k)
        return [
            (float(scores[0][j]), self.chunks[indices[0][j]])
            for j in range(k)
            if 0 <= indices[0][j] < len(self.chunks)
        ]

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        """Return True if no index has been loaded or created yet."""
        return self.index is None


# ---------------------------------------------------------------------------
# Module-level convenience functions
# ---------------------------------------------------------------------------


def create_vector_store(
    chunks: List[Document], embeddings: np.ndarray
) -> VectorStore:
    """
    Create and return a populated VectorStore from *chunks* and *embeddings*.

    This is a convenience wrapper around VectorStore().create_vector_store().
    """
    store = VectorStore()
    store.create_vector_store(chunks, embeddings)
    return store


def save_vector_store(store: VectorStore, path: str) -> None:
    """
    Persist *store* to the directory at *path*.

    Convenience wrapper around store.save_vector_store(path).
    """
    store.save_vector_store(path)


def load_vector_store(path: str) -> VectorStore:
    """
    Load and return a VectorStore from the directory at *path*.

    Convenience wrapper around VectorStore().load_vector_store(path).
    """
    store = VectorStore()
    store.load_vector_store(path)
    return store


def vector_store_path(document_id: str, base_dir: str = VECTOR_DB_DIR) -> str:
    """Return the canonical storage path for a given document_id."""
    return os.path.join(base_dir, document_id)
