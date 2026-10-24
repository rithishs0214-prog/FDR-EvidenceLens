from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import models as m
from .. import services
from ..config import Settings
from ..core.auth import (dummy_hash, hash_token, new_session_token, normalize_username, verify_password)
from ..deps import SESSION_COOKIE, get_current_user, get_db, get_settings_dep
from ..errors import ApiError
from ..schemas import LoginIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])
GENERIC_FAILURE = "Incorrect username or password."


def _client_key(request: Request, username: str) -> str:
    return f"{username}|{request.client.host if request.client else 'unknown'}"


@router.post("/login", response_model=UserOut, summary="Log in (sets an HttpOnly session cookie)")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db),
          settings: Settings = Depends(get_settings_dep)):
    limiter = request.app.state.login_limiter
    username = normalize_username(body.username) or ""
    key = _client_key(request, username)
    if limiter.is_locked(key):
        raise ApiError(429, "too_many_attempts",
                       f"Too many failed attempts. Try again in about {max(1, limiter.retry_after(key) // 60)} minute(s).")

    user = db.scalar(select(m.User).where(m.User.username == username)) if username else None
    # Always run one hash verification so timing does not reveal whether the username exists.
    password_ok = verify_password(body.password, user.password_hash if user else dummy_hash())
    if not (user and user.is_active and password_ok):
        limiter.record_failure(key)
        services.audit(db, None, "login_failed", {"reason": "bad_credentials"}, actor="anonymous", case_code="-")
        db.commit()   # the typed username/password are deliberately not stored anywhere
        raise ApiError(401, "invalid_credentials", GENERIC_FAILURE)

    limiter.reset(key)
    now = datetime.now(timezone.utc)
    db.execute(delete(m.AuthSession).where(m.AuthSession.expires_at <= now))   # tidy expired sessions
    token = new_session_token()
    db.add(m.AuthSession(token_hash=hash_token(token), user_id=user.id,
                         expires_at=now + timedelta(hours=settings.session_hours)))
    user.last_login_at = now
    services.audit(db, None, "login_success", {}, actor=user.username, case_code="-")
    db.commit()
    response.set_cookie(SESSION_COOKIE, token, max_age=settings.session_hours * 3600, httponly=True,
                        samesite="lax", secure=settings.app_env != "development", path="/")
    return UserOut(username=user.username, display_name=user.display_name)


@router.post("/logout", status_code=204, summary="Log out (idempotent)")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        sess = db.scalar(select(m.AuthSession).where(m.AuthSession.token_hash == hash_token(token)))
        if sess is not None:
            user = db.get(m.User, sess.user_id)
            db.delete(sess)
            services.audit(db, None, "logout", {}, actor=user.username if user else "unknown", case_code="-")
            db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=UserOut, summary="Current logged-in user (401 if not logged in)")
def me(user: m.User = Depends(get_current_user)):
    return UserOut(username=user.username, display_name=user.display_name)
