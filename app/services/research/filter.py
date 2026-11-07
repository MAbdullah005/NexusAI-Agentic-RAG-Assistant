"""
Content Relevance Filter for Deep Research Mode.
Chunks extracted text, removes duplicates and irrelevant content,
and ranks evidence for high-quality report generation.
"""

from typing import List, Dict, Any, Set
import re
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Boilerplate / low-value phrases to exclude
STOP_PATTERNS = [
    r"cookie policy", r"all rights reserved", r"privacy policy",
    r"terms of use", r"subscribe to our newsletter", r"sign up for free",
    r"click here to read", r"share on facebook", r"share on twitter",
    r"advertisement", r"sponsored content", r"skip to main content"
]


def extract_keywords(text: str) -> Set[str]:
    """Extract lowercased significant words from query or text."""
    words = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower())
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "are", "was",
        "were", "what", "which", "how", "why", "when", "where", "about",
        "can", "will", "would", "should", "their", "there", "have", "been",
        "into", "some", "than", "them", "then", "also", "more", "most"
    }
    return {w for w in words if w not in stopwords}


def chunk_text(text: str, max_words: int = 250) -> List[str]:
    """Split text into coherent paragraphs/chunks of up to max_words."""
    # Split by double newline first, or single newline, or sentence periods
    raw_blocks = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if len(p.strip()) > 30]
    if not raw_blocks:
        raw_blocks = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if len(p.strip()) > 30]

    chunks = []
    current_chunk = []
    current_words = 0

    for b in raw_blocks:
        words = b.split()
        if not words:
            continue
        # If an individual block is too large, break it down by words
        if len(words) > max_words:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_words = 0
            for i in range(0, len(words), max_words):
                slice_words = words[i:i + max_words]
                if len(slice_words) > 20:
                    chunks.append(" ".join(slice_words))
            continue

        if current_words + len(words) <= max_words:
            current_chunk.append(b)
            current_words += len(words)
        else:
            if current_chunk:
                chunks.append(" ".join(current_chunk))
            current_chunk = [b]
            current_words = len(words)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def score_relevance(
    chunk: str,
    query_keywords: Set[str],
    subquery_keywords: Set[str]
) -> float:
    """
    Compute a normalized relevance score for a chunk against query and subquery keywords.
    """
    chunk_lower = chunk.lower()

    # Penalize boilerplate
    for pat in STOP_PATTERNS:
        if re.search(pat, chunk_lower):
            return 0.05

    chunk_words = extract_keywords(chunk)
    if not chunk_words:
        return 0.0

    # Main query overlap has higher weight
    main_matches = len(query_keywords & chunk_words)
    sub_matches = len(subquery_keywords & chunk_words)

    score = (main_matches * 2.0 + sub_matches * 1.0) / (len(query_keywords) + len(subquery_keywords) or 1.0)
    return min(1.0, score)


def filter_and_rank_evidence(
    sources: List[Dict[str, Any]],
    research_query: str,
    sub_queries: List[str],
    max_evidence_chunks: int = 15,
    max_total_chars: int = 18000
) -> List[Dict[str, Any]]:
    """
    Filter, deduplicate, and rank evidence across web, arXiv, and document sources.

    Returns:
        List of evidence dicts sorted by relevance:
        [{
            "title": str,
            "url": str,
            "source_type": str,
            "published_date": str,
            "authors": List[str],
            "text": str,
            "score": float
        }]
    """
    query_keywords = extract_keywords(research_query)
    subquery_keywords = set()
    for sq in sub_queries:
        subquery_keywords.update(extract_keywords(sq))

    all_candidate_chunks = []
    seen_fingerprints = set()

    for src in sources:
        title = src.get("title") or "Source"
        url = src.get("url") or ""
        source_type = src.get("source_type") or "web"
        published_date = src.get("published_date")
        authors = src.get("authors") or []
        full_text = src.get("text") or src.get("snippet") or ""

        if not full_text or len(full_text.strip()) < 50:
            continue

        # Chunk the source content
        chunks = chunk_text(full_text)

        for chunk in chunks:
            # Simple fingerprinting to deduplicate repetitive content
            fingerprint = " ".join(chunk.lower().split()[:15])
            if fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)

            score = score_relevance(chunk, query_keywords, subquery_keywords)
            # Give slight boost to arXiv academic papers and local documents
            if source_type in ("arxiv", "document"):
                score = min(1.0, score + 0.15)

            if score > 0.10 or len(chunks) == 1:
                all_candidate_chunks.append({
                    "title": title,
                    "url": url,
                    "source_type": source_type,
                    "published_date": published_date,
                    "authors": authors,
                    "text": chunk,
                    "score": round(score, 3),
                })

    # Sort descending by score
    all_candidate_chunks.sort(key=lambda x: x["score"], reverse=True)

    # Pick top chunks up to budget, maintaining source diversity
    curated = []
    total_chars = 0
    source_counts = {}

    for chunk_item in all_candidate_chunks:
        url_key = chunk_item.get("url") or chunk_item.get("title")
        # Allow at most 3 chunks from the exact same URL to ensure multi-source coverage
        if source_counts.get(url_key, 0) >= 3:
            continue

        chunk_len = len(chunk_item["text"])
        if total_chars + chunk_len > max_total_chars:
            break
        curated.append(chunk_item)
        source_counts[url_key] = source_counts.get(url_key, 0) + 1
        total_chars += chunk_len
        if len(curated) >= max_evidence_chunks:
            break

    logger.info(
        f"[DEEP RESEARCH FILTER] Curated {len(curated)} evidence items from {len(sources)} sources "
        f"({total_chars} chars total)"
    )
    return curated
