import sys

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.auth.routes import router as auth_router
from app.repocore.main import router as repo_router


app = FastAPI(
    title="NexusAI & RepoGuide API"
)

# Enable CORS for Next.js frontend (default port 3000) and legacy Streamlit (8501)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Main chatbot APIs
app.include_router(api_router)

# Authentication APIs
app.include_router(auth_router)

# RepoGuide GitHub Repository & Q&A APIs
app.include_router(repo_router)
