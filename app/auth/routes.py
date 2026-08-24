from datetime import datetime, timedelta, timezone
import secrets
import hashlib

from fastapi import APIRouter, HTTPException, status,Depends

import sqlite3
from app.auth.security import hash_password, verify_password
import os
from app.auth.jwt_utils import create_access_token
from app.auth.dependencies import get_current_user
from app.schemas.auth_schema import (SignupRequest,LoginRequest,
                               TokenResponse,ForgotPasswordRequest
                               ,ResetPasswordRequest)
from app.auth.email_service import (send_reset_email,
                                    send_verification_email)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


DB_DIR = "database"
DB_PATH = os.path.join(DB_DIR, "chatbot_conv.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)



# ============================================================
# SIGNUP
# ============================================================

@router.post("/signup")
async def signup(data: SignupRequest):

    email = data.email.strip().lower()

    cursor = conn.cursor()

    # Check existing user
    cursor.execute(
        """
        SELECT user_id
        FROM users
        WHERE email = ?
        """,
        (email,)
    )

    existing_user = cursor.fetchone()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered"
        )

    # Hash password
    password_hash = hash_password(data.password)

    # Create unverified user
    cursor.execute(
        """
        INSERT INTO users (
            email,
            password_hash,
            is_verified
        )
        VALUES (?, ?, ?)
        """,
        (
            email,
            password_hash,
            0
        )
    )

    user_id = cursor.lastrowid

    # Generate verification token
    token = secrets.token_urlsafe(32)

    # Store only token hash
    token_hash = hashlib.sha256(
        token.encode()
    ).hexdigest()

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=15)
    )

    # Store verification token
    cursor.execute(
        """
        INSERT INTO email_verifications (
            user_id,
            token_hash,
            expires_at
        )
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            token_hash,
            expires_at.isoformat()
        )
    )

    conn.commit()

    # Send actual token by email
    await send_verification_email(
        email,
        token
    )

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
def login(data: LoginRequest):

    email = data.email.strip().lower()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            user_id,
            email,
            password_hash,
            is_verified
        FROM users
        WHERE email = ?
        """,
        (email,)
    )

    user = cursor.fetchone()

    # Don't reveal whether email exists
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    user_id = user[0]
    password_hash = user[2]
    is_verified = bool(user[3])

    if not is_verified:
      raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Please verify your email before logging in"
    )

    # Verify password
    if not verify_password(
        data.password,
        password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    # For now, signup marks the account verified.
    # If you add email verification later,
    # this check can be enabled.
    #
    # if not is_verified:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Please verify your email first"
    #     )

    # Create JWT
    access_token = create_access_token(user_id)

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# ============================================================
# CURRENT USER
# ============================================================

@router.get("/me")
def get_me(
    current_user: dict = Depends(get_current_user)
):
    return {
        "user_id": current_user["user_id"],
        "email": current_user["email"],
        "is_verified": current_user["is_verified"],
        "created_at": current_user["created_at"]
    }


# ============================================================
# FORGOT PASSWORD
# ============================================================

@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest
):

    email = data.email.strip().lower()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT user_id, email
        FROM users
        WHERE email = ?
        """,
        (email,)
    )

    user = cursor.fetchone()

    # Don't reveal whether email exists
    if user is None:
        return {
            "message": (
                "If the email exists, "
                "a password reset link has been sent."
            )
        }

    user_id = user[0]

    # Generate token
    token = secrets.token_urlsafe(32)

    token_hash = hashlib.sha256(
        token.encode()
    ).hexdigest()

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=15)
    )

    # Delete old reset tokens
    cursor.execute(
        """
        DELETE FROM password_resets
        WHERE user_id = ?
        """,
        (user_id,)
    )

    # Store new token
    cursor.execute(
        """
        INSERT INTO password_resets (
            user_id,
            token_hash,
            expires_at
        )
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            token_hash,
            expires_at.isoformat()
        )
    )

    conn.commit()

    # Send reset email
    await send_reset_email(
        email,
        token
    )

    return {
        "message": (
            "If the email exists, "
            "a password reset link has been sent."
        )
    }

    # TO DO:
    # Send `token` to user's email.
    #
    # Example:
    #
    # reset_link = f"http://localhost:8501/reset-password?token={token}"
    #
    # await send_reset_email(
    #     email,
    #     reset_link
    # )

   # return {
   #     "message": "If the email exists, a password reset link has been sent."
   # }


# ============================================================
# RESET PASSWORD
# ============================================================

@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest
):

    token_hash = hashlib.sha256(
        data.token.encode()
    ).hexdigest()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            user_id,
            expires_at
        FROM password_resets
        WHERE token_hash = ?
        """,
        (token_hash,)
    )

    reset_record = cursor.fetchone()

    if reset_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    reset_id = reset_record[0]
    user_id = reset_record[1]
    expires_at = datetime.fromisoformat(
        reset_record[2]
    )

    # Check expiration
    if expires_at < datetime.now(timezone.utc):

        cursor.execute(
            """
            DELETE FROM password_resets
            WHERE id = ?
            """,
            (reset_id,)
        )

        conn.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired"
        )

    # Hash new password
    new_password_hash = hash_password(
        data.new_password
    )

    # Update password
    cursor.execute(
        """
        UPDATE users
        SET password_hash = ?
        WHERE user_id = ?
        """,
        (
            new_password_hash,
            user_id
        )
    )

    # Delete token so it cannot be reused
    cursor.execute(
        """
        DELETE FROM password_resets
        WHERE id = ?
        """,
        (reset_id,)
    )

    conn.commit()

    return {
        "message": "Password reset successfully"
    }




@router.get("/verify-email")
def verify_email(
    token: str
):

    token_hash = hashlib.sha256(
        token.encode()
    ).hexdigest()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            id,
            user_id,
            expires_at
        FROM email_verifications
        WHERE token_hash = ?
        """,
        (token_hash,)
    )

    record = cursor.fetchone()

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )

    verification_id = record[0]
    user_id = record[1]
    expires_at = datetime.fromisoformat(record[2])

    # Check expiration
    if expires_at < datetime.now(timezone.utc):

        cursor.execute(
            """
            DELETE FROM email_verifications
            WHERE id = ?
            """,
            (verification_id,)
        )

        conn.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token has expired"
        )

    # Verify user
    cursor.execute(
        """
        UPDATE users
        SET is_verified = 1
        WHERE user_id = ?
        """,
        (user_id,)
    )

    # Delete used token
    cursor.execute(
        """
        DELETE FROM email_verifications
        WHERE id = ?
        """,
        (verification_id,)
    )

    conn.commit()

    return {
        "message": "Email verified successfully. You can now log in."
    }