"""
Conversation Memory Configuration

Centralized settings for conversation memory thresholds and window sizes.
Values can be overridden using environment variables:
    MEMORY_RECENT_MESSAGE_WINDOW: Number of recent messages to retain in active state (default: 6).
    MEMORY_MAX_MESSAGES_BEFORE_SUMMARY: Number of messages before summarization triggers (default: 12).
"""
import os
from typing import Dict, Any
from app.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_RECENT_MESSAGE_WINDOW = 6
DEFAULT_MAX_MESSAGES_BEFORE_SUMMARY = 12

DEFAULT_HISTORICAL_RETRIEVAL_ENABLED = True
DEFAULT_HISTORICAL_TOP_K = 5
DEFAULT_HISTORICAL_CANDIDATE_LIMIT = 100
DEFAULT_HISTORICAL_MIN_SCORE = 0.0
DEFAULT_HISTORICAL_RRF_K = 60
DEFAULT_HISTORICAL_EMBEDDING_BATCH_SIZE = 16


def is_historical_retrieval_enabled() -> bool:
    """
    Check whether historical memory retrieval is enabled.
    Defaults to True. Can be disabled via MEMORY_HISTORICAL_RETRIEVAL_ENABLED='false'.
    """
    val = os.getenv("MEMORY_HISTORICAL_RETRIEVAL_ENABLED")
    if val is None:
        val = os.getenv("HISTORICAL_RETRIEVAL_ENABLED")
    if val is not None:
        clean = str(val).strip().lower()
        if clean in ("1", "true", "yes", "on"):
            return True
        if clean in ("0", "false", "no", "off"):
            return False
        logger.warning(
            f"Invalid boolean value for MEMORY_HISTORICAL_RETRIEVAL_ENABLED '{val}'. "
            f"Falling back to default: {DEFAULT_HISTORICAL_RETRIEVAL_ENABLED}"
        )
    return DEFAULT_HISTORICAL_RETRIEVAL_ENABLED


def get_historical_top_k() -> int:
    """
    Get the configured maximum number of historical messages to inject into context.
    Validates that the value is an integer >= 1.
    """
    val = os.getenv("MEMORY_HISTORICAL_TOP_K")
    if val is not None:
        try:
            parsed = int(str(val).strip())
            if parsed >= 1:
                return parsed
            logger.warning(
                f"Invalid MEMORY_HISTORICAL_TOP_K '{val}': must be >= 1. "
                f"Falling back to default: {DEFAULT_HISTORICAL_TOP_K}"
            )
        except ValueError:
            logger.warning(
                f"Invalid MEMORY_HISTORICAL_TOP_K '{val}': not an integer. "
                f"Falling back to default: {DEFAULT_HISTORICAL_TOP_K}"
            )
    return DEFAULT_HISTORICAL_TOP_K


def get_historical_candidate_limit() -> int:
    """
    Get the maximum number of historical candidate messages to fetch from SQLite for ranking.
    Validates that the value is an integer >= 1.
    """
    val = os.getenv("MEMORY_HISTORICAL_CANDIDATE_LIMIT")
    if val is not None:
        try:
            parsed = int(str(val).strip())
            if parsed >= 1:
                return parsed
            logger.warning(
                f"Invalid MEMORY_HISTORICAL_CANDIDATE_LIMIT '{val}': must be >= 1. "
                f"Falling back to default: {DEFAULT_HISTORICAL_CANDIDATE_LIMIT}"
            )
        except ValueError:
            logger.warning(
                f"Invalid MEMORY_HISTORICAL_CANDIDATE_LIMIT '{val}': not an integer. "
                f"Falling back to default: {DEFAULT_HISTORICAL_CANDIDATE_LIMIT}"
            )
    return DEFAULT_HISTORICAL_CANDIDATE_LIMIT


def get_historical_min_score() -> float:
    """
    Get the minimum relevance threshold score for historical retrieval.
    Validates that the value is a float >= 0.0.
    """
    val = os.getenv("MEMORY_HISTORICAL_MIN_SCORE")
    if val is not None:
        try:
            parsed = float(str(val).strip())
            if parsed >= 0.0:
                return parsed
            logger.warning(
                f"Invalid MEMORY_HISTORICAL_MIN_SCORE '{val}': must be >= 0.0. "
                f"Falling back to default: {DEFAULT_HISTORICAL_MIN_SCORE}"
            )
        except ValueError:
            logger.warning(
                f"Invalid MEMORY_HISTORICAL_MIN_SCORE '{val}': not a valid float. "
                f"Falling back to default: {DEFAULT_HISTORICAL_MIN_SCORE}"
            )
    return DEFAULT_HISTORICAL_MIN_SCORE


def get_historical_rrf_k() -> int:
    """
    Get the constant k for Reciprocal Rank Fusion (RRF).
    Validates that the value is an integer >= 1.
    """
    val = os.getenv("MEMORY_HISTORICAL_RRF_K")
    if val is not None:
        try:
            parsed = int(str(val).strip())
            if parsed >= 1:
                return parsed
            logger.warning(
                f"Invalid MEMORY_HISTORICAL_RRF_K '{val}': must be >= 1. "
                f"Falling back to default: {DEFAULT_HISTORICAL_RRF_K}"
            )
        except ValueError:
            logger.warning(
                f"Invalid MEMORY_HISTORICAL_RRF_K '{val}': not an integer. "
                f"Falling back to default: {DEFAULT_HISTORICAL_RRF_K}"
            )
    return DEFAULT_HISTORICAL_RRF_K


def get_historical_embedding_batch_size() -> int:
    """
    Get the batch size for embedding historical messages.
    Validates that the value is an integer >= 1.
    """
    val = os.getenv("MEMORY_HISTORICAL_EMBEDDING_BATCH_SIZE")
    if val is not None:
        try:
            parsed = int(str(val).strip())
            if parsed >= 1:
                return parsed
            logger.warning(
                f"Invalid MEMORY_HISTORICAL_EMBEDDING_BATCH_SIZE '{val}': must be >= 1. "
                f"Falling back to default: {DEFAULT_HISTORICAL_EMBEDDING_BATCH_SIZE}"
            )
        except ValueError:
            logger.warning(
                f"Invalid MEMORY_HISTORICAL_EMBEDDING_BATCH_SIZE '{val}': not an integer. "
                f"Falling back to default: {DEFAULT_HISTORICAL_EMBEDDING_BATCH_SIZE}"
            )
    return DEFAULT_HISTORICAL_EMBEDDING_BATCH_SIZE


def get_recent_message_window() -> int:
    """
    Get the configured number of recent conversation messages to keep in active memory.
    Validates that the value is an integer >= 2. Falls back to default if invalid.
    """
    val = os.getenv("MEMORY_RECENT_MESSAGE_WINDOW") or os.getenv("RECENT_MESSAGES_WINDOW")
    if val is not None:
        try:
            parsed = int(str(val).strip())
            if parsed >= 2:
                return parsed
            logger.warning(
                f"Invalid MEMORY_RECENT_MESSAGE_WINDOW '{val}': must be >= 2. "
                f"Falling back to default: {DEFAULT_RECENT_MESSAGE_WINDOW}"
            )
        except ValueError:
            logger.warning(
                f"Invalid MEMORY_RECENT_MESSAGE_WINDOW '{val}': not an integer. "
                f"Falling back to default: {DEFAULT_RECENT_MESSAGE_WINDOW}"
            )
    return DEFAULT_RECENT_MESSAGE_WINDOW


def get_summarization_threshold() -> int:
    """
    Get the configured message count threshold that triggers memory summarization.
    Validates that the value is an integer > recent_message_window.
    """
    recent_window = get_recent_message_window()
    val = os.getenv("MEMORY_MAX_MESSAGES_BEFORE_SUMMARY") or os.getenv("MAX_MESSAGES_BEFORE_SUMMARY")
    if val is not None:
        try:
            parsed = int(str(val).strip())
            if parsed > recent_window:
                return parsed
            logger.warning(
                f"Invalid MEMORY_MAX_MESSAGES_BEFORE_SUMMARY '{val}': must be > recent window ({recent_window}). "
                f"Falling back to default: {DEFAULT_MAX_MESSAGES_BEFORE_SUMMARY}"
            )
        except ValueError:
            logger.warning(
                f"Invalid MEMORY_MAX_MESSAGES_BEFORE_SUMMARY '{val}': not an integer. "
                f"Falling back to default: {DEFAULT_MAX_MESSAGES_BEFORE_SUMMARY}"
            )

    # Ensure default summarization threshold is strictly greater than recent_window
    if DEFAULT_MAX_MESSAGES_BEFORE_SUMMARY <= recent_window:
        return recent_window + 2
    return DEFAULT_MAX_MESSAGES_BEFORE_SUMMARY


def get_memory_config() -> Dict[str, Any]:
    """
    Return dictionary of current memory configuration settings.
    """
    recent_window = get_recent_message_window()
    max_threshold = get_summarization_threshold()
    return {
        "recent_messages_to_retain": recent_window,
        "summarization_threshold": max_threshold,
        "historical_retrieval_enabled": is_historical_retrieval_enabled(),
        "historical_top_k": get_historical_top_k(),
        "historical_candidate_limit": get_historical_candidate_limit(),
        "historical_min_score": get_historical_min_score(),
        "historical_rrf_k": get_historical_rrf_k(),
        "historical_embedding_batch_size": get_historical_embedding_batch_size(),
    }


# ============================================================
# RAG CHUNKING & RETRIEVAL CONFIGURATION
# ============================================================

DEFAULT_RAG_CHUNK_SIZE = 1000
DEFAULT_RAG_CHUNK_OVERLAP = 200
DEFAULT_RAG_TOP_K = 6
DEFAULT_RAG_MIN_SCORE = 0.0
DEFAULT_RAG_RERANKING_ENABLED = False


def get_rag_chunk_size() -> int:
    """
    Get the configured chunk size for document splitting.
    Validates that the value is an integer >= 100.
    """
    val = os.getenv("RAG_CHUNK_SIZE")
    if val is not None:
        try:
            parsed = int(str(val).strip())
            if parsed >= 100:
                return parsed
            logger.warning(
                f"Invalid RAG_CHUNK_SIZE '{val}': must be >= 100. "
                f"Falling back to default: {DEFAULT_RAG_CHUNK_SIZE}"
            )
        except ValueError:
            logger.warning(
                f"Invalid RAG_CHUNK_SIZE '{val}': not an integer. "
                f"Falling back to default: {DEFAULT_RAG_CHUNK_SIZE}"
            )
    return DEFAULT_RAG_CHUNK_SIZE


def get_rag_chunk_overlap() -> int:
    """
    Get the configured chunk overlap for document splitting.
    Validates that the value is an integer >= 0 and strictly less than chunk size.
    """
    chunk_size = get_rag_chunk_size()
    val = os.getenv("RAG_CHUNK_OVERLAP")
    if val is not None:
        try:
            parsed = int(str(val).strip())
            if 0 <= parsed < chunk_size:
                return parsed
            logger.warning(
                f"Invalid RAG_CHUNK_OVERLAP '{val}': must be >= 0 and < chunk_size ({chunk_size}). "
                f"Falling back to default: {DEFAULT_RAG_CHUNK_OVERLAP}"
            )
        except ValueError:
            logger.warning(
                f"Invalid RAG_CHUNK_OVERLAP '{val}': not an integer. "
                f"Falling back to default: {DEFAULT_RAG_CHUNK_OVERLAP}"
            )
    return DEFAULT_RAG_CHUNK_OVERLAP


def get_rag_top_k() -> int:
    """
    Get the configured number of top document chunks to retrieve for RAG context.
    Validates that the value is an integer >= 1.
    """
    val = os.getenv("RAG_TOP_K") or os.getenv("RAG_RETRIEVAL_K")
    if val is not None:
        try:
            parsed = int(str(val).strip())
            if parsed >= 1:
                return parsed
            logger.warning(
                f"Invalid RAG_TOP_K '{val}': must be >= 1. "
                f"Falling back to default: {DEFAULT_RAG_TOP_K}"
            )
        except ValueError:
            logger.warning(
                f"Invalid RAG_TOP_K '{val}': not an integer. "
                f"Falling back to default: {DEFAULT_RAG_TOP_K}"
            )
    return DEFAULT_RAG_TOP_K


def get_rag_min_score() -> float:
    """
    Get the minimum relevance score threshold for RAG retrieval.
    Validates that the value is a float >= 0.0.
    """
    val = os.getenv("RAG_MIN_SCORE")
    if val is not None:
        try:
            parsed = float(str(val).strip())
            if parsed >= 0.0:
                return parsed
            logger.warning(
                f"Invalid RAG_MIN_SCORE '{val}': must be >= 0.0. "
                f"Falling back to default: {DEFAULT_RAG_MIN_SCORE}"
            )
        except ValueError:
            logger.warning(
                f"Invalid RAG_MIN_SCORE '{val}': not a valid float. "
                f"Falling back to default: {DEFAULT_RAG_MIN_SCORE}"
            )
    return DEFAULT_RAG_MIN_SCORE


def is_rag_reranking_enabled() -> bool:
    """
    Check whether optional retrieval reranking is enabled.
    Defaults to False.
    """
    val = os.getenv("RAG_RERANKING_ENABLED")
    if val is not None:
        clean = str(val).strip().lower()
        if clean in ("1", "true", "yes", "on"):
            return True
        if clean in ("0", "false", "no", "off"):
            return False
        logger.warning(
            f"Invalid boolean value for RAG_RERANKING_ENABLED '{val}'. "
            f"Falling back to default: {DEFAULT_RAG_RERANKING_ENABLED}"
        )
    return DEFAULT_RAG_RERANKING_ENABLED


def get_rag_config() -> Dict[str, Any]:
    """
    Return dictionary of current RAG configuration settings.
    """
    return {
        "chunk_size": get_rag_chunk_size(),
        "chunk_overlap": get_rag_chunk_overlap(),
        "top_k": get_rag_top_k(),
        "min_score": get_rag_min_score(),
        "reranking_enabled": is_rag_reranking_enabled(),
    }

