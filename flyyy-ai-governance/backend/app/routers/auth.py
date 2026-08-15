"""Auth API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas import LoginRequest, Token
from app.security import authenticate, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest):
    if not authenticate(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return Token(access_token=create_access_token(payload.username))
