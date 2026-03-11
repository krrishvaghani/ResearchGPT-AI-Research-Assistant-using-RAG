from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from db.database import Base, engine
from routers import ask, auth, chat, research, research_assistant, upload

# Create all database tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Research & PDF Chat Platform",
    description="Upload research papers and ask questions using Retrieval-Augmented Generation.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure storage directories exist on startup
os.makedirs("uploads", exist_ok=True)
os.makedirs("vector_stores", exist_ok=True)
os.makedirs("vector_db", exist_ok=True)

app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(ask.router, prefix="/api", tags=["Ask"])
app.include_router(research.router, prefix="/api", tags=["Research"])
app.include_router(research_assistant.router, prefix="/api", tags=["Research Assistant"])


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "API is running"}
