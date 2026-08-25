import re
import uuid

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)

    email: EmailStr

    password: str = Field(min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
            raise ValueError(
                "Password must contain at least one letter and one digit."
            )
        return v


class LoginRequest(BaseModel):
    email: EmailStr

    password: str


def _validate_new_password(v: str) -> str:
    if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError(
            "Password must contain at least one letter and one digit."
        )
    return v


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=128)

    new_password: str = Field(min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_new_password(v)


class ChangePasswordRequest(BaseModel):
    current_password: str

    new_password: str = Field(min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _validate_new_password(v)


class MessageResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: EmailStr
    role: UserRole

    model_config = {
        "from_attributes": True,
    }


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse