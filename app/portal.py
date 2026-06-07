from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

from passlib.hash import argon2

from .db import get_db

router = APIRouter(prefix="/portal", tags=["portal"])
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)


def _require_login(request: Request) -> int:
    investor_id = request.session.get("investor_id")
    if not investor_id:
        raise ValueError("not_logged_in")
    return int(investor_id)


def _is_explicitly_inactive(value) -> bool:
    if value is False:
        return True
    if value is None:
        return False
    return str(value).strip().lower() in {"0", "false", "f", "no", "n", "off", "inactive"}


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, msg: str = ""):
    return templates.TemplateResponse(request, "portal/login.html", {"msg": msg})

@router.head("/login", response_class=HTMLResponse)
def login_head():
    return HTMLResponse(content="")

@router.post("/login")
def login_post(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    username = (username or "").strip()
    if not username or not password:
        return RedirectResponse(url="/portal/login?msg=missing", status_code=303)

    try:
        inv = db.execute(
            text("""
                SELECT id, username, password_hash, is_active
                FROM investors
                WHERE username = :u
                LIMIT 1
            """),
            {"u": username},
        ).mappings().first()
    except Exception:
        logger.exception("Failed to load investor during portal login")
        return RedirectResponse(url="/portal/login?msg=bad", status_code=303)

    if (not inv) or _is_explicitly_inactive(inv.get("is_active")):
        return RedirectResponse(url="/portal/login?msg=bad", status_code=303)

    ph = (inv.get("password_hash") or "").strip()
    try:
        password_ok = bool(ph) and argon2.verify(password, ph)
    except Exception:
        logger.exception("Failed to verify investor password hash")
        password_ok = False

    if not password_ok:
        return RedirectResponse(url="/portal/login?msg=bad", status_code=303)

    request.session["investor_id"] = int(inv["id"])
    return RedirectResponse(url="/portal/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/portal/login?msg=bye", status_code=303)


@router.get("/", response_class=HTMLResponse)
def portal_home(request: Request, fund_id: int = 1, db: Session = Depends(get_db)):
    try:
        investor_id = _require_login(request)
    except ValueError:
        return RedirectResponse(url="/portal/login", status_code=303)

    # latest unit price
    unit_price: Optional[Decimal] = None
    px_asof = None
    try:
        px_row = db.execute(
            text("""
                SELECT asof_at, price
                FROM unit_price_points
                WHERE fund_id=:fid
                ORDER BY asof_at DESC
                LIMIT 1
            """),
            {"fid": int(fund_id)},
        ).mappings().first()

        if px_row:
            unit_price = Decimal(str(px_row["price"]))
            px_asof = px_row["asof_at"]
    except Exception:
        logger.exception("Failed to load unit price for investor portal")

    # investor units
    units = Decimal("0")
    try:
        pos = db.execute(
            text("""
                SELECT units
                FROM investor_positions
                WHERE fund_id=:fid AND investor_id=:iid
                LIMIT 1
            """),
            {"fid": int(fund_id), "iid": int(investor_id)},
        ).mappings().first()
        units = Decimal(str(pos["units"])) if pos and pos.get("units") is not None else Decimal("0")
    except Exception:
        logger.exception("Failed to load investor units for portal")

    value = (units * unit_price) if (unit_price is not None) else None

    # cashflows
    flows = []
    try:
        flows = db.execute(
            text("""
                SELECT id, kind, currency, amount, status, requested_at, confirmed_at, cancelled_at
                FROM cashflow_requests
                WHERE fund_id=:fid AND investor_id=:iid
                ORDER BY requested_at DESC
                LIMIT 50
            """),
            {"fid": int(fund_id), "iid": int(investor_id)},
        ).mappings().all()
    except Exception:
        logger.exception("Failed to load cashflows for investor portal")

    return templates.TemplateResponse(
        request,
        "portal/index.html",
        {
            "fund_id": int(fund_id),
            "investor_id": int(investor_id),
            "units": units,
            "unit_price": unit_price,
            "px_asof": px_asof,
            "value": value,
            "flows": flows,
        },
    )
