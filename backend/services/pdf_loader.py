"""
pdf_loader.py — PDF loading and text extraction using LangChain Document objects.

Uses pypdf for reliable text extraction on all Python versions, and wraps the
output as langchain_core Document objects so this module is fully compatible
with the rest of the LangChain ecosystem.
"""

import os
from typing import List

import pypdf
from langchain_core.documents import Document


def load_pdf(file_path: str) -> List[Document]:
    """
    Load a PDF file and extract text from every page.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        A list of Document objects, one per page, each with:
          - page_content: the extracted text of that page
          - metadata: {"source": file_path, "page": <0-based page index>}

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file is not a PDF or contains no extractable text.
        RuntimeError: If extraction fails for any other reason.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_path.lower().endswith(".pdf"):
        raise ValueError(f"Not a PDF file: {file_path}")

    try:
        documents: List[Document] = []

        with open(file_path, "rb") as f:
            reader = pypdf.PdfReader(f)

            if len(reader.pages) == 0:
                raise ValueError("The PDF file contains no pages.")

            for page_num, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                text = text.strip()

                if text:
                    documents.append(
                        Document(
                            page_content=text,
                            metadata={
                                "source": file_path,
                                "page": page_num,
                                "total_pages": len(reader.pages),
                            },
                        )
                    )

        if not documents:
            raise ValueError(
                "No extractable text found in the PDF. "
                "The file may be scanned or image-based."
            )

        return documents

    except (FileNotFoundError, ValueError):
        raise
    except Exception as exc:
        raise RuntimeError(f"Failed to extract text from PDF: {exc}") from exc
