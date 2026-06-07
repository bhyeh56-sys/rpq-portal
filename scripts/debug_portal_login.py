from __future__ import annotations

import os
import sys
from pathlib import Path

from passlib.hash import argon2
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import DATABASE_URL, SessionLocal  # noqa: E402
from app.portal import _is_explicitly_inactive  # noqa: E402


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python scripts/debug_portal_login.py <username> <password>")
        return 2

    username = (sys.argv[1] or "").strip()
    password = sys.argv[2] or ""

    print(f"DATABASE_URL set: {bool(os.getenv('DATABASE_URL'))}")
    print(f"DATABASE_URL driver: {DATABASE_URL.split(':', 1)[0] if DATABASE_URL else '<empty>'}")

    if not username:
        print("row_found: False")
        print("final_result: FAIL")
        print("failure_reason: empty username after strip")
        return 1
    if not password:
        print("row_found: False")
        print("final_result: FAIL")
        print("failure_reason: empty password")
        return 1

    with SessionLocal() as db:
        row = db.execute(
            text(
                """
                SELECT id, username, password_hash, is_active
                FROM investors
                WHERE username = :u
                LIMIT 1
                """
            ),
            {"u": username},
        ).mappings().first()

    print(f"row_found: {bool(row)}")
    if not row:
        print("final_result: FAIL")
        print("failure_reason: investor row not found by username")
        return 1

    password_hash = (row.get("password_hash") or "").strip()
    is_active = row.get("is_active")
    inactive = _is_explicitly_inactive(is_active)

    print(f"id: {row.get('id')}")
    print(f"username: {row.get('username')}")
    print(f"is_active_raw: {is_active!r}")
    print(f"is_active_type: {type(is_active).__name__}")
    print(f"password_hash_prefix: {password_hash[:32]}")
    print(f"password_hash_length: {len(password_hash)}")

    try:
        password_ok = bool(password_hash) and argon2.verify(password, password_hash)
    except Exception as exc:
        password_ok = False
        print(f"argon2_verify_exception: {type(exc).__name__}")

    print(f"argon2_verify_result: {password_ok}")
    print(f"app_active_result: {not inactive}")

    if inactive:
        print("final_result: FAIL")
        print("failure_reason: app logic treats investor as explicitly inactive")
        return 1
    if not password_ok:
        print("final_result: FAIL")
        print("failure_reason: argon2.verify returned false")
        return 1

    print("final_result: SUCCESS")
    print("session_key_on_success: investor_id")
    print("redirect_on_success: /portal/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
