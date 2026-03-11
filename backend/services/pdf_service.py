from typing import List, Tuple

from langchain_core.documents import Document

from services.pdf_loader import load_pdf
from services.text_chunker import split_documents


def extract_text_from_pdf(file_path: str) -> Tuple[List[str], int]:
    """Extract text from every page of a PDF and return page strings + total page count."""
    documents = load_pdf(file_path)  # raises FileNotFoundError / ValueError on bad input
    pages_text = [doc.page_content for doc in documents]
    total_pages = documents[0].metadata["total_pages"] if documents else 0
    return pages_text, total_pages


def chunk_text(
    pages_text: List[str],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[str]:
    """Split page text strings into overlapping chunks via text_chunker."""
    documents = [
        Document(page_content=text, metadata={"page": i})
        for i, text in enumerate(pages_text)
    ]
    chunk_docs = split_documents(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return [doc.page_content for doc in chunk_docs]
