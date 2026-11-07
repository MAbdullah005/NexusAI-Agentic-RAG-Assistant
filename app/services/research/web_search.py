"""
Web Search Service for Deep Research Mode.
Retrieves web search results using Tavily (primary) with DuckDuckGo fallback.
"""

from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv

from app.tools.search_tool import search_tool
from app.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


def search_web(
    query: str,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """
    Search the web for a given query and return normalized results.

    Returns:
        List of dicts with keys: title, url, snippet, source_type, published_date
    """
    logger.info(f"[DEEP RESEARCH WEB] Searching query='{query}' (max_results={max_results})")
    cleaned_query = query.strip()
    if not cleaned_query:
        return []

    results = []
    try:
        raw_results = search_tool.invoke({"query": cleaned_query})
        
        if isinstance(raw_results, list):
            for item in raw_results:
                if not isinstance(item, dict):
                    continue
                url = item.get("url") or ""
                if not url or not url.startswith("http"):
                    continue
                results.append({
                    "title": item.get("title") or "Web Source",
                    "url": url,
                    "snippet": item.get("content") or "",
                    "source_type": "web",
                    "published_date": item.get("published_date") or None,
                    "score": item.get("score") or 0.0,
                })
        elif isinstance(raw_results, str) and raw_results and not raw_results.startswith("Unable to retrieve"):
            # Text result from fallback search
            results.append({
                "title": f"Web Result for {cleaned_query[:40]}",
                "url": "https://duckduckgo.com/?q=" + cleaned_query.replace(" ", "+"),
                "snippet": raw_results[:800],
                "source_type": "web",
                "published_date": None,
                "score": 0.5,
            })
    except Exception as e:
        logger.warning(f"[DEEP RESEARCH WEB] Search failed for query '{cleaned_query}': {e}")

    # Deduplicate by URL
    seen_urls = set()
    deduped = []
    for r in results:
        u = r["url"].lower().rstrip("/")
        if u not in seen_urls:
            seen_urls.add(u)
            deduped.append(r)
        if len(deduped) >= max_results:
            break

    logger.info(f"[DEEP RESEARCH WEB] Retrieved {len(deduped)} distinct results for '{cleaned_query}'")
    return deduped

