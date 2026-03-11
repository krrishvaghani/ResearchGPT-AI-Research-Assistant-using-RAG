"""
text_chunker.py — Split LangChain Documents into smaller overlapping chunks.

Uses RecursiveCharacterTextSplitter which tries to split on natural boundaries
(paragraphs → sentences → words → characters) before falling back to hard cuts,
so each chunk stays semantically coherent.
"""

from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Default configuration — tuneable at call-time
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


def split_documents(
    documents: List[Document],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Document]:
    """
    Split a list of Documents into smaller overlapping chunks.

    Args:
        documents:     List of Document objects from pdf_loader.load_pdf().
        chunk_size:    Maximum number of characters per chunk (default 1000).
        chunk_overlap: Number of characters shared between consecutive chunks
                       to preserve context across boundaries (default 200).

    Returns:
        A flat list of Document objects.  Every chunk retains the metadata from
        its source document (source, page, total_pages) so downstream steps can
        always trace a chunk back to its original page.

    Raises:
        ValueError: If documents is empty or None.
    """
    if not documents:
        raise ValueError("No documents provided to split.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        # Try these separators in order before doing a hard character split
        separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""],
        length_function=len,
    )

    chunks: List[Document] = splitter.split_documents(documents)

    if not chunks:
        raise ValueError("Splitting produced no chunks — document may be empty.")

    return chunks
