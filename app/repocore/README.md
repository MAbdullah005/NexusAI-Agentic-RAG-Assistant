# RepoGuide

**Understand any codebase like someone who built it explained it to you.**

RepoGuide is an AI-powered GitHub repository assistant that helps developers understand unfamiliar codebases through natural-language questions. It retrieves relevant code and explains how files, functions, and components work together, with clickable GitHub links to the exact source lines.

## Key Features

- **GitHub Repository Indexing** — Clones and indexes source files while filtering unnecessary build and dependency files.
- **Hybrid RAG Retrieval** — Combines semantic search, PostgreSQL full-text search, and filename matching using Reciprocal Rank Fusion (RRF).
- **Context-Aware Code Understanding** — Expands relevant code chunks with neighboring lines and uses Jina AI reranking to improve relevance.
- **Grounded AI Answers** — Uses Google Gemini to explain retrieved code and provides commit-specific GitHub source links with line ranges.
- **Conversation Memory** — Supports follow-up questions using conversation history and summaries.
- **Secure Authentication** — JWT access tokens, rotating refresh tokens, and user-level resource isolation.
- **Persistent Storage** — PostgreSQL and pgvector store repository chunks, embeddings, conversations, messages, and application data.
- **Modern Web Interface** — Next.js and React frontend with authentication, repository workspaces, chat, and source references.

## Tech Stack

**Backend:** Python, FastAPI, SQLAlchemy, Alembic  
**Frontend:** Next.js 15, React 19, TypeScript  
**AI & Retrieval:** Google Gemini, LangChain, Sentence Transformers, Jina AI Reranker, RAG, RRF  
**Database:** PostgreSQL, pgvector, PostgreSQL Full-Text Search  
**Security:** JWT, bcrypt  
**Integration:** GitHub REST API, Git

## How It Works

1. Submit a GitHub repository URL.
2. RepoGuide filters, chunks, and embeds relevant source files.
3. Ask questions in natural language.
4. Hybrid retrieval finds relevant code, expands context, and reranks results.
5. Gemini generates an explanation grounded in the retrieved code.
6. RepoGuide provides clickable GitHub links to the referenced files and line ranges.

## Getting Started

### Prerequisites
- Python 3.12
- Node.js 18+
- Git
- PostgreSQL with the pgvector extension
- Google Gemini API key
- Jina AI API key

### Backend

```bash
python -m venv .venv
# Activate the virtual environment
pip install -r backend/requirements.txt
cp .env.example .env
alembic -c backend/alembic.ini upgrade head
uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Configure the required environment variables in the backend and frontend `.env` files before running the application.

## Project Goal

RepoGuide makes codebase exploration, technical onboarding, and architecture understanding faster by turning real repository code into interactive, source-grounded explanations.