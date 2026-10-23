"""
Backward compatibility layer for sqlite_memory.
Redirects all persistent conversation memory, checkpointer, and thread operations
to PostgreSQL and app.memory.postgres_memory.
"""
from app.memory.postgres_memory import (
    init_db,
    verify_thread_ownership,
    save_message,
    backfill_thread_messages_from_checkpoint,
    save_thread_summary,
    get_thread_summary,
    get_thread_messages,
    retrieve_all_threads,
    thread_exists,
    get_thread_title_db,
    save_thread_title,
    save_youtube_url,
    get_youtube_url,
    serialize_embedding,
    deserialize_embedding,
    save_message_embedding,
    get_message_embeddings,
    get_unembedded_messages,
    checkpointer,
)

__all__ = [
    "init_db",
    "verify_thread_ownership",
    "save_message",
    "backfill_thread_messages_from_checkpoint",
    "save_thread_summary",
    "get_thread_summary",
    "get_thread_messages",
    "retrieve_all_threads",
    "thread_exists",
    "get_thread_title_db",
    "save_thread_title",
    "save_youtube_url",
    "get_youtube_url",
    "serialize_embedding",
    "deserialize_embedding",
    "save_message_embedding",
    "get_message_embeddings",
    "get_unembedded_messages",
    "checkpointer",
]
