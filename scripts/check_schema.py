#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text


REQUIRED_TABLES = [
    "funds",
    "investors",
    "investor_positions",
    "unit_price_points",
    "fx_accounts",
    "fx_account_snapshots",
    "cashflow_requests",
    "ledger_entries",
    "audit_logs",
]

REQUIRED_COLUMNS = {
    "investors": ["id", "name", "email", "is_active", "username", "password_hash"],
    "investor_positions": ["fund_id", "investor_id", "units"],
    "unit_price_points": ["fund_id", "asof_at", "price"],
    "fx_accounts": ["id", "fund_id", "secret", "is_active"],
    "fx_account_snapshots": ["fx_account_id", "asof_at", "balance", "equity", "profit"],
    "cashflow_requests": [
        "fund_id",
        "investor_id",
        "kind",
        "currency",
        "amount",
        "status",
        "requested_at",
        "confirmed_at",
        "cancelled_at",
    ],
    "ledger_entries": [
        "source_type",
        "source_id",
        "account",
        "amount",
        "unit_price",
    ],
}

OPTIONAL_FUTURE_COLUMNS = {
    "ledger_entries": ["fund_id", "investor_id", "currency"],
}


def load_dotenv_database_url() -> None:
    if os.getenv("DATABASE_URL"):
        return

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key != "DATABASE_URL":
            continue
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ["DATABASE_URL"] = value
        return


def print_result(ok: bool, label: str, detail: str = "") -> None:
    prefix = "OK  " if ok else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"{prefix} {label}{suffix}")


def print_warn(label: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"WARN {label}{suffix}")


def main() -> int:
    load_dotenv_database_url()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print_result(False, "DATABASE_URL", "not set")
        return 1

    schema = os.getenv("DB_SCHEMA", "public")
    engine = create_engine(database_url, pool_pre_ping=True)
    failures = 0
    warnings = 0

    try:
        with engine.connect() as conn:
            print("Required checks")
            table_rows = conn.execute(
                text(
                    """
                    select table_name
                    from information_schema.tables
                    where table_schema = :schema
                      and table_type = 'BASE TABLE'
                    """
                ),
                {"schema": schema},
            ).scalars().all()
            existing_tables = set(table_rows)

            for table in REQUIRED_TABLES:
                ok = table in existing_tables
                print_result(ok, f"table {schema}.{table}")
                if not ok:
                    failures += 1

            checked_tables = sorted(
                set(REQUIRED_COLUMNS.keys()) | set(OPTIONAL_FUTURE_COLUMNS.keys())
            )
            column_rows = conn.execute(
                text(
                    """
                    select table_name, column_name
                    from information_schema.columns
                    where table_schema = :schema
                      and table_name = any(:tables)
                    """
                ),
                {"schema": schema, "tables": checked_tables},
            ).mappings().all()
            existing_columns: dict[str, set[str]] = {}
            for row in column_rows:
                existing_columns.setdefault(row["table_name"], set()).add(row["column_name"])

            for table, columns in REQUIRED_COLUMNS.items():
                table_columns = existing_columns.get(table, set())
                for column in columns:
                    ok = column in table_columns
                    print_result(ok, f"column {schema}.{table}.{column}")
                    if not ok:
                        failures += 1

            print("")
            print("Optional future checks")
            for table, columns in OPTIONAL_FUTURE_COLUMNS.items():
                table_columns = existing_columns.get(table, set())
                for column in columns:
                    ok = column in table_columns
                    if ok:
                        print_result(True, f"column {schema}.{table}.{column}")
                    else:
                        print_warn(
                            f"column {schema}.{table}.{column}",
                            "optional future column missing",
                        )
                        warnings += 1
    except Exception as exc:
        print_result(False, "schema check", type(exc).__name__)
        return 1
    finally:
        engine.dispose()

    if failures:
        print(f"Schema check failed: {failures} missing item(s).")
        return 1

    if warnings:
        print(f"Schema check passed with {warnings} optional warning(s).")
    else:
        print("Schema check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
