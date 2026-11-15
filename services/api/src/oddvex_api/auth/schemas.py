from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?\.[A-Za-z]{2,24}$")


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 320 or not _EMAIL_RE.match(email) or ".." in email:
        raise ValueError("must be a valid email address")
    return email


class RegisterRequest(BaseModel):
    email: str = Field(max_length=320, json_schema_extra={"format": "email"})
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    age_confirmed: bool = Field(
        description="Attestation that the user is 21 or older. Must be true."
    )

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("display_name")
    @classmethod
    def _display_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display name cannot be blank")
        return cleaned

    @field_validator("age_confirmed")
    @classmethod
    def _must_confirm_age(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("you must confirm that you are 21 or older to register")
        return value


class LoginRequest(BaseModel):
    email: str = Field(max_length=320, json_schema_extra={"format": "email"})
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str
    role: Literal["user", "admin"]
    age_confirmed_at: datetime
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds")
    user: UserOut
