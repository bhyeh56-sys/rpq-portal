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

check_get_any() {
  local url="$1"
  shift

  local result
  result=$(curl -sS -X GET -o /dev/null -w "%{http_code} %{redirect_url}" --connect-timeout 10 --max-time 20 "$url")
  local curl_status=$?
  local code="${result%% *}"
  local redirect_url="${result#* }"
  local expected

  if [[ $curl_status -eq 0 && "$redirect_url" != "$OLD_COPY_REDIRECT_TARGET" ]]; then
    for expected in "$@"; do
      if [[ "$code" == "$expected" ]]; then
        printf 'OK   %s -> %s\n' "$url" "$code"
        return
      fi
    done
  fi

  printf 'FAIL %s -> %s redirect=%s (expected one of: %s; curl exit %s)\n' "$url" "$code" "$redirect_url" "$*" "$curl_status"
  failures=$((failures + 1))
}

check_content() {
  local url="$1"
  local expected="$2"
  local label="$3"

  local result
  result=$(curl -sS -X GET -w $'\n__RPQ_STATUS__%{http_code} %{redirect_url}' --connect-timeout 10 --max-time 20 "$url")
  local curl_status=$?
  local status_line="${result##*$'\n'__RPQ_STATUS__}"
  local body="${result%$'\n'__RPQ_STATUS__*}"
  local code="${status_line%% *}"
  local redirect_url="${status_line#* }"

  if [[ $curl_status -eq 0 && "$code" == "200" && "$redirect_url" != "$OLD_COPY_REDIRECT_TARGET" ]] && printf '%s' "$body" | grep -qi "$expected"; then
    printf 'OK   %s -> 200 contains %s\n' "$url" "$label"
  else
    printf 'FAIL %s -> %s redirect=%s (expected 200 containing %s, curl exit %s)\n' "$url" "$code" "$redirect_url" "$label" "$curl_status"
    failures=$((failures + 1))
  fi
}

printf 'Primary target: %s\n' "$BASE_URL"

check_content "${BASE_URL}/" "<title>RedPine Quant</title>" "company title"

for path in "${PUBLIC_PATHS[@]}"; do
  check_get "${BASE_URL}${path}" "200"
done

printf 'Fund targets: %s %s\n' "$FUND_URL" "$FUND_WWW_URL"
check_content "${FUND_URL}/" "<title>RedPineQuant Fund Portal</title>" "portal title"
check_content "${FUND_URL}/" "Latest FX Snapshot" "snapshot section"
check_content "${FUND_URL}/portal/login" "<title>Investor Login</title>" "investor login title"
check_get_any "${FUND_URL}/admin/investors" "401" "200"
check_get "${FUND_WWW_URL}/" "200"
check_content "${FUND_URL}/fund" "<title>RedPine Quant" "fund title"

if [[ $failures -gt 0 ]]; then
  printf 'Smoke test failed: %d check(s) failed.\n' "$failures"
  exit 1
fi

printf 'Smoke test passed.\n'
