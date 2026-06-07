from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import DATABASE_URL, SessionLocal  # noqa: E402
from app.portal import evaluate_investor_login, load_investor_login_row  # noqa: E402


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
        row = load_investor_login_row(db, username)

    print(f"row_found: {bool(row)}")
    decision = evaluate_investor_login(row, password)

    print(f"id: {decision['id']}")
    print(f"username: {decision['username']}")
    print(f"is_active_raw: {decision['is_active_raw']!r}")
    print(f"is_active_type: {decision['is_active_type']}")
    print(f"password_hash_prefix: {decision['password_hash_prefix']}")
    print(f"password_hash_length: {decision['password_hash_length']}")
    print(f"argon2_verify_result: {decision['verify_result']}")
    if decision["verify_exception"]:
        print(f"argon2_verify_exception: {decision['verify_exception']}")
    print(f"app_active_result: {decision['active_result']}")

    if not decision["success"]:
        print("final_result: FAIL")
        print(f"failure_reason: {decision['reason']}")
        return 1

    print("final_result: SUCCESS")
    print("session_key_on_success: investor_id")
    print("redirect_on_success: /portal/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
