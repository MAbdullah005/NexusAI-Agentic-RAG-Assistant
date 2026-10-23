from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from app.auth.jwt_utils import decode_access_token
from app.db.session import SessionLocal
from app.db.models import User

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Validate JWT access token and return
    the authenticated user from PostgreSQL.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            raise credentials_exception
        user_id = int(user_id_raw)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    try:
        with SessionLocal() as session:
            user = session.query(User).filter(User.id == user_id).first()
            if user is None:
                raise credentials_exception

            return {
                "user_id": user.id,
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "password_hash": user.password_hash,
                "is_verified": bool(user.is_verified),
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
    except HTTPException:
        raise
    except Exception:
        raise credentials_exception
