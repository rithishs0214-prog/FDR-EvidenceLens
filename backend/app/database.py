from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .core.dburl import normalize_database_url


def make_engine(url: str) -> Engine:
    url = normalize_database_url(url)
    is_sqlite = url.startswith("sqlite")
    if is_sqlite and ":memory:" not in url:
        path = url.replace("sqlite:///", "", 1)
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    if is_sqlite:
        engine = create_engine(url, connect_args={"check_same_thread": False})
    else:  # hosted Postgres: drop dead connections instead of failing the next request
        engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def _pragmas(dbapi_conn, _):  # enforce foreign keys (off by default in SQLite)
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
