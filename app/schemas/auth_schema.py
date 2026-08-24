
from pydantic import BaseModel,EmailStr,Field

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=70
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(
        min_length=8,
        max_length=70
    )