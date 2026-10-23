from __future__ import annotations
"""
RepoCore Models — Unified with app.db.models.
Avoids duplicate DeclarativeBase or model definitions.
"""
from app.db.models import (
    Base,
    User,
    Repository,
    Conversation,
    RepoMessage as Message,
    RepoMessage,
    MessageSource,
    UserRepository,
    RefreshToken,
    Chunk,
    Thread,
    Document,
    ThreadDocument,
    ThreadContext,
    Message as ChatMessage,
    MessageEmbedding,
    utc_now,
)

__all__ = [
    "Base",
    "User",
    "Repository",
    "Conversation",
    "Message",
    "RepoMessage",
    "ChatMessage",
    "MessageSource",
    "UserRepository",
    "RefreshToken",
    "Chunk",
    "Thread",
    "Document",
    "ThreadDocument",
    "ThreadContext",
    "MessageEmbedding",
    "utc_now",
]
