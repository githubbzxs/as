from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import create_access_token, verify_password
from app.core.settings import Settings, get_settings
from app.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, settings: Settings = Depends(get_settings)) -> TokenResponse:
    if payload.username != settings.app_admin_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not verify_password(payload.password, settings.app_admin_password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    token = create_access_token(settings, subject=payload.username)
    return TokenResponse(access_token=token)
