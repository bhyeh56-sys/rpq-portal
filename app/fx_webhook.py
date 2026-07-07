# app/fx_webhook.py
import json
import hmac
import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text

from .db import get_db
from .models import FXAccount

router = APIRouter(prefix="/fx", tags=["fx"])


def _parse_dt(s: str) -> datetime:
    s = (s or "").strip()
    if not s:
        raise ValueError("empty asof_at")
    if " " in s and "T" not in s:
        s = s.replace(" ", "T", 1)
    return datetime.fromisoformat(s)


def _normalize_asof(dt: datetime) -> datetime:
    return dt.replace(microsecond=0)


def _D(x) -> Decimal:
    try:
        return Decimal(str(x))
    except (InvalidOperation, TypeError):
        raise ValueError(f"invalid decimal: {x}")


def _verify_sig(secret: str, body: bytes, sig_hex: str | None):
    if not sig_hex:
        raise HTTPException(status_code=401, detail="Missing X-Signature")

    sig = sig_hex.strip().lower()

    # A) 표준: HMAC-SHA256(secret, body_bytes)
    mac_hmac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    # B) 레거시: SHA256(secret + body_bytes)
    mac_concat = hashlib.sha256(secret.encode("utf-8") + body).hexdigest()

    if not (hmac.compare_digest(mac_hmac, sig) or hmac.compare_digest(mac_concat, sig)):
        raise HTTPException(status_code=401, detail="Bad signature")


@router.post("/mt5/snapshot")
async def mt5_snapshot(request: Request, db: Session = Depends(get_db)):
    fx_id = request.headers.get("X-FX-Account-Id")
    if not fx_id:
        raise HTTPException(status_code=401, detail="Missing X-FX-Account-Id")

    fx = db.get(FXAccount, int(fx_id))
    if not fx or not fx.is_active:
        raise HTTPException(status_code=404, detail="FX account not found")

    body = await request.body()
    _verify_sig(fx.secret, body, request.headers.get("X-Signature"))

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body must be JSON")

    try:
        asof_at_raw = _parse_dt(payload.get("asof_at"))
        asof_at = _normalize_asof(asof_at_raw)

        balance = _D(payload.get("balance"))
        equity = _D(payload.get("equity"))
        margin = payload.get("margin")
        free_margin = payload.get("free_margin")
        margin_d = _D(margin) if margin is not None else None
        free_d = _D(free_margin) if free_margin is not None else None
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bad payload: {e}")

    profit = equity - balance

    # 1) snapshot UPSERT (idempotent for the exact sender timestamp)
    db.execute(
        text(
            """
            INSERT INTO fx_account_snapshots
              (fx_account_id, asof_at, balance, equity, margin, free_margin, profit, raw)
            VALUES
              (:fxid, :asof, :bal, :eq, :m, :fm, :pf, CAST(:raw AS jsonb))
            ON CONFLICT (fx_account_id, asof_at)
            DO UPDATE SET
              balance = EXCLUDED.balance,
              equity = EXCLUDED.equity,
              margin = EXCLUDED.margin,
              free_margin = EXCLUDED.free_margin,
              profit = EXCLUDED.profit,
              raw = EXCLUDED.raw
            """
        ),
        {
            "fxid": fx.id,
            "asof": asof_at,
            "bal": balance,
            "eq": equity,
            "m": margin_d,
            "fm": free_d,
            "pf": profit,
            "raw": json.dumps(payload),
        },
    )

    # 2) total units
    total_units = db.execute(
        text("SELECT COALESCE(SUM(units),0) FROM investor_positions WHERE fund_id=:fid"),
        {"fid": fx.fund_id},
    ).scalar_one()
    total_units = Decimal(str(total_units))

    # 3) unit price UPSERT (same sender timestamp)
    unit_price = None
    auto_created = False
    if total_units > 0:
        unit_price = (equity / total_units)
        db.execute(
            text(
                """
                INSERT INTO unit_price_points (fund_id, asof_at, price, note)
                VALUES (:fid, :asof, :px, :note)
                ON CONFLICT (fund_id, asof_at)
                DO UPDATE SET price = EXCLUDED.price, note = EXCLUDED.note
                """
            ),
            {
                "fid": fx.fund_id,
                "asof": asof_at,
                "px": unit_price,
                "note": f"AUTO from FX snapshot fx_account_id={fx.id}",
            },
        )
        auto_created = True

    db.commit()

    return {
        "ok": True,
        "fx_account_id": fx.id,
        "fund_id": fx.fund_id,
        "asof_at_raw": payload.get("asof_at"),
        "asof_at": asof_at.isoformat(),
        "balance": str(balance),
        "equity": str(equity),
        "profit": str(profit),
        "total_units": str(total_units),
        "unit_price": (str(unit_price) if unit_price is not None else None),
        "auto_unit_price_created": auto_created,
        "idempotent": True,
    }


@router.get("/snapshots/latest")
def latest_snapshot(fx_account_id: int, db: Session = Depends(get_db)):
    row = db.execute(
        text(
            """
            select id, fx_account_id, asof_at, balance, equity, profit
            from fx_account_snapshots
            where fx_account_id = :fxid
            order by asof_at desc
            limit 1
            """
        ),
        {"fxid": fx_account_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="no snapshots")
    return dict(row)


@router.get("/snapshots/recent")
def recent_snapshots(
    fx_account_id: int,
    limit: int = 20,
    period: str | None = None,
    db: Session = Depends(get_db),
):
    period_seconds = {
        "5m": 5 * 60,
        "1h": 60 * 60,
        "1d": 24 * 60 * 60,
    }

    if period:
        normalized_period = period.strip().lower()
        if normalized_period not in period_seconds:
            raise HTTPException(status_code=400, detail="period must be one of 5m, 1h, 1d")

        rows = db.execute(
            text(
                """
                select id, fx_account_id, asof_at, balance, equity, profit
                from fx_account_snapshots
                where fx_account_id = :fxid
                  and asof_at >= now() - (:seconds * interval '1 second')
                order by asof_at desc
                """
            ),
            {"fxid": fx_account_id, "seconds": period_seconds[normalized_period]},
        ).mappings().all()

        return {
            "count": len(rows),
            "period": normalized_period,
            "items": [dict(r) for r in rows],
        }

    limit = max(1, min(int(limit), 200))
    rows = db.execute(
        text(
            """
            select id, fx_account_id, asof_at, balance, equity, profit
            from fx_account_snapshots
            where fx_account_id = :fxid
            order by asof_at desc
            limit :lim
            """
        ),
        {"fxid": fx_account_id, "lim": limit},
    ).mappings().all()

    return {"count": len(rows), "items": [dict(r) for r in rows]}
