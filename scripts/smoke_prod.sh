#!/usr/bin/env bash
set -u

# Usage:
#   scripts/smoke_prod.sh
#   BASE_URL=https://staging.example.com scripts/smoke_prod.sh
#   ADMIN_USER=admin ADMIN_PASS='secret' scripts/smoke_prod.sh
#
# App-direct checks behind nginx can be run separately with:
#   curl -H "Host: rpqtfund.com" -H "X-Admin-User: admin" http://127.0.0.1:8001/admin/investors
#   curl -H "Host: rpqtfund.com" -H "X-Admin-User: admin" http://127.0.0.1:8001/admin/unit-price
#   curl -H "Host: rpqtfund.com" -H "X-Admin-User: admin" http://127.0.0.1:8001/admin/cashflows

BASE_URL="${BASE_URL:-https://rpqtfund.com}"
BASE_URL="${BASE_URL%/}"

PUBLIC_PATHS=(
  "/"
  "/portal/login"
)

ADMIN_PATHS=(
  "/admin/investors"
  "/admin/cashflows"
  "/admin/unit-price"
)

failures=0

has_admin_auth=false
if [[ -n "${ADMIN_USER:-}" && -n "${ADMIN_PASS:-}" ]]; then
  has_admin_auth=true
fi

check_path() {
  local path="$1"
  local expected="$2"
  shift 2

  local code
  code=$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 20 "$@" "${BASE_URL}${path}")
  local curl_status=$?

  if [[ $curl_status -eq 0 && "$code" == "$expected" ]]; then
    printf 'OK   %s -> %s\n' "$path" "$code"
  else
    printf 'FAIL %s -> %s (expected %s, curl exit %s)\n' "$path" "$code" "$expected" "$curl_status"
    failures=$((failures + 1))
  fi
}

check_body_contains() {
  local path="$1"
  local expected="$2"
  shift 2

  local body_file
  body_file="$(mktemp)"

  local code
  code=$(curl -sS -o "$body_file" -w "%{http_code}" --connect-timeout 10 --max-time 20 "$@" "${BASE_URL}${path}")
  local curl_status=$?

  if [[ $curl_status -eq 0 && "$code" == "200" ]] && grep -qi "$expected" "$body_file"; then
    printf 'OK   %s contains "%s"\n' "$path" "$expected"
  else
    printf 'FAIL %s content check for "%s" (status %s, curl exit %s)\n' "$path" "$expected" "$code" "$curl_status"
    failures=$((failures + 1))
  fi

  rm -f "$body_file"
}

printf 'Smoke target: %s\n' "$BASE_URL"

for path in "${PUBLIC_PATHS[@]}"; do
  check_path "$path" "200"
done

check_body_contains "/" "Latest FX Snapshot"
check_body_contains "/" "Portal"
check_body_contains "/portal/login" "Investor Login"
check_body_contains "/portal/login" "name=\"password\""

if [[ "$has_admin_auth" == true ]]; then
  check_body_contains "/admin/investors" "Create Investor" --user "${ADMIN_USER}:${ADMIN_PASS}"
  check_body_contains "/admin/cashflows" "Cashflows" --user "${ADMIN_USER}:${ADMIN_PASS}"
  check_body_contains "/admin/unit-price" "Unit Price" --user "${ADMIN_USER}:${ADMIN_PASS}"
else
  printf 'Admin credentials not set; expecting 401 for admin paths.\n'
  for path in "${ADMIN_PATHS[@]}"; do
    check_path "$path" "401"
  done
fi

if [[ $failures -gt 0 ]]; then
  printf 'Smoke test failed: %d check(s) failed.\n' "$failures"
  exit 1
fi

printf 'Smoke test passed.\n'
