from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .config import Settings
from .core.auth import hash_token
from .errors import ApiError

SESSION_COOKIE = "evidencelens_session"
# Deny-by-default: every route needs a login except these.
PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/api/auth/logout"}


def get_db(request: Request):
    with request.app.state.session_factory() as db:
        yield db


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_current_user(request: Request, db: Session = Depends(get_db)) -> m.User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise ApiError(401, "not_authenticated", "Please log in to continue.")
    sess = db.scalar(select(m.AuthSession).where(m.AuthSession.token_hash == hash_token(token)))
    if sess is None or sess.expires_at <= datetime.now(timezone.utc):
        raise ApiError(401, "session_expired", "Your session has expired. Please log in again.")
    user = db.get(m.User, sess.user_id)
    if user is None or not user.is_active:
        raise ApiError(401, "not_authenticated", "Please log in to continue.")
    return user


def require_auth(request: Request, db: Session = Depends(get_db)):
    """App-wide dependency: protects every route (including ones added later) except PUBLIC_PATHS."""
    if request.url.path in PUBLIC_PATHS:
        return None
    return get_current_user(request, db)
