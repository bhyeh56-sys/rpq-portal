#!/usr/bin/env bash
set -u

# Usage:
#   scripts/smoke_prod.sh
#   BASE_URL=https://staging.example.com scripts/smoke_prod.sh
#   ADMIN_USER=admin ADMIN_PASS='secret' scripts/smoke_prod.sh

BASE_URL="${BASE_URL:-https://redpinequant.com}"
BASE_URL="${BASE_URL%/}"

PUBLIC_PATHS=(
  "/"
  "/copy"
  "/risk"
  "/faq"
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

printf 'Smoke target: %s\n' "$BASE_URL"

for path in "${PUBLIC_PATHS[@]}"; do
  check_path "$path" "200"
done

if [[ "$has_admin_auth" == true ]]; then
  for path in "${ADMIN_PATHS[@]}"; do
    check_path "$path" "200" --user "${ADMIN_USER}:${ADMIN_PASS}"
  done
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
