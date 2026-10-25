"""Settings logic for deployments (needs python-dotenv, i.e. the normal requirements)."""
import os
import pytest
from app.config import load_settings

KEYS = ["APP_ENV", "COOKIE_SECURE", "COOKIE_SAMESITE", "ALLOW_DEMO_IN_PRODUCTION", "ENABLE_DEMO_ENDPOINTS"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)


def test_development_defaults():
    s = load_settings()
    assert s.secure_cookies is False and s.demo_allowed is True and s.cookie_samesite == "lax"


def test_production_defaults_are_locked_down(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    s = load_settings()
    assert s.secure_cookies is True and s.demo_allowed is False


def test_demo_can_be_enabled_on_a_deployed_demo_but_still_switched_off(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production"); monkeypatch.setenv("ALLOW_DEMO_IN_PRODUCTION", "true")
    assert load_settings().demo_allowed is True
    monkeypatch.setenv("ENABLE_DEMO_ENDPOINTS", "false")
    assert load_settings().demo_allowed is False


def test_samesite_none_forces_secure(monkeypatch):
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    s = load_settings()
    assert s.cookie_samesite == "none" and s.secure_cookies is True
    monkeypatch.setenv("COOKIE_SAMESITE", "garbage")
    assert load_settings().cookie_samesite == "lax"
