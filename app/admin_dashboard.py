from __future__ import annotations

from decimal import Decimal
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from .db import get_db
from .auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


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

    # 3) Latest unit price
    px = db.execute(
        text("""
            select asof_at, price, note
            from unit_price_points
            where fund_id=:fid
            order by asof_at desc
            limit 1
        """),
        {"fid": fid},
    ).mappings().first()

    unit_price = Decimal(str(px["price"])) if px else None
    unit_price_asof = px["asof_at"] if px else None
    unit_price_note = px["note"] if px else None

    # 4) Total units
    total_units = db.execute(
        text("select coalesce(sum(units),0) from investor_positions where fund_id=:fid"),
        {"fid": fid},
    ).scalar_one()
    total_units = Decimal(str(total_units))

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

    snap_equity = Decimal(str(snap["equity"])) if snap and snap.get("equity") is not None else None
    snap_asof = snap["asof_at"] if snap else None
    snap_fxid = snap["fx_account_id"] if snap else None

    # 6) Implied unit price from latest equity (if possible)
    implied_px = None
    if snap_equity is not None and total_units > 0:
        implied_px = (snap_equity / total_units)

    return request.app.state.templates.TemplateResponse(
        "admin/index.html",
        {
            "request": request,
            "fund_id": fid,
            "inv_total": int(inv_total),
            "inv_active": int(inv_active),
            "pending": int(pending),
            "unit_price": unit_price,
            "unit_price_asof": unit_price_asof,
            "unit_price_note": unit_price_note,
            "total_units": total_units,
            "snap_fxid": snap_fxid,
            "snap_asof": snap_asof,
            "snap_equity": snap_equity,
            "implied_px": implied_px,
        },
    )
