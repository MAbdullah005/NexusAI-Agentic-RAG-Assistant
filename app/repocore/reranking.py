from dotenv import load_dotenv
import os
import asyncio
import httpx
import logging

load_dotenv()

logger = logging.getLogger(__name__)

TIMEOUT = 30.0
RETRIES = 2

async def rerank(query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
    """Rerank documents using Jina AI Reranker API.

    Returns list of (original_index, relevance_score) sorted by relevance descending.
    If JINA_API_KEY is not set or reranker fails, gracefully falls back to ranked candidates.
    """
    if not documents:
        return []

    jina_key = os.getenv("JINA_API_KEY")
    if not jina_key:
        logger.info("JINA_API_KEY not set; preserving RRF candidate ranking.")
        return [(i, 1.0 - (i * 0.02)) for i in range(min(top_n, len(documents)))]

    url = "https://api.jina.ai/v1/rerank"
    headers = {
        "Authorization": f"Bearer {jina_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "jina-reranker-v1-base-en",
        "query": query,
        "documents": documents,
        "top_n": top_n,
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for attempt in range(RETRIES):
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 429 and attempt < RETRIES - 1:
                    await asyncio.sleep(2)
                    continue
                resp.raise_for_status()
                data = resp.json()
                results = sorted(data["results"], key=lambda x: x["relevance_score"], reverse=True)
                return [(r["index"], r["relevance_score"]) for r in results]
            except (httpx.HTTPError, KeyError) as e:
                if attempt < RETRIES - 1:
                    await asyncio.sleep(1)
                    continue
                logger.warning(f"Jina rerank failed: {e}; falling back to candidate rank order.")
                return [(i, 1.0 - (i * 0.02)) for i in range(min(top_n, len(documents)))]


def sync_rerank(query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
    """Synchronous Jina reranker with fallback."""
    if not documents:
        return []
    jina_key = os.getenv("JINA_API_KEY")
    if not jina_key:
        return [(i, 1.0 - (i * 0.02)) for i in range(min(top_n, len(documents)))]

    url = "https://api.jina.ai/v1/rerank"
    headers = {
        "Authorization": f"Bearer {jina_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "jina-reranker-v1-base-en",
        "query": query,
        "documents": documents,
        "top_n": top_n,
    }
    with httpx.Client(timeout=TIMEOUT) as client:
        for attempt in range(RETRIES):
            try:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 429 and attempt < RETRIES - 1:
                    import time
                    time.sleep(2)
                    continue
                resp.raise_for_status()
                data = resp.json()
                results = sorted(data["results"], key=lambda x: x["relevance_score"], reverse=True)
                return [(r["index"], r["relevance_score"]) for r in results]
            except Exception as e:
                logger.warning(f"Jina rerank sync error: {e}")
                return [(i, 1.0 - (i * 0.02)) for i in range(min(top_n, len(documents)))]
    return [(i, 1.0 - (i * 0.02)) for i in range(min(top_n, len(documents)))]
