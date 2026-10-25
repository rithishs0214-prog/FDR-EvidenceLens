"""FastAPI application factory.  Run:  uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import services
from .config import Settings, load_settings
from .core.auth import LoginLimiter
from .deps import require_auth
from .database import make_engine, make_session_factory
from .errors import ApiError
from .models import Base
from .routers import admin, auth, cases, documents

log = logging.getLogger("evidencelens")

DESCRIPTION = ("Explainable FDR document review assistant (decision support). Local demo with a basic "
               "username/password login (no roles, no MFA), not production-ready, not an official AICTE system. It never authenticates an FDR "
               "with a bank and never approves or rejects a refund.")


def _err(status: int, code: str, message: str, details=None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details}})


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or load_settings()
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    with session_factory() as db:
        services.seed_defaults(db)

    app = FastAPI(title="FDR EvidenceLens API", version="0.2.0", description=DESCRIPTION,
                  dependencies=[Depends(require_auth)])
    app.state.settings, app.state.engine, app.state.session_factory = settings, engine, session_factory
    app.state.login_limiter = LoginLimiter()

    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return _err(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        return _err(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e.get("loc", [])[1:]), "message": e.get("msg", "Invalid value")}
                   for e in exc.errors()]
        return _err(422, "validation_error", "Some input is invalid. " + "; ".join(
            f"{d['field']}: {d['message']}" if d["field"] else d["message"] for d in details), details)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.error("Unhandled error: %s", type(exc).__name__)   # no stack trace or data to the client
        resp = _err(500, "internal_error", "Something went wrong. Please try again.")
        origin = request.headers.get("origin")
        if origin and origin in settings.cors_origins:   # this response bypasses CORSMiddleware
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Vary"] = "Origin"
        return resp

    for r in (auth.router, admin.router, cases.router, documents.router):
        app.include_router(r)
    return app
app = create_app()
