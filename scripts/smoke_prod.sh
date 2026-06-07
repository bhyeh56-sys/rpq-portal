#!/usr/bin/env bash
set -u

# Usage:
#   scripts/smoke_prod.sh
#   BASE_URL=https://staging.example.com scripts/smoke_prod.sh
#   ADMIN_USER=admin ADMIN_PASS='secret' scripts/smoke_prod.sh
#   LOCAL_APP_URL=http://127.0.0.1:8000 scripts/smoke_prod.sh
#
# App-direct checks behind nginx can be run separately with:
#   curl -H "Host: rpqtfund.com" -H "X-Admin-User: admin" http://127.0.0.1:8001/admin/investors
#   curl -H "Host: rpqtfund.com" -H "X-Admin-User: admin" http://127.0.0.1:8001/admin/unit-price
#   curl -H "Host: rpqtfund.com" -H "X-Admin-User: admin" http://127.0.0.1:8001/admin/cashflows

BASE_URL="${BASE_URL:-https://rpqtfund.com}"
BASE_URL="${BASE_URL%/}"
LOCAL_APP_URL="${LOCAL_APP_URL:-}"
LOCAL_APP_URL="${LOCAL_APP_URL%/}"
HOST_HEADER="${HOST_HEADER:-rpqtfund.com}"

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

check_url_body_contains() {
  local url="$1"
  local expected="$2"
  shift 2

  local body_file
  body_file="$(mktemp)"

  local code
  code=$(curl -sS -o "$body_file" -w "%{http_code}" --connect-timeout 10 --max-time 20 "$@" "$url")
  local curl_status=$?

  if [[ $curl_status -eq 0 && "$code" == "200" ]] && grep -qi "$expected" "$body_file"; then
    printf 'OK   %s contains "%s"\n' "$url" "$expected"
  else
    printf 'FAIL %s content check for "%s" (status %s, curl exit %s)\n' "$url" "$expected" "$code" "$curl_status"
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
check_body_contains "/" "/portal/login"
check_body_contains "/" "/admin/investors"
check_body_contains "/" "/admin/unit-price"
check_body_contains "/portal/login" "Investor Login"
check_body_contains "/portal/login" "form"
check_body_contains "/portal/login" "username"
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

if [[ -n "$LOCAL_APP_URL" ]]; then
  printf 'Local app target: %s (Host: %s)\n' "$LOCAL_APP_URL" "$HOST_HEADER"
  check_url_body_contains "${LOCAL_APP_URL}/" "Latest FX Snapshot" -H "Host: ${HOST_HEADER}"
  check_url_body_contains "${LOCAL_APP_URL}/" "/portal/login" -H "Host: ${HOST_HEADER}"
  check_url_body_contains "${LOCAL_APP_URL}/" "/admin/investors" -H "Host: ${HOST_HEADER}"
  check_url_body_contains "${LOCAL_APP_URL}/admin/investors" "Create Investor" -H "Host: ${HOST_HEADER}" -H "X-Admin-User: admin"
  check_url_body_contains "${LOCAL_APP_URL}/admin/unit-price" "Unit Price" -H "Host: ${HOST_HEADER}" -H "X-Admin-User: admin"
  check_url_body_contains "${LOCAL_APP_URL}/admin/cashflows" "Cashflows" -H "Host: ${HOST_HEADER}" -H "X-Admin-User: admin"
  check_url_body_contains "${LOCAL_APP_URL}/admin/" "NAV Status" -H "Host: ${HOST_HEADER}" -H "X-Admin-User: admin"
  check_url_body_contains "${LOCAL_APP_URL}/admin/" "Latest FX Snapshot" -H "Host: ${HOST_HEADER}" -H "X-Admin-User: admin"
  check_url_body_contains "${LOCAL_APP_URL}/admin/" "Latest Unit Price" -H "Host: ${HOST_HEADER}" -H "X-Admin-User: admin"

  if [[ -n "${PORTAL_TEST_USERNAME:-}" && -n "${PORTAL_TEST_PASSWORD:-}" ]]; then
    header_file="$(mktemp)"
    login_code=$(curl -sS -o /dev/null -D "$header_file" -w "%{http_code}" \
      --connect-timeout 10 --max-time 20 \
      -H "Host: ${HOST_HEADER}" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      --data-urlencode "username=${PORTAL_TEST_USERNAME}" \
      --data-urlencode "password=${PORTAL_TEST_PASSWORD}" \
      "${LOCAL_APP_URL}/portal/login")
    login_status=$?
    login_location="$(grep -i '^location:' "$header_file" | head -n 1 | sed -E 's/^[Ll]ocation:[[:space:]]*//; s/\r$//')"
    if [[ $login_status -eq 0 && "$login_code" == "303" && "$login_location" == "/portal/" ]]; then
      printf 'OK   local portal login POST -> %s\n' "$login_code"
      session_cookie="$(grep -i '^set-cookie:' "$header_file" | grep -i 'session=' | head -n 1 | sed -E 's/\r$//; s/.*[Ss][Ee][Ss][Ss][Ii][Oo][Nn]=([^;]+).*/session=\1/')"
      if [[ -n "$session_cookie" ]]; then
        printf 'OK   local portal login returned session cookie.\n'
        check_url_body_contains "${LOCAL_APP_URL}/portal/" "Investor Portal" -H "Host: ${HOST_HEADER}" -H "Cookie: ${session_cookie}"
        check_url_body_contains "${LOCAL_APP_URL}/portal/" "Units" -H "Host: ${HOST_HEADER}" -H "Cookie: ${session_cookie}"
        check_url_body_contains "${LOCAL_APP_URL}/portal/" "Unit price" -H "Host: ${HOST_HEADER}" -H "Cookie: ${session_cookie}"
        check_url_body_contains "${LOCAL_APP_URL}/portal/" "Recent Cashflows" -H "Host: ${HOST_HEADER}" -H "Cookie: ${session_cookie}"
      else
        printf 'FAIL local portal login POST did not return a session cookie.\n'
        printf 'Observed login redirect location: %s\n' "${login_location:-<none>}"
        failures=$((failures + 1))
      fi
    else
      printf 'FAIL local portal login POST -> %s location=%s (expected 303 location=/portal/, curl exit %s)\n' "$login_code" "${login_location:-<none>}" "$login_status"
      failures=$((failures + 1))
    fi
    rm -f "$header_file"
  else
    printf 'Portal login POST skipped; set PORTAL_TEST_USERNAME and PORTAL_TEST_PASSWORD to enable it.\n'
  fi
fi

if [[ $failures -gt 0 ]]; then
  printf 'Smoke test failed: %d check(s) failed.\n' "$failures"
  exit 1
fi

printf 'Smoke test passed.\n'
