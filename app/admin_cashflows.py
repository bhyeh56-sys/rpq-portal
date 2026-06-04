from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func, text
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .db import get_db
from .auth import require_admin
from .models import (
    Fund, Investor, InvestorPosition,
    UnitPricePoint, CashflowRequest, LedgerEntry,
    AuditLog,
)

router = APIRouter(prefix="/admin", tags=["admin-cashflows"])


def audit(db: Session, admin_id: int, action: str, target_type: str, target_id: int, diff: dict | None = None):
    db.add(AuditLog(
        actor_admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        diff=diff,
    ))


def parse_dt(s: str) -> datetime:
    s = (s or "").strip()
    if not s:
        raise ValueError("empty datetime")
    s = s.replace(" ", "T")
    return datetime.fromisoformat(s)


def latest_unit_price(db: Session, fund_id: int):
    row = db.execute(
        select(UnitPricePoint.price, UnitPricePoint.asof_at)
        .where(UnitPricePoint.fund_id == fund_id)
        .order_by(UnitPricePoint.asof_at.desc())
        .limit(1)
    ).first()
    return row  # (price, asof_at) or None


@router.get("/unit-price", response_class=HTMLResponse)
def unit_price_page(
    request: Request,
    fund_id: int = 1,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    funds = db.execute(select(Fund).order_by(Fund.id.asc())).scalars().all()
    latest = latest_unit_price(db, fund_id)
    return request.app.state.templates.TemplateResponse(
        "admin/unit_price.html",
        {"request": request, "funds": funds, "fund_id": fund_id, "latest": latest},
    )


@router.post("/unit-price", response_class=HTMLResponse)
def create_unit_price(
    request: Request,
    fund_id: int = Form(...),
    asof_at: str = Form(...),
    price: str = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    try:
        dt = parse_dt(asof_at)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid asof_at. Use ISO8601 like 2026-01-26T17:45:00+09:00")

    try:
        px = Decimal(price)
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=400, detail="Invalid price")

    fund = db.get(Fund, int(fund_id))
    if not fund:
        raise HTTPException(status_code=400, detail="Invalid fund_id")

    db.add(UnitPricePoint(fund_id=int(fund_id), asof_at=dt, price=px, note=note))
    audit(db, admin_id, "UNIT_PRICE_CREATE", "fund", int(fund_id), {"asof_at": asof_at, "price": str(px)})

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"DB error: {type(e).__name__}")

    # HTML 렌더링에서 500이 날 수 있으니 리다이렉트로 안전 처리
    return RedirectResponse(url=f"/admin/unit-price?fund_id={int(fund_id)}", status_code=303)


@router.get("/cashflows", response_class=HTMLResponse)
def cashflows_page(
    request: Request,
    status: str = "PENDING",
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    funds = db.execute(select(Fund).order_by(Fund.id.asc())).scalars().all()
    investors = db.execute(
        select(Investor).where(Investor.is_active.is_(True)).order_by(Investor.id.asc())
    ).scalars().all()

    flows = db.execute(
        select(CashflowRequest)
        .where(CashflowRequest.status == status)
        .order_by(CashflowRequest.id.desc())
        .limit(200)
    ).scalars().all()

    fund_map = {f.id: f for f in funds}
    inv_map = {i.id: i for i in investors}

    return request.app.state.templates.TemplateResponse(
        "admin/cashflows.html",
        {"request": request, "funds": funds, "investors": investors, "flows": flows,
         "status": status, "fund_map": fund_map, "inv_map": inv_map},
    )


@router.post("/cashflows", response_class=HTMLResponse)
def create_cashflow(
    request: Request,
    fund_id: int = Form(...),
    investor_id: int = Form(...),
    kind: str = Form(...),
    currency: str = Form("USD"),
    amount: str = Form(...),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    if kind not in ("DEPOSIT", "WITHDRAW"):
        raise HTTPException(status_code=400, detail="Invalid kind")

    inv = db.get(Investor, int(investor_id))
    if not inv or not inv.is_active:
        raise HTTPException(status_code=400, detail="Invalid investor")

    try:
        amt = Decimal(amount)
        if amt <= 0:
            raise InvalidOperation()
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=400, detail="Invalid amount")

    flow = CashflowRequest(
        kind=kind,
        amount=amt,
        status="PENDING",
        note=note,
        created_by_admin=admin_id,
    )
    db.add(flow)
    db.flush()

    audit(db, admin_id, "CASHFLOW_CREATE", "cashflow_request", flow.id, {
        "fund_id": int(fund_id),
        "investor_id": int(investor_id),
        "kind": kind,
        "currency": currency,
        "amount": str(amt),
    })

    db.commit()
    return RedirectResponse(url="/admin/cashflows?status=PENDING", status_code=303)


@router.post("/cashflows/{flow_id}/confirm", response_class=HTMLResponse)
def confirm_cashflow(
    request: Request,
    flow_id: int,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    flow = db.get(CashflowRequest, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Not found")
    if flow.status != "PENDING":
        raise HTTPException(status_code=400, detail="Not pending")

    latest = latest_unit_price(db, flow.fund_id)
    if not latest:
        raise HTTPException(status_code=400, detail="Missing unit price for this fund")
    price, asof_at = latest

    # ✅ Python에서 계산 (DB 문법/바인딩 이슈 제거)
    px = Decimal(str(price))
    amt = Decimal(str(flow.amount))
    if px <= 0:
        raise HTTPException(status_code=400, detail="Invalid unit price")
    units = (amt / px)

    # Ensure position exists
    db.execute(
        text("""
            INSERT INTO investor_positions (fund_id, investor_id, units)
            VALUES (:fund_id, :investor_id, 0)
            ON CONFLICT (fund_id, investor_id) DO NOTHING
        """),
        {"fund_id": flow.fund_id, "investor_id": flow.investor_id},
    )

    if flow.kind == "DEPOSIT":
        cash_delta = amt
        unit_delta = units
    else:
        cash_delta = -amt
        unit_delta = -units

        cur_units = db.execute(
            text("""
                SELECT units FROM investor_positions
                WHERE fund_id=:fund_id AND investor_id=:investor_id
            """),
            {"fund_id": flow.fund_id, "investor_id": flow.investor_id},
        ).scalar_one()

        if (Decimal(str(cur_units)) + unit_delta) < 0:
            raise HTTPException(status_code=400, detail="Insufficient units")

    # Ledger 2 lines
    db.add(LedgerEntry(
        source_type="CASHFLOW_REQUEST",
        source_id=flow.id,
        account="CASH",
        amount=cash_delta,
        unit_price=px,
    ))
    db.add(LedgerEntry(
        source_type="CASHFLOW_REQUEST",
        source_id=flow.id,
        account="UNITS",
        amount=unit_delta,
        unit_price=px,
    ))

    # Position update
    db.execute(
        text("""
            UPDATE investor_positions
            SET units = units + :dunits
            WHERE fund_id=:fund_id AND investor_id=:investor_id
        """),
        {"dunits": unit_delta, "fund_id": flow.fund_id, "investor_id": flow.investor_id},
    )

    flow.status = "CONFIRMED"
    flow.confirmed_at = func.now()

    audit(db, admin_id, "CASHFLOW_CONFIRM", "cashflow_request", flow.id, {
        "unit_price": str(px),
        "units": str(units),
        "asof_at": str(asof_at),
    })

    db.commit()
    return RedirectResponse(url="/admin/cashflows?status=PENDING", status_code=303)


@router.post("/cashflows/{flow_id}/cancel", response_class=HTMLResponse)
def cancel_cashflow(
    request: Request,
    flow_id: int,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    flow = db.get(CashflowRequest, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Not found")
    if flow.status != "PENDING":
        raise HTTPException(status_code=400, detail="Not pending")

    flow.status = "CANCELLED"
    flow.cancelled_at = func.now()

    audit(db, admin_id, "CASHFLOW_CANCEL", "cashflow_request", flow.id)
    db.commit()

    return RedirectResponse(url="/admin/cashflows?status=PENDING", status_code=303)
