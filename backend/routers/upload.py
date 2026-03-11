import json
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import Document as DBDocument
from db.models import User
from models.schemas import DocumentInfo, DocumentResponse, ListDocumentsResponse
from services.embeddings import generate_embeddings
from services.pdf_loader import load_pdf
from services.text_chunker import split_documents
from services.vector_store import (
    VECTOR_DB_DIR,
    create_vector_store,
    save_vector_store,
    vector_store_path,
)

router = APIRouter()

UPLOADS_DIR = "uploads"
MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB

# JSON file that tracks all uploaded document metadata.
_REGISTRY_PATH = os.path.join(VECTOR_DB_DIR, "registry.json")


def _load_registry() -> dict:
    """Return the registry dict, creating it if absent."""
    if os.path.exists(_REGISTRY_PATH):
        try:
            with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_registry(registry: dict) -> None:
    os.makedirs(VECTOR_DB_DIR, exist_ok=True)
    with open(_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)


@router.get("/documents", response_model=ListDocumentsResponse)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return metadata for every document uploaded by the current user."""
    rows = (
        db.query(DBDocument)
        .filter(DBDocument.user_id == current_user.id)
        .order_by(DBDocument.created_at.desc())
        .all()
    )
    docs = [
        DocumentInfo(
            document_id=row.document_id,
            filename=row.filename,
            pages=row.pages,
            chunks=row.chunks,
        )
        for row in rows
    ]
    return ListDocumentsResponse(documents=docs, total=len(docs))


@router.post("/upload", response_model=DocumentResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # --- 1. Validate file type ---
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    document_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOADS_DIR, f"{document_id}.pdf")

    try:
        # --- 2. Read & size-check uploaded bytes ---
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        if len(content) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="File too large. Maximum allowed size is 50 MB.",
            )

        # --- 3. Save to disk ---
        with open(file_path, "wb") as f:
            f.write(content)

        # --- 4. Extract text via pdf_loader (returns List[Document]) ---
        documents = await run_in_threadpool(load_pdf, file_path)
        num_pages = documents[0].metadata["total_pages"]

        # Inject original filename into every page's metadata so chunks
        # carry it through to the vector store and citations.
        original_filename = file.filename
        for doc in documents:
            doc.metadata["filename"] = original_filename

        # --- 5. Split documents into overlapping chunks ---
        chunk_docs = await run_in_threadpool(split_documents, documents)

        # --- 6. Generate embeddings for each chunk ---
        embeddings = await run_in_threadpool(generate_embeddings, chunk_docs)

        # --- 7. Build FAISS vector store and persist to vector_db/ ---
        store = create_vector_store(chunk_docs, embeddings)
        store_path = vector_store_path(document_id)
        await run_in_threadpool(save_vector_store, store, store_path)

        # --- 8. Register document metadata (registry.json + DB) ---
        registry = _load_registry()
        registry[document_id] = {
            "filename": original_filename,
            "pages": num_pages,
            "chunks": len(chunk_docs),
        }
        _save_registry(registry)

        db_doc = DBDocument(
            user_id=current_user.id,
            document_id=document_id,
            filename=original_filename,
            pages=num_pages,
            chunks=len(chunk_docs),
        )
        db.add(db_doc)
        db.commit()

        return DocumentResponse(
            document_id=document_id,
            filename=original_filename,
            pages=num_pages,
            chunks=len(chunk_docs),
            status="ready",
            message=(
                f"Document processed successfully. "
                f"Extracted {len(documents)} page(s) → {len(chunk_docs)} chunks. "
                f"You can now ask questions!"
            ),
        )

    except HTTPException:
        raise
    except (ValueError, FileNotFoundError) as exc:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        # Clean up orphaned file on failure
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {exc}",
        )
