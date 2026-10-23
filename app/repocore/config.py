import os
from dotenv import load_dotenv

load_dotenv()

# --- env + constants ---
class Settings:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("Gemini_API_Key")
    JINA_API_KEY = os.getenv("JINA_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")
    JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRES_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS = 30
    EMBEDDING_MODEL = os.getenv("REPO_EMBEDDING_MODEL", "models/gemini-embedding-001")
    EMBEDDING_DIMENSIONS = int(os.getenv("REPO_EMBEDDING_DIMENSIONS", "768"))
    EMBEDDING_BATCH_SIZE = int(os.getenv("REPO_EMBEDDING_BATCH_SIZE", "50"))
    EMBEDDING_MAX_CONCURRENCY = 1
    LLM_MODEL = os.getenv("REPO_LLM_MODEL", os.getenv("DEFAULT_GEMINI_MODEL", "gemini-2.5-flash"))

settings = Settings()
