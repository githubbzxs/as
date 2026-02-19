from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.settings import Settings, get_settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class AuthError(Exception):
    """鉴权异常。"""


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    settings: Settings,
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.app_token_expire_minutes))
    payload = {"sub": subject, "exp": expire, "iat": now}
    return jwt.encode(payload, settings.app_jwt_secret, algorithm="HS256")


def decode_access_token(settings: Settings, token: str) -> str:
    try:
        payload = jwt.decode(token, settings.app_jwt_secret, algorithms=["HS256"])
        subject = payload.get("sub")
        if not subject:
            raise AuthError("令牌缺少用户信息")
        return str(subject)
    except JWTError as exc:
        raise AuthError("令牌无效或已过期") from exc


def get_current_user(
    token: str = Depends(oauth2_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    try:
        username = decode_access_token(settings, token)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return username

