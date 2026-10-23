from datetime import datetime, timedelta, timezone
import secrets
import hashlib
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session

from app.auth.security import hash_password, verify_password
from app.auth.jwt_utils import create_access_token
from app.auth.dependencies import get_current_user
from app.schemas.auth_schema import (
    SignupRequest,
    LoginRequest,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.auth.email_service import (
    send_reset_email,
    send_verification_email,
)
from app.db.session import get_db
from app.db.models import User, PasswordReset, EmailVerification, utc_now

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# ============================================================
# SIGNUP
# ============================================================

@router.post("/signup")
async def signup(data: SignupRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()

    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered",
        )

    # Hash password
    pwd_hash = hash_password(data.password)

    # Base username on email prefix
    username_candidate = email.split("@")[0]
    existing_username = db.query(User).filter(User.username == username_candidate).first()
    username = username_candidate if not existing_username else f"{username_candidate}_{secrets.token_hex(2)}"

    # Create unverified user
    user = User(
        email=email,
        username=username,
        password_hash=pwd_hash,
        is_verified=False,
        created_at=utc_now(),
    )
    db.add(user)
    db.flush()

    # Generate verification token
    token = secrets.token_urlsafe(32)
    token_h = hashlib.sha256(token.encode()).hexdigest()
    expires_at = utc_now() + timedelta(minutes=15)

    ev = EmailVerification(
        user_id=user.id,
        token_hash=token_h,
        expires_at=expires_at,
        created_at=utc_now(),
    )
    db.add(ev)
    db.commit()

    # Send verification token by email
    await send_verification_email(email, token)

    return {
        "message": (
            "Account created successfully. "
            "Please check your email to verify your account."
        )
    }


# ============================================================
# LOGIN
# ============================================================

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()

    user = db.query(User).filter(User.email == email).first()

    # Don't reveal whether email exists
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in",
        )

    # Verify password
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create JWT
    access_token = create_access_token(user.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


# ============================================================
# CURRENT USER
# ============================================================

@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "username": current_user.get("username"),
        "is_verified": current_user["is_verified"],
        "created_at": current_user["created_at"],
    }


# ============================================================
# FORGOT PASSWORD
# ============================================================

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = data.email.strip().lower()

    user = db.query(User).filter(User.email == email).first()

    # Don't reveal whether email exists
    if user is None:
        return {
            "message": (
                "If the email exists, "
                "a password reset link has been sent."
            )
        }

    # Generate token
    token = secrets.token_urlsafe(32)
    token_h = hashlib.sha256(token.encode()).hexdigest()
    expires_at = utc_now() + timedelta(minutes=15)

    # Delete old reset tokens
    db.query(PasswordReset).filter(PasswordReset.user_id == user.id).delete()

    reset_rec = PasswordReset(
        user_id=user.id,
        token_hash=token_h,
        expires_at=expires_at,
        created_at=utc_now(),
    )
    db.add(reset_rec)
    db.commit()

    # Send reset email
    await send_reset_email(email, token)

    return {
        "message": (
            "If the email exists, "
            "a password reset link has been sent."
        )
    }


# ============================================================
# RESET PASSWORD
# ============================================================

@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_h = hashlib.sha256(data.token.encode()).hexdigest()

    reset_record = db.query(PasswordReset).filter(PasswordReset.token_hash == token_h).first()

    if reset_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Check expiration
    if reset_record.expires_at < utc_now():
        db.delete(reset_record)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired",
        )

    # Hash new password
    new_password_hash = hash_password(data.new_password)

    # Update password
    user = db.query(User).filter(User.id == reset_record.user_id).first()
    if user:
        user.password_hash = new_password_hash

    # Delete token so it cannot be reused
    db.delete(reset_record)
    db.commit()

    return {
        "message": "Password reset successfully",
    }


# ============================================================
# VERIFY EMAIL
# ============================================================

@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    token_h = hashlib.sha256(token.encode()).hexdigest()

    record = db.query(EmailVerification).filter(EmailVerification.token_hash == token_h).first()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    # Check expiration
    if record.expires_at < utc_now():
        db.delete(record)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired",
        )

    # Verify user
    user = db.query(User).filter(User.id == record.user_id).first()
    if user:
        user.is_verified = True

    # Delete used token
    db.delete(record)
    db.commit()

    return {
        "message": "Email verified successfully. You can now log in.",
    }
