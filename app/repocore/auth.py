"""
RepoCore Authentication Module — Unified with NexusAI auth system & PostgreSQL User model.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.auth.security import hash_password as password_hash, verify_password
from app.auth.jwt_utils import create_access_token, decode_access_token
from app.db.models import User, RefreshToken, utc_now
from .database import get_db
from .config import settings

security = HTTPBearer(auto_error=False)


def hash_token(token: str) -> str:
    """Hash a token using SHA-256 for secure storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_refresh_token(db: AsyncSession, user_id: int) -> str:
    """Generate and persist a secure random refresh token."""
    raw_token = secrets.token_urlsafe(48)
    token_h = hash_token(raw_token)
    expires_at = utc_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    refresh_obj = RefreshToken(
        user_id=user_id,
        token_hash=token_h,
        expires_at=expires_at,
        revoked=False,
    )
    db.add(refresh_obj)
    await db.flush()
    return raw_token


async def get_valid_refresh_token(db: AsyncSession, raw_token: str) -> Optional[RefreshToken]:
    """Retrieve and validate a refresh token."""
    token_h = hash_token(raw_token)
    stmt = select(RefreshToken).where(
        RefreshToken.token_hash == token_h,
        RefreshToken.revoked == False,
        RefreshToken.expires_at > utc_now(),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    FastAPI dependency to authenticate requests using JWT access tokens.
    Returns the unified User instance from PostgreSQL.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise credentials_exception

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            raise credentials_exception
        user_id = int(user_id_raw)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user

