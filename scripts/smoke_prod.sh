#!/usr/bin/env bash
set -u

# Usage:
#   bash scripts/smoke_prod.sh
#   BASE_URL=https://staging.example.com bash scripts/smoke_prod.sh

BASE_URL="${BASE_URL:-https://redpinequant.com}"
BASE_URL="${BASE_URL%/}"
FUND_URL="${FUND_URL:-https://rpqtfund.com}"
FUND_URL="${FUND_URL%/}"
FUND_WWW_URL="${FUND_WWW_URL:-https://www.rpqtfund.com}"
FUND_WWW_URL="${FUND_WWW_URL%/}"
OLD_COPY_REDIRECT_TARGET="https://redpinequant.com/copy"

PUBLIC_PATHS=(
  "/"
  "/copy"
  "/risk"
  "/faq"
  "/fund"
)

failures=0

check_get() {
  local url="$1"
  local expected="$2"

  local result
  result=$(curl -sS -X GET -o /dev/null -w "%{http_code} %{redirect_url}" --connect-timeout 10 --max-time 20 "$url")
  local curl_status=$?
  local code="${result%% *}"
  local redirect_url="${result#* }"

  if [[ $curl_status -eq 0 && "$code" == "$expected" ]]; then
    if [[ "$redirect_url" == "$OLD_COPY_REDIRECT_TARGET" ]]; then
      printf 'FAIL %s -> %s redirect=%s (must not redirect to old copy target)\n' "$url" "$code" "$redirect_url"
      failures=$((failures + 1))
    else
      printf 'OK   %s -> %s\n' "$url" "$code"
    fi
  else
    printf 'FAIL %s -> %s redirect=%s (expected %s, curl exit %s)\n' "$url" "$code" "$redirect_url" "$expected" "$curl_status"
    failures=$((failures + 1))
  fi
}

printf 'Primary target: %s\n' "$BASE_URL"

for path in "${PUBLIC_PATHS[@]}"; do
  check_get "${BASE_URL}${path}" "200"
done

printf 'Fund targets: %s %s\n' "$FUND_URL" "$FUND_WWW_URL"
check_get "${FUND_URL}/" "200"
check_get "${FUND_WWW_URL}/" "200"

if [[ $failures -gt 0 ]]; then
  printf 'Smoke test failed: %d check(s) failed.\n' "$failures"
  exit 1
fi

printf 'Smoke test passed.\n'
