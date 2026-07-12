# app/main.py
import logging
import os
from decimal import Decimal, InvalidOperation

from fastapi import Depends, FastAPI, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from . import admin_dashboard
from .admin_cashflows import router as admin_cashflows_router
from .admin_investors import router as admin_investors_router
from .db import get_db
from .fx_webhook import router as fx_router
from .portal import router as portal_router

app = FastAPI(title="RPQ Portal")
logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="templates")
app.state.templates = templates

SESSION_SECRET = os.environ["SESSION_SECRET"]
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=True,
)

app.include_router(admin_investors_router)
app.include_router(admin_cashflows_router)
app.include_router(fx_router)
app.include_router(portal_router)
app.include_router(admin_dashboard.router)


def _decimal_or_none(value):
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _money(value):
    dec = _decimal_or_none(value)
    if dec is None:
        return None
    sign = "-" if dec < 0 else ""
    return f"{sign}${abs(dec):,.2f}"


def _pct(value):
    dec = _decimal_or_none(value)
    if dec is None:
        return None
    return f"{dec:+,.2f}%"


def _chart_path(rows):
    points = list(reversed(rows or []))
    equities = [_decimal_or_none(row.get("equity")) for row in points]
    equities = [value for value in equities if value is not None]
    if len(equities) < 2:
        return "M 0 74 L 300 74"

    low = min(equities)
    high = max(equities)
    span = high - low
    if span == 0:
        span = Decimal("1")

    coords = []
    last_index = len(equities) - 1
    for index, value in enumerate(equities):
        x = Decimal(300) * Decimal(index) / Decimal(last_index)
        normalized = (value - low) / span
        y = Decimal(78) - (normalized * Decimal(42))
        coords.append(f"{float(x):.1f} {float(y):.1f}")

    return "M " + " L ".join(coords)


def _public_context(request: Request, lang: str | None):
    selected = (lang or request.query_params.get("lang") or "en").strip().lower()
    if selected not in {"en", "ko"}:
        selected = "en"
    return {
        "lang": selected,
        "contact_email": os.getenv("CONTACT_EMAIL", "info@redpinequant.com"),
        "global_prime_copy_url": os.getenv("GLOBAL_PRIME_COPY_URL", ""),
        "copy_link_configured": bool(os.getenv("GLOBAL_PRIME_COPY_URL", "")),
        "myfxbook_url": os.getenv("MYFXBOOK_URL", ""),
        "fxblue_url": os.getenv("FXBLUE_URL", ""),
    }


def _is_redpine_host(request: Request):
    host = request.headers.get("host", "").split(":", 1)[0].lower()
    return host in {"redpinequant.com", "www.redpinequant.com"}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/")
def home(
    request: Request,
    fx_account_id: int = 1,
    lang: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if _is_redpine_host(request):
        return templates.TemplateResponse(
            request,
            "company_home.html",
            _public_context(request, lang),
        )

    snap = None
    recent = []
    metrics = {
        "balance": None,
        "equity": None,
        "profit": None,
        "return_rate": None,
        "previous_equity": None,
        "equity_change": None,
        "chart_path": "M 0 74 L 300 74",
    }
    try:
        rows = db.execute(
            text(
                """
                select fx_account_id, asof_at, balance, equity, profit
                from fx_account_snapshots
                where fx_account_id = :fxid
                order by asof_at desc
                limit 12
            """
            ),
            {"fxid": fx_account_id},
        ).mappings().all()
        recent = [dict(row) for row in rows]
        snap = recent[0] if recent else None

        if snap:
            balance = _decimal_or_none(snap.get("balance"))
            equity = _decimal_or_none(snap.get("equity"))
            profit = _decimal_or_none(snap.get("profit"))
            previous_equity = _decimal_or_none(recent[1].get("equity")) if len(recent) > 1 else None
            equity_change = (equity - previous_equity) if equity is not None and previous_equity is not None else None
            return_rate = (profit / balance * Decimal("100")) if profit is not None and balance not in (None, 0) else None

            metrics = {
                "balance": _money(balance),
                "equity": _money(equity),
                "profit": _money(profit),
                "return_rate": _pct(return_rate),
                "previous_equity": _money(previous_equity),
                "equity_change": _money(equity_change),
                "chart_path": _chart_path(recent),
            }
    except Exception:
        logger.exception("Failed to load latest FX snapshot for portal home")

    return templates.TemplateResponse(
        request,
        "index.html",
        {"snap": snap, "recent": recent, "metrics": metrics, "fx_account_id": fx_account_id},
    )


@app.head("/")
def home_head():
    return


@app.get("/copy")
def copy_page(request: Request, lang: str | None = Query(default=None)):
    return templates.TemplateResponse(request, "copy.html", _public_context(request, lang))


@app.get("/fund")
def fund_page(request: Request, lang: str | None = Query(default=None)):
    return templates.TemplateResponse(request, "fund.html", _public_context(request, lang))


@app.get("/risk")
def risk_page(request: Request, lang: str | None = Query(default=None)):
    return templates.TemplateResponse(request, "risk.html", _public_context(request, lang))


@app.get("/faq")
def faq_page(request: Request, lang: str | None = Query(default=None)):
    return templates.TemplateResponse(request, "faq.html", _public_context(request, lang))
