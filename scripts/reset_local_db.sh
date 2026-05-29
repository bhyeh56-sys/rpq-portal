#!/usr/bin/env bash
set -euo pipefail

APP_DB_URL="${DATABASE_URL:-}"
PSQL_DB_URL="${PSQL_DATABASE_URL:-}"
ADMIN_DB_URL="${RPQ_ADMIN_DATABASE_URL:-}"

if [[ -z "$PSQL_DB_URL" ]]; then
  echo "PSQL_DATABASE_URL is required, for example:"
  echo "  export PSQL_DATABASE_URL='postgresql://rpq_user:<password>@127.0.0.1:5432/rpq_db'"
  exit 1
fi

python3 - "$PSQL_DB_URL" <<'PY'
import sys
from urllib.parse import urlparse

url = urlparse(sys.argv[1])
if url.scheme not in {"postgresql", "postgres"}:
    raise SystemExit("PSQL_DATABASE_URL must use postgresql://")
if url.hostname not in {"127.0.0.1", "localhost"}:
    raise SystemExit("Refusing to reset a non-local database host")
if url.path.lstrip("/") != "rpq_db":
    raise SystemExit("Refusing to reset any database other than rpq_db")
PY

if [[ -n "$APP_DB_URL" ]]; then
  python3 - "$APP_DB_URL" <<'PY'
import sys
from urllib.parse import urlparse

url = urlparse(sys.argv[1])
if url.scheme != "postgresql+psycopg":
    raise SystemExit("DATABASE_URL must use postgresql+psycopg://")
if url.hostname not in {"127.0.0.1", "localhost"}:
    raise SystemExit("Refusing to use a non-local app database host")
if url.path.lstrip("/") != "rpq_db":
    raise SystemExit("Refusing to use any app database other than rpq_db")
PY
fi

echo "Resetting local rpq_db"

if [[ -n "$ADMIN_DB_URL" ]]; then
  psql "$ADMIN_DB_URL" -v ON_ERROR_STOP=1 \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'rpq_db' AND pid <> pg_backend_pid();" \
    -c "DROP DATABASE IF EXISTS rpq_db;" \
    -c "CREATE DATABASE rpq_db OWNER rpq_user;"
else
  dropdb --if-exists rpq_db
  createdb -O rpq_user rpq_db
fi

psql "$PSQL_DB_URL" -v ON_ERROR_STOP=1 -f schema.sql
psql "$PSQL_DB_URL" -v ON_ERROR_STOP=1 -f scripts/seed.sql

echo "Local rpq_db reset complete"
