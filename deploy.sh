#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOCAL_APP_URL="${LOCAL_APP_URL:-http://127.0.0.1:8000}"
LOCAL_APP_URL="${LOCAL_APP_URL%/}"
HOST_HEADER="${HOST_HEADER:-rpqtfund.com}"

failures=0

check_status() {
  local label="$1"
  local expected="$2"
  shift 2

  local code
  code="$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 20 "$@")"
  local curl_status=$?

  if [[ $curl_status -eq 0 && "$code" == "$expected" ]]; then
    printf 'OK   %s -> %s\n' "$label" "$code"
  else
    printf 'FAIL %s -> %s (expected %s, curl exit %s)\n' "$label" "$code" "$expected" "$curl_status"
    failures=$((failures + 1))
  fi
}

check_body() {
  local label="$1"
  local expected="$2"
  shift 2

  local body_file
  body_file="$(mktemp)"

  local code
  code="$(curl -sS -o "$body_file" -w "%{http_code}" --connect-timeout 10 --max-time 20 "$@")"
  local curl_status=$?

  if [[ $curl_status -eq 0 && "$code" == "200" ]] && grep -qi "$expected" "$body_file"; then
    printf 'OK   %s contains "%s"\n' "$label" "$expected"
  else
    printf 'FAIL %s content check for "%s" (status %s, curl exit %s)\n' "$label" "$expected" "$code" "$curl_status"
    failures=$((failures + 1))
  fi

  rm -f "$body_file"
}

printf 'Deploy local checks: %s (Host: %s)\n' "$LOCAL_APP_URL" "$HOST_HEADER"

check_status "/" "200" -H "Host: ${HOST_HEADER}" "${LOCAL_APP_URL}/"
check_status "/portal/login" "200" -H "Host: ${HOST_HEADER}" "${LOCAL_APP_URL}/portal/login"
check_body "/admin/investors" "Create Investor" -H "Host: ${HOST_HEADER}" -H "X-Admin-User: admin" "${LOCAL_APP_URL}/admin/investors"
check_body "/admin/unit-price" "Unit Price" -H "Host: ${HOST_HEADER}" -H "X-Admin-User: admin" "${LOCAL_APP_URL}/admin/unit-price"
check_body "/admin/cashflows" "Cashflows" -H "Host: ${HOST_HEADER}" -H "X-Admin-User: admin" "${LOCAL_APP_URL}/admin/cashflows"

if [[ $failures -gt 0 ]]; then
  printf 'Deploy local checks failed: %d check(s) failed.\n' "$failures"
  exit 1
fi

bash scripts/smoke_prod.sh

printf 'Deploy checks passed.\n'
