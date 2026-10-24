"""Command line helpers:  python -m app.cli init-db | seed-demo | reset-demo"""
from __future__ import annotations

import argparse
import getpass

from . import demo, services
from . import models as m
from .core.auth import hash_password, normalize_username, validate_password
from .config import load_settings
from .database import make_engine, make_session_factory
from .models import Base


def _user_command(db, args) -> None:
    username = normalize_username(args.username)
    if not username:
        raise SystemExit("Use --username with 3-50 characters: letters, digits, dot, underscore or hyphen.")
    existing = db.query(m.User).filter(m.User.username == username).one_or_none()
    if args.command == "create-user" and existing:
        raise SystemExit(f"User '{username}' already exists. Use set-password to change the password.")
    if args.command == "set-password" and not existing:
        raise SystemExit(f"User '{username}' does not exist. Use create-user first.")
    pw = getpass.getpass("Password (not shown): ")
    if pw != getpass.getpass("Repeat password: "):
        raise SystemExit("The passwords do not match. Nothing was changed.")
    problem = validate_password(pw, username)
    if problem:
        raise SystemExit(problem)
    if existing:
        existing.password_hash = hash_password(pw)
        db.query(m.AuthSession).filter(m.AuthSession.user_id == existing.id).delete()   # force re-login everywhere
        print(f"Password updated for '{username}'. Existing sessions were ended.")
    else:
        db.add(m.User(username=username, display_name=args.display_name, password_hash=hash_password(pw)))
        print(f"User '{username}' created. You can now log in at the web app.")
    db.commit()


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    p.add_argument("command", choices=["init-db", "seed-demo", "reset-demo", "create-user", "set-password"])
    p.add_argument("--username", help="for create-user / set-password")
    p.add_argument("--display-name", help="optional, for create-user")
    args = p.parse_args()
    settings = load_settings()
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    factory = make_session_factory(engine)
    with factory() as db:
        services.seed_defaults(db)
        if args.command == "init-db":
            print("Database initialised and demo checklist seeded.")
            return
        if args.command in ("create-user", "set-password"):
            _user_command(db, args)
            return
        if not settings.demo_allowed:
            raise SystemExit("Demo commands are disabled (needs APP_ENV=development and ENABLE_DEMO_ENDPOINTS=true).")
        if args.command == "reset-demo":
            print(f"Removed {demo.reset_demo(db, settings)} demo case(s). User cases were not touched.")
        else:
            ok, msg = services.ocr_status(settings)
            if not ok:
                print(f"WARNING: OCR unavailable ({msg}). Demo documents will be marked failed.")
            for r in demo.seed_demo(db, settings):
                print(f"Scenario {r['scenario']}: {r['case_code']} -> {r['overall_status']} "
                      f"(issues={r['issues']}, needs confirmation={r['needs_confirmation']})")


if __name__ == "__main__":
    main()
