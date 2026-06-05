#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def env_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(2)
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build and optionally send a signed FX snapshot webhook payload."
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Actually POST the signed snapshot. Default is dry-run.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BASE_URL", "https://rpqtfund.com"),
        help="Target base URL. Defaults to BASE_URL env or https://rpqtfund.com.",
    )
    parser.add_argument(
        "--balance",
        default=os.getenv("FX_BALANCE", "10000.00"),
        help="Sample balance value. Defaults to FX_BALANCE env or 10000.00.",
    )
    parser.add_argument(
        "--equity",
        default=os.getenv("FX_EQUITY", "10050.00"),
        help="Sample equity value. Defaults to FX_EQUITY env or 10050.00.",
    )
    parser.add_argument(
        "--asof-at",
        default=os.getenv("FX_ASOF_AT"),
        help="Snapshot asof_at. Defaults to current UTC ISO timestamp.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fx_account_id = env_required("FX_ACCOUNT_ID")
    secret = env_required("FX_SECRET")

    asof_at = args.asof_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload = {
        "asof_at": asof_at,
        "balance": args.balance,
        "equity": args.equity,
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    body_sha256 = hashlib.sha256(body).hexdigest()

    # Match app.fx_webhook._verify_sig: HMAC-SHA256(secret, raw body bytes).
    verify_signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(verify_signature, signature):
        print("Internal signing self-check failed.", file=sys.stderr)
        return 1

    url = f"{args.base_url.rstrip('/')}/fx/mt5/snapshot"
    print(f"Body SHA256: {body_sha256}")
    print(f"Signature length: {len(signature)}")
    if not args.send:
        print("DRY RUN: snapshot was not sent.")
        print(f"Target: {url}")
        print(f"FX account id: {fx_account_id}")
        print(f"Payload: {body.decode('utf-8')}")
        print("Run with --send to POST this signed payload.")
        return 0

    request = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "X-FX-Account-Id": fx_account_id,
            "X-Signature": signature,
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            print(response_body)
            return 0 if 200 <= response.status < 300 else 1
    except HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        print(response_body or f"HTTP {exc.code}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Request failed: {exc.reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
