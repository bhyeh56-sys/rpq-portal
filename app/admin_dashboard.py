from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from .db import get_db
from .auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


def _decimal_or_none(value) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _age_info(asof_at):
    if not asof_at:
        return {"status": "No data", "level": "nodata", "age": "Not available"}

    now = datetime.now(timezone.utc)
    dt = asof_at
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return {"status": "Unknown", "level": "warn", "age": str(asof_at)}
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    age = max(now - dt, timedelta(0))
    total_seconds = int(age.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60

    if hours >= 48:
        age_label = f"{hours // 24}d {hours % 24}h ago"
    elif hours >= 1:
        age_label = f"{hours}h {minutes}m ago"
    else:
        age_label = f"{minutes}m ago"

    if hours >= 24:
        return {"status": "주의", "level": "warn", "age": age_label}
    return {"status": "정상", "level": "ok", "age": age_label}


@router.get("", response_class=HTMLResponse)   # /admin  (no trailing slash)
@router.get("/", response_class=HTMLResponse)  # /admin/
def admin_home(
    request: Request,
    fund_id: int = 1,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    fid = int(fund_id)

    # 1) Investors count (active / total)
    inv_total = db.execute(text("select count(*) from investors")).scalar_one()
    inv_active = db.execute(text("select count(*) from investors where is_active=true")).scalar_one()

    # 2) Pending cashflows count
    pending = db.execute(
        text("""
            select count(*)
            from cashflow_requests
            where fund_id=:fid and status='PENDING'
        """),
        {"fid": fid},
    ).scalar_one()

    # 3) Latest unit price for selected fund
    px = db.execute(
        text("""
            select fund_id, asof_at, price, note
            from unit_price_points
            where fund_id=:fid
            order by asof_at desc
            limit 1
        """),
        {"fid": fid},
    ).mappings().first()

    unit_price = _decimal_or_none(px["price"]) if px else None
    unit_price_asof = px["asof_at"] if px else None
    unit_price_fund_id = int(px["fund_id"]) if px else fid
    unit_price_note = px["note"] if px else None

    # 4) Total units for selected fund
    total_units = db.execute(
        text("select coalesce(sum(units),0) from investor_positions where fund_id=:fid"),
        {"fid": fid},
    ).scalar_one()
    total_units = Decimal(str(total_units))

    units_by_fund = db.execute(
        text("""
            select f.id as fund_id, f.name as fund_name, coalesce(sum(p.units), 0) as total_units
            from funds f
            left join investor_positions p on p.fund_id = f.id
            group by f.id, f.name
            order by f.id asc
        """)
    ).mappings().all()
    units_by_fund = [
        {
            "fund_id": int(row["fund_id"]),
            "fund_name": row["fund_name"],
            "total_units": Decimal(str(row["total_units"])),
        }
        for row in units_by_fund
    ]

    # 5) Latest FX snapshot (across active fx accounts for the fund)
    snap = db.execute(
        text("""
            select s.fx_account_id, s.asof_at, s.balance, s.equity, s.profit
            from fx_account_snapshots s
            join fx_accounts a on a.id = s.fx_account_id
            where a.fund_id=:fid and a.is_active=true
            order by s.asof_at desc
            limit 1
        """),
        {"fid": fid},
    ).mappings().first()

    snap_balance = _decimal_or_none(snap["balance"]) if snap else None
    snap_equity = _decimal_or_none(snap["equity"]) if snap else None
    snap_profit = _decimal_or_none(snap["profit"]) if snap else None
    snap_asof = snap["asof_at"] if snap else None
    snap_fxid = snap["fx_account_id"] if snap else None

    # 6) Implied unit price from latest equity (if possible)
    implied_px = None
    if snap_equity is not None and total_units > 0:
        implied_px = (snap_equity / total_units)

    snap_age = _age_info(snap_asof)
    unit_price_age = _age_info(unit_price_asof)
    if snap_age["level"] == "nodata" or unit_price_age["level"] == "nodata":
        nav_status = {"status": "No data", "level": "nodata", "detail": "Snapshot or unit price is missing."}
    elif snap_age["level"] == "warn" or unit_price_age["level"] == "warn":
        nav_status = {"status": "주의", "level": "warn", "detail": "Snapshot or unit price is older than 24h."}
    else:
        nav_status = {"status": "정상", "level": "ok", "detail": "Snapshot and unit price are recent."}

    return request.app.state.templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "fund_id": fid,
            "inv_total": int(inv_total),
            "inv_active": int(inv_active),
            "pending": int(pending),
            "unit_price": unit_price,
            "unit_price_fund_id": unit_price_fund_id,
            "unit_price_asof": unit_price_asof,
            "unit_price_age": unit_price_age,
            "unit_price_note": unit_price_note,
            "total_units": total_units,
            "units_by_fund": units_by_fund,
            "snap_fxid": snap_fxid,
            "snap_asof": snap_asof,
            "snap_age": snap_age,
            "snap_balance": snap_balance,
            "snap_equity": snap_equity,
            "snap_profit": snap_profit,
            "implied_px": implied_px,
            "nav_status": nav_status,
        },
    )
