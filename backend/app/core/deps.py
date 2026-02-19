from __future__ import annotations

from fastapi import Depends, Request

from app.core.auth import get_current_user
from app.core.container import AppContainer


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def require_user(_: str = Depends(get_current_user)) -> str:
    return _
