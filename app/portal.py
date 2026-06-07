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

INVESTOR_LOGIN_SQL = text(
    """
    SELECT id, username, password_hash, is_active
    FROM investors
    WHERE username = :u
    LIMIT 1
    """
)


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


def is_active_enabled(value) -> bool:
    return not _is_explicitly_inactive(value)


def verify_investor_password(password: str, password_hash: str | None) -> tuple[bool, str | None]:
    ph = (password_hash or "").strip()
    if not ph:
        return False, None
    try:
        return bool(argon2.verify(password, ph)), None
    except Exception as exc:
        return False, type(exc).__name__


def load_investor_login_row(db: Session, username: str):
    return db.execute(INVESTOR_LOGIN_SQL, {"u": username}).mappings().first()


def evaluate_investor_login(row, password: str) -> dict:
    password_hash = (row.get("password_hash") or "").strip() if row else ""
    is_active = row.get("is_active") if row else None
    active_result = is_active_enabled(is_active) if row else False
    verify_result, verify_exception = verify_investor_password(password, password_hash)

    if not row:
        reason = "row_not_found"
    elif not active_result:
        reason = "inactive"
    elif not verify_result:
        reason = "password_verify_failed"
    else:
        reason = "success"

    return {
        "success": reason == "success",
        "reason": reason,
        "id": row.get("id") if row else None,
        "username": row.get("username") if row else None,
        "row_found": bool(row),
        "is_active_raw": is_active,
        "is_active_type": type(is_active).__name__,
        "active_result": active_result,
        "password_hash_prefix": password_hash[:32],
        "password_hash_length": len(password_hash),
        "verify_result": verify_result,
        "verify_exception": verify_exception,
    }


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
    raw_username = username
    username = (username or "").strip()
    if not username:
        logger.warning(
            "portal_login_failed reason=missing_username username_raw=%r username_stripped=%r",
            raw_username,
            username,
        )
        return RedirectResponse(url="/portal/login?msg=missing", status_code=303)
    if not password:
        logger.warning(
            "portal_login_failed reason=missing_password username_raw=%r username_stripped=%r",
            raw_username,
            username,
        )
        return RedirectResponse(url="/portal/login?msg=missing", status_code=303)

    try:
        inv = load_investor_login_row(db, username)
    except Exception:
        logger.exception(
            "portal_login_failed reason=query_exception username_raw=%r username_stripped=%r",
            raw_username,
            username,
        )
        return RedirectResponse(url="/portal/login?msg=bad", status_code=303)

    decision = evaluate_investor_login(inv, password)
    if not decision["success"]:
        logger.warning(
            "portal_login_failed reason=%s username_raw=%r username_stripped=%r row_found=%s "
            "investor_id=%r is_active_raw=%r is_active_type=%s active_result=%s "
            "password_hash_prefix=%r password_hash_length=%s verify_result=%s verify_exception=%r",
            decision["reason"],
            raw_username,
            username,
            decision["row_found"],
            decision["id"],
            decision["is_active_raw"],
            decision["is_active_type"],
            decision["active_result"],
            decision["password_hash_prefix"],
            decision["password_hash_length"],
            decision["verify_result"],
            decision["verify_exception"],
        )
        return RedirectResponse(url="/portal/login?msg=bad", status_code=303)

    request.session["investor_id"] = int(decision["id"])
    logger.info(
        "portal_login_success username=%r investor_id=%s redirect=/portal/ session_key_set=%s",
        username,
        decision["id"],
        "investor_id" in request.session,
    )
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
