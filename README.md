# AI Research PDF Chat Platform

A production-ready, full-stack AI application that lets users upload research PDFs and ask questions using Retrieval-Augmented Generation (RAG). Users can also search arXiv for research papers and generate AI summaries — all with per-user authentication and persistent storage.

---

## Features

- **PDF Upload & Chat** — Upload multiple PDFs; ask questions answered with source citations
- **Multi-document RAG** — FAISS vector search across all your documents simultaneously
- **Source Citations** — Every answer includes the filename and page number of supporting excerpts
- **arXiv Research Search** — Search papers by keyword; view abstracts and PDF links
- **AI Paper Summarization** — One-click structured summaries (contributions, methods, results)
- **User Authentication** — JWT-based registration and login; every user sees only their own documents
- **Persistent Storage** — PostgreSQL for users/documents/chat/search history; FAISS indexes on disk
- **Docker Deployment** — Single `docker compose up` brings up the full stack

---

## Architecture

```
+-------------------------------------------------------------+
|                        Browser                              |
|   React 18 + Vite + Tailwind CSS                            |
|  +----------------+ +------------------+ +---------------+  |
|  |  AuthPage      | |  PDF Chat        | | Research      |  |
|  |  (JWT login)   | |  (Upload+Chat)   | | Search        |  |
|  +----------------+ +------------------+ +---------------+  |
+----------------------------+--------------------------------+
                             | HTTP/REST (Bearer JWT)
+----------------------------v--------------------------------+
|                    FastAPI (Python 3.11)                    |
|                                                            |
|  POST /api/register   POST /api/login                      |
|  POST /api/upload [*]  GET  /api/documents [*]             |
|  POST /api/ask    [*]  GET  /api/search_papers             |
|  POST /api/summarize                                       |
|                                                            |
|  [*] = JWT-protected                                       |
|                                                            |
|  +------------------------------------------------------+  |
|  |  RAG Pipeline                                        |  |
|  |  PDF > pypdf > text_chunker > sentence-transformers  |  |
|  |  > FAISS (per-user, on-disk) > gpt-3.5-turbo        |  |
|  +------------------------------------------------------+  |
+----------+-----------------------------+--------------------+
           |                             |
+----------v----------+     +-----------v---------+
|  PostgreSQL          |     |  Filesystem         |
|  * users             |     |  * vector_db/       |
|  * documents         |     |    <uuid>/           |
|  * chat_history      |     |    index.faiss       |
|  * search_history    |     |    chunks.pkl        |
+---------------------+     +---------------------+
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS v3, Axios |
| Backend | FastAPI, Python 3.11, Uvicorn |
| Auth | python-jose (JWT HS256), passlib/bcrypt |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` |
| Vector DB | FAISS (faiss-cpu, IndexFlatIP / cosine similarity) |
| LLM | OpenAI `gpt-3.5-turbo` via LangChain LCEL |
| Database | PostgreSQL 15 + SQLAlchemy 2 |
| Deployment | Docker, Nginx, docker-compose |

---

## Local Development (without Docker)

### Prerequisites

- Python 3.11+
- Node.js 20+
- An [OpenAI API key](https://platform.openai.com/api-keys)

### 1 — Clone and configure

```bash
git clone <repo-url>
cd Project-1
cp .env.example .env
# Edit .env: fill in OPENAI_API_KEY and SECRET_KEY
```

### 2 — Backend

```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API: http://localhost:8000  
Swagger UI: http://localhost:8000/docs

> **Database:** SQLite (`backend/app.db`) is used by default. Set `DATABASE_URL` in `.env` for PostgreSQL.

### 3 — Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:5173

---

## Docker Deployment

### Prerequisites

- Docker 24+  
- Docker Compose v2

### 1 — Configure environment

```bash
cp .env.example .env
# Fill in: OPENAI_API_KEY, SECRET_KEY, POSTGRES_USER, POSTGRES_PASSWORD
```

### 2 — Build and start

```bash
docker compose up --build -d
```

| Service | URL |
|---------|-----|
| Frontend (Nginx) | http://localhost |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

### 3 — Stop

```bash
docker compose down       # keep database volume
docker compose down -v    # also delete database volume
```

---

## Cloud Deployment

### AWS (EC2 + RDS)

1. Launch an EC2 instance (t3.small+, Ubuntu 22.04).
2. Create an RDS PostgreSQL instance; copy the connection string.
3. Set `DATABASE_URL=postgresql://user:pass@rds-endpoint:5432/aipdfchat` in `.env`.
4. Copy the project to EC2 and run `docker compose up --build -d`.
5. Point your domain at the EC2 IP; add Certbot/Nginx for HTTPS termination.

### Railway / Render / Fly.io

1. Connect the `backend/` directory to the platform.
2. Set environment variables: `OPENAI_API_KEY`, `SECRET_KEY`, `DATABASE_URL`.
3. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`.
4. Deploy the frontend as a static site: `npm run build`, serve `dist/`.

---

## API Documentation

Full interactive documentation: `/docs` (Swagger UI) and `/redoc`.

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/register` | Create account; returns JWT token |
| `POST` | `/api/login` | Authenticate; returns JWT token |

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

**Register / Login request body:**
```json
{ "username": "alice", "email": "alice@example.com", "password": "secret" }
```

**Response:**
```json
{ "access_token": "eyJ...", "token_type": "bearer", "username": "alice" }
```

### Documents (protected)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload a PDF (`multipart/form-data`, field `file`) |
| `GET` | `/api/documents` | List your documents |

### Question Answering (protected)

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/api/ask` | `{"question": "...", "document_id": null}` | RAG answer with citations |

Set `document_id` to restrict search to a single document.

**Response:**
```json
{
  "answer": "The paper proposes...",
  "sources": [
    { "content": "...", "index": 0, "filename": "paper.pdf", "page": 4 }
  ],
  "documents_searched": 3
}
```

### Research (public)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/search_papers?query=transformers&max_results=10` | Search arXiv |
| `POST` | `/api/summarize` | AI summary of text |

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `SECRET_KEY` | Yes | dev key | JWT signing secret (min 32 chars) |
| `DATABASE_URL` | No | SQLite | SQLAlchemy connection string |
| `POSTGRES_USER` | Docker | `aipdfuser` | PostgreSQL user (compose) |
| `POSTGRES_PASSWORD` | Docker | `changeme` | PostgreSQL password (compose) |

---

## Project Structure

```
Project-1/
+-- backend/
|   +-- auth/               # JWT handler + FastAPI dependencies
|   +-- db/                 # SQLAlchemy engine + ORM models
|   +-- models/schemas.py   # Pydantic request/response models
|   +-- routers/
|   |   +-- auth.py         # POST /register, POST /login
|   |   +-- upload.py       # POST /upload, GET /documents
|   |   +-- ask.py          # POST /ask (RAG + auth)
|   |   +-- chat.py         # POST /chat (single-doc)
|   |   +-- research.py     # GET /search_papers, POST /summarize
|   +-- services/
|   |   +-- rag_pipeline.py     # Retrieval + generation pipeline
|   |   +-- vector_store.py     # FAISS wrapper (persistent on disk)
|   |   +-- embeddings.py       # sentence-transformers wrapper
|   |   +-- research_search.py  # arXiv API + LLM summarization
|   +-- Dockerfile
|   +-- requirements.txt
+-- frontend/
|   +-- src/
|   |   +-- components/
|   |   |   +-- AuthPage.jsx        # Login / register UI
|   |   |   +-- Header.jsx          # Top bar + logout button
|   |   |   +-- PDFUpload.jsx       # Multi-doc upload panel
|   |   |   +-- ChatWindow.jsx      # Chat interface
|   |   |   +-- ChatMessage.jsx     # Message bubble + source citations
|   |   |   +-- ResearchSearch.jsx  # arXiv search + AI summary
|   |   +-- api/api.js              # Axios client + auth helpers
|   |   +-- App.jsx                 # Root: auth gate + tab navigation
|   +-- Dockerfile
|   +-- nginx.conf
+-- docker-compose.yml
+-- .env.example
+-- README.md
```

---

## Database Schema

```
users              documents            chat_history         search_history
-----------------  -------------------  -------------------  -------------------
id (PK)            id (PK)              id (PK)              id (PK)
username           user_id (FK->users)  user_id (FK->users)  user_id (FK->users)
email              document_id (UUID)   document_id (UUID?)  query
hashed_password    filename             question             results_count
created_at         pages                answer               created_at
                   chunks               created_at
                   created_at
```
