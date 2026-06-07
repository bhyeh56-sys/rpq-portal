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
  "/copy"
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

check_content() {
  local url="$1"
  local expected="$2"
  local label="$3"

  local body_file
  body_file=$(mktemp)
  local result
  result=$(curl -sS -X GET -o "$body_file" -w "%{http_code} %{redirect_url}" --connect-timeout 10 --max-time 20 "$url")
  local curl_status=$?
  local code="${result%% *}"
  local redirect_url="${result#* }"

  if [[ $curl_status -eq 0 && "$code" == "200" && "$redirect_url" != "$OLD_COPY_REDIRECT_TARGET" && grep -qi "$expected" "$body_file" ]]; then
    printf 'OK   %s -> 200 contains %s\n' "$url" "$label"
  else
    printf 'FAIL %s -> %s redirect=%s (expected 200 containing %s, curl exit %s)\n' "$url" "$code" "$redirect_url" "$label" "$curl_status"
    failures=$((failures + 1))
  fi

  rm -f "$body_file"
}

printf 'Primary target: %s\n' "$BASE_URL"

check_content "${BASE_URL}/" "<title>RedPine Quant</title>" "company title"

for path in "${PUBLIC_PATHS[@]}"; do
  check_get "${BASE_URL}${path}" "200"
done

printf 'Fund targets: %s %s\n' "$FUND_URL" "$FUND_WWW_URL"
check_content "${FUND_URL}/" "<title>RedPineQuant Fund Portal</title>" "portal title"
check_get "${FUND_WWW_URL}/" "200"
check_content "${FUND_URL}/fund" "<title>RedPine Quant 투자조합 참여 검토</title>" "fund title"

if [[ $failures -gt 0 ]]; then
  printf 'Smoke test failed: %d check(s) failed.\n' "$failures"
  exit 1
fi

printf 'Smoke test passed.\n'
