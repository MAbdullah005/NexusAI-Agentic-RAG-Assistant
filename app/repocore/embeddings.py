import asyncio
import logging
from google import genai
from google.genai import types
from .config import settings

logger = logging.getLogger(__name__)

# --- Google Gemini embedding client ---

_client = None

def _get_client():
    global _client
    if _client is None:
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            raise ValueError("GEMINI_API_KEY (or Gemini_API_Key) is not set.")
        logger.info(
            f"Initializing Google GenAI client for embeddings ({settings.EMBEDDING_DIMENSIONS}-dim: {settings.EMBEDDING_MODEL})"
        )
        _client = genai.Client(api_key=api_key)
    return _client


def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of texts using Google Gemini embedding model.
    Respects configured EMBEDDING_DIMENSIONS (768) and EMBEDDING_BATCH_SIZE (50).
    """
    if not texts:
        return []

    client = _get_client()
    batch_size = getattr(settings, "EMBEDDING_BATCH_SIZE", 50)
    config = types.EmbedContentConfig(output_dimensionality=settings.EMBEDDING_DIMENSIONS)
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=batch,
            config=config,
        )
        for emb in response.embeddings:
            all_embeddings.append(list(emb.values))

    return all_embeddings


async def embed_text(
    texts: list[str],
    **kwargs
) -> list[list[float]]:
    """Embed texts asynchronously using Google Gemini embedding model."""
    if not texts:
        return []
    return await asyncio.to_thread(embed_batch, texts)


async def embed_query(text: str) -> list[float]:
    """Embed a single query using Google Gemini embedding model."""
    result = await embed_text([text])
    return result[0] if result else []
