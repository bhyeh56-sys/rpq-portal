#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

cd "$REPO_ROOT"

echo "Predeploy check starting."

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . ".env"
  set +a
  echo "Loaded .env."
else
  echo "No .env file found; using current environment."
fi

echo "Step 1/2: schema check starting."
if .venv/bin/python scripts/check_schema.py; then
  echo "Step 1/2: schema check passed."
else
  echo "Step 1/2: schema check failed."
  exit 1
fi

echo "Step 2/2: production smoke test starting."
if scripts/smoke_prod.sh; then
  echo "Step 2/2: production smoke test passed."
else
  echo "Step 2/2: production smoke test failed."
  exit 1
fi

echo "Predeploy check passed."
