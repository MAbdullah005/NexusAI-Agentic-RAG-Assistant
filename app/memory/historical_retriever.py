"""
Historical Conversation Memory Retrieval

Provides hybrid semantic and BM25 keyword search over persistent SQLite messages.
Features:
- Incremental embedding caching in SQLite (message_embeddings table).
- BM25Okapi keyword matching with exact identifier and keyword support.
- Reciprocal Rank Fusion (RRF) combining semantic and keyword signals.
- Graceful degradation: semantic -> BM25, BM25 -> semantic, or empty fallback.
- Strict user and thread isolation.
- Untrusted context formatting to prevent prompt injection.
"""
import re
import math
import sqlite3
from typing import List, Dict, Any, Optional, Set, Tuple

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

from app.memory.config import (
    is_historical_retrieval_enabled,
    get_historical_top_k,
    get_historical_candidate_limit,
    get_historical_min_score,
    get_historical_rrf_k,
    get_historical_embedding_batch_size,
)
from app.memory.sqlite_memory import (
    conn as default_conn,
    verify_thread_ownership,
    save_message_embedding,
    get_message_embeddings,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "as", "at",
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "could", "did", "do", "does", "doing", "down", "during",
    "each", "few", "for", "from", "further",
    "had", "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "itself",
    "me", "more", "most", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very",
    "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why", "with", "would",
    "you", "your", "yours", "yourself", "yourselves"
}


def tokenize_text(text: str) -> List[str]:
    """
    Tokenize text into lowercase alphanumeric words for BM25 matching,
    filtering common English stopwords to avoid false keyword matches.
    """
    if not text:
        return []
    words = re.findall(r"\w+", text.lower())
    content_words = [w for w in words if w not in STOPWORDS]
    return content_words if content_words else words


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Calculate cosine similarity between two float vectors.
    Returns 0.0 if either vector has zero norm or length mismatch.
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def run_bm25_search(
    query: str,
    candidates: List[Dict[str, Any]],
    k1: float = 1.5,
    b: float = 0.75,
) -> List[Tuple[str, float]]:
    """
    Run BM25 keyword search over candidate messages using Lucene-style non-negative IDF.
    Guarantees positive scores for matching terms across any message count (N=1, 2, ...).
    Returns ranked list of (message_id, bm25_score) descending.
    Filters out candidates with 0 score (no query terms found).
    """
    query_tokens = tokenize_text(query)
    if not query_tokens or not candidates:
        return []

    corpus = [tokenize_text(c.get("content", "")) for c in candidates]
    N = len(corpus)
    if N == 0:
        return []

    avgdl = sum(len(doc) for doc in corpus) / N
    if avgdl == 0:
        avgdl = 1.0

    # Calculate document frequencies
    doc_freqs: Dict[str, int] = {}
    for token in set(query_tokens):
        doc_freqs[token] = sum(1 for doc in corpus if token in doc)

    results = []
    for candidate, doc in zip(candidates, corpus):
        doc_len = len(doc)
        score = 0.0
        for token in query_tokens:
            df = doc_freqs.get(token, 0)
            if df > 0 and token in doc:
                tf = doc.count(token)
                # Lucene-style BM25 non-negative IDF: ln(1 + (N - df + 0.5) / (df + 0.5))
                idf = math.log(1.0 + (N - df + 0.5) / (df + 0.5))
                term_score = idf * (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * (doc_len / avgdl)))
                score += term_score

        if score > 0.0:
            results.append((candidate["message_id"], float(score)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def run_semantic_search(
    query: str,
    candidates: List[Dict[str, Any]],
    thread_id: str,
    user_id: int,
    embedding_client: Optional[Any] = None,
    target_conn: Optional[sqlite3.Connection] = None,
    min_score: float = 0.0,
) -> List[Tuple[str, float]]:
    """
    Run semantic search using query embeddings and cached message embeddings.
    Missing message embeddings are incrementally computed and saved to SQLite.
    Returns ranked list of (message_id, cosine_similarity) descending.
    Filters out results with similarity <= 0.0 or below min_score.
    """
    if not query or not candidates:
        return []

    client = embedding_client
    if client is None:
        try:
            from app.llm.embeddings import get_embeddings
            client = get_embeddings()
        except Exception as e:
            logger.warning(f"Failed to load default embeddings client: {e}")
            return []

    if client is None:
        return []

    db = target_conn or default_conn
    candidate_mids = [c["message_id"] for c in candidates]

    # Fetch cached embeddings from SQLite
    try:
        cached_embeddings = get_message_embeddings(
            thread_id=thread_id,
            user_id=user_id,
            message_ids=candidate_mids,
            target_conn=db
        )
    except Exception as e:
        logger.warning(f"Failed to fetch cached embeddings from SQLite: {e}")
        cached_embeddings = {}

    # Identify candidate messages needing embeddings
    unembedded = [c for c in candidates if c["message_id"] not in cached_embeddings]

    if unembedded:
        batch_size = get_historical_embedding_batch_size()
        for i in range(0, len(unembedded), batch_size):
            chunk = unembedded[i:i + batch_size]
            texts = [c.get("content", "") for c in chunk]
            try:
                vectors = client.embed_documents(texts)
                for c, vec in zip(chunk, vectors):
                    cached_embeddings[c["message_id"]] = vec
                    save_message_embedding(
                        message_id=c["message_id"],
                        thread_id=thread_id,
                        user_id=user_id,
                        embedding=vec,
                        target_conn=db
                    )
            except Exception as e:
                logger.warning(f"Failed to generate embeddings for batch: {e}")
                # Continue with available cached embeddings

    # Embed user query
    try:
        query_vec = client.embed_query(query)
    except Exception as e:
        logger.warning(f"Failed to generate query embedding: {e}")
        return []

    results = []
    effective_min = max(0.0, min_score)
    for c in candidates:
        mid = c["message_id"]
        if mid in cached_embeddings:
            sim = cosine_similarity(query_vec, cached_embeddings[mid])
            if sim > effective_min:
                results.append((mid, sim))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def compute_rrf_rankings(
    semantic_ranked: List[Tuple[str, float]],
    bm25_ranked: List[Tuple[str, float]],
    rrf_k: int = 60,
    min_score: float = 0.0,
) -> List[Tuple[str, float]]:
    """
    Combine semantic and BM25 rankings using Reciprocal Rank Fusion (RRF).
    RRF score = sum(1 / (k + rank)) for each ranking list the item appears in.
    """
    rrf_scores: Dict[str, float] = {}

    for rank_idx, (mid, _) in enumerate(semantic_ranked, start=1):
        rrf_scores[mid] = rrf_scores.get(mid, 0.0) + (1.0 / (rrf_k + rank_idx))

    for rank_idx, (mid, _) in enumerate(bm25_ranked, start=1):
        rrf_scores[mid] = rrf_scores.get(mid, 0.0) + (1.0 / (rrf_k + rank_idx))

    results = []
    for mid, score in rrf_scores.items():
        if score > 0.0 and score >= min_score:
            results.append((mid, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results


def retrieve_historical_context(
    query: str,
    thread_id: str,
    user_id: int,
    exclude_message_ids: Optional[Set[str]] = None,
    exclude_contents: Optional[Set[Tuple[str, str]]] = None,
    top_k: Optional[int] = None,
    candidate_limit: Optional[int] = None,
    min_score: Optional[float] = None,
    rrf_k: Optional[int] = None,
    embedding_client: Optional[Any] = None,
    target_conn: Optional[sqlite3.Connection] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant historical conversation messages from SQLite using hybrid search.

    Parameters:
        query: The user's current question/prompt.
        thread_id: Conversation thread identifier.
        user_id: Authenticated user ID.
        exclude_message_ids: Set of message_ids currently in active LLM context.
        exclude_contents: Set of (role, content) pairs currently in active context.
        top_k: Maximum number of historical messages to return (default from config).
        candidate_limit: Max older messages to inspect (default from config).
        min_score: Minimum relevance threshold (default from config).
        rrf_k: RRF constant k (default from config).
        embedding_client: Custom embeddings client (for dependency injection/tests).
        target_conn: Custom SQLite connection (for dependency injection/tests).

    Returns:
        List of historical message dictionaries sorted chronologically (oldest to newest).
    """
    if not is_historical_retrieval_enabled():
        return []

    db = target_conn or default_conn

    # Enforce thread ownership and isolation
    if not verify_thread_ownership(thread_id, user_id, target_conn=db):
        logger.warning(
            f"Historical retrieval denied: thread '{thread_id}' not owned by user {user_id}"
        )
        return []

    clean_query = (query or "").strip()
    if not clean_query:
        return []

    effective_top_k = top_k if top_k is not None else get_historical_top_k()
    effective_limit = candidate_limit if candidate_limit is not None else get_historical_candidate_limit()
    effective_min_score = min_score if min_score is not None else get_historical_min_score()
    effective_rrf_k = rrf_k if rrf_k is not None else get_historical_rrf_k()

    exclude_ids = exclude_message_ids or set()
    exclude_content_set = exclude_contents or set()

    # Query candidate messages strictly parameterized by thread_id and user_id
    cursor = db.cursor()
    cursor.execute(
        """
        SELECT message_id, thread_id, user_id, role, content, created_at
        FROM messages
        WHERE thread_id = ? AND user_id = ?
        ORDER BY created_at DESC, rowid DESC
        LIMIT ?
        """,
        (thread_id, user_id, effective_limit)
    )
    rows = cursor.fetchall()
    if not rows:
        return []

    candidate_dict = {}
    candidates = []
    for r in rows:
        mid, tid, uid, role, content, created_at = r
        if mid in exclude_ids:
            continue
        if (role, content) in exclude_content_set:
            continue
        msg = {
            "message_id": mid,
            "thread_id": tid,
            "user_id": uid,
            "role": role,
            "content": content,
            "created_at": created_at,
        }
        candidates.append(msg)
        candidate_dict[mid] = msg

    if not candidates:
        return []

    # 1. Semantic Search
    try:
        semantic_ranked = run_semantic_search(
            query=clean_query,
            candidates=candidates,
            thread_id=thread_id,
            user_id=user_id,
            embedding_client=embedding_client,
            target_conn=db,
            min_score=effective_min_score,
        )
    except Exception as e:
        logger.warning(f"Semantic search failed unexpectedly: {e}")
        semantic_ranked = []

    # 2. BM25 Search
    try:
        bm25_ranked = run_bm25_search(
            query=clean_query,
            candidates=candidates,
        )
    except Exception as e:
        logger.warning(f"BM25 search failed unexpectedly: {e}")
        bm25_ranked = []

    # If neither method produced hits, return empty
    if not semantic_ranked and not bm25_ranked:
        return []

    # 3. Hybrid Fusion via RRF
    rrf_ranked = compute_rrf_rankings(
        semantic_ranked=semantic_ranked,
        bm25_ranked=bm25_ranked,
        rrf_k=effective_rrf_k,
        min_score=effective_min_score,
    )

    if not rrf_ranked:
        return []

    # Top K selection
    top_hits = rrf_ranked[:effective_top_k]

    selected_messages = []
    for mid, score in top_hits:
        msg = dict(candidate_dict[mid])
        msg["score"] = score
        selected_messages.append(msg)

    # Sort selected messages chronologically so conversation reads naturally
    selected_messages.sort(key=lambda m: (m.get("created_at") or "", m["message_id"]))
    return selected_messages


def format_historical_context(retrieved_messages: List[Dict[str, Any]]) -> str:
    """
    Format retrieved historical messages into a clearly delimited, untrusted context block.
    """
    if not retrieved_messages:
        return ""

    lines = [
        "Relevant earlier conversation context:",
        "---"
    ]
    for msg in retrieved_messages:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        lines.append(f"[{role}]: {content}")
    lines.append("---")
    lines.append(
        "Note: The above historical conversation turns are provided for background context only."
    )
    return "\n".join(lines)

