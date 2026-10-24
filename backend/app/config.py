"""Application settings read from environment variables (see .env.example)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'evidencelens.db').as_posix()}"
    upload_dir: Path = BACKEND_DIR / "data" / "uploads"
    max_upload_mb: int = 10
    max_pdf_pages: int = 10
    cors_origins: tuple = ("http://localhost:5173", "http://127.0.0.1:5173")
    tesseract_cmd: str = ""
    ocr_lang: str = "eng"
    ocr_confidence_threshold: float = 80.0
    approaching_maturity_days: int = 30
    enable_demo_endpoints: bool = True
    session_hours: int = 8

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def demo_allowed(self) -> bool:
        """Demo seeding/reset is development-only and can be switched off explicitly."""
        return self.app_env == "development" and self.enable_demo_endpoints


def load_settings() -> Settings:
    d = Settings()
    return Settings(
        app_env=os.getenv("APP_ENV", d.app_env),
        database_url=os.getenv("DATABASE_URL", d.database_url),
        upload_dir=Path(os.getenv("UPLOAD_DIR", str(d.upload_dir))),
        max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", d.max_upload_mb)),
        max_pdf_pages=int(os.getenv("MAX_PDF_PAGES", d.max_pdf_pages)),
        cors_origins=tuple(o.strip() for o in os.getenv("CORS_ORIGINS", ",".join(d.cors_origins)).split(",") if o.strip()),
        tesseract_cmd=os.getenv("TESSERACT_CMD", ""),
        ocr_lang=os.getenv("OCR_LANG", d.ocr_lang),
        ocr_confidence_threshold=float(os.getenv("OCR_CONFIDENCE_THRESHOLD", d.ocr_confidence_threshold)),
        approaching_maturity_days=int(os.getenv("APPROACHING_MATURITY_DAYS", d.approaching_maturity_days)),
        enable_demo_endpoints=_bool("ENABLE_DEMO_ENDPOINTS", d.enable_demo_endpoints),
        session_hours=int(os.getenv("SESSION_HOURS", d.session_hours)),
    )
