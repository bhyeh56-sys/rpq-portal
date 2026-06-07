# app/main.py
import os

from fastapi import FastAPI, Request, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from . import admin_dashboard
from .admin_cashflows import router as admin_cashflows_router
from .admin_investors import router as admin_investors_router
from .db import SessionLocal
from .fx_webhook import router as fx_router
from .portal import router as portal_router

app = FastAPI(title="RPQ Portal")

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


@app.get("/health")
def health():
    return {"ok": True}


def public_context(request: Request) -> dict:
    global_prime_copy_url = os.getenv("GLOBAL_PRIME_COPY_URL", "").strip()
    myfxbook_url = os.getenv("MYFXBOOK_URL", "").strip()
    fxblue_url = os.getenv("FXBLUE_URL", "").strip()
    contact_email = os.getenv("CONTACT_EMAIL", "contact@redpinequant.com").strip()

    return {
        "request": request,
        "global_prime_copy_url": global_prime_copy_url,
        "copy_link_configured": bool(global_prime_copy_url),
        "myfxbook_url": myfxbook_url or None,
        "fxblue_url": fxblue_url or None,
        "contact_email": contact_email or "contact@redpinequant.com",
    }


def is_fund_host(request: Request) -> bool:
    host = request.headers.get("host", "").split(":", 1)[0].lower()
    return host in {"rpqtfund.com", "www.rpqtfund.com"}


def load_latest_snapshot(fx_account_id: int = 1) -> dict | None:
    if not os.getenv("DATABASE_URL"):
        return None

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                select fx_account_id, asof_at, balance, equity, profit
                from fx_account_snapshots
                where fx_account_id = :fxid
                order by asof_at desc
                limit 1
                """
            ),
            {"fxid": fx_account_id},
        ).mappings().first()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        db.close()


def render_rpq_portal_home(request: Request, fx_account_id: int = 1):
    context = public_context(request)
    context["snap"] = load_latest_snapshot(fx_account_id)
    return templates.TemplateResponse(request, "rpq_portal_home.html", context=context)


@app.get("/")
def home(request: Request, fx_account_id: int = 1):
    if is_fund_host(request):
        return render_rpq_portal_home(request, fx_account_id)
    return templates.TemplateResponse(request, "index.html", context=public_context(request))


@app.get("/fund")
def fund_page(request: Request):
    return templates.TemplateResponse(request, "fund.html", context=public_context(request))


@app.get("/copy")
def copy_page(request: Request):
    return templates.TemplateResponse(request, "copy.html", context=public_context(request))


@app.get("/risk")
def risk_page(request: Request):
    return templates.TemplateResponse(request, "risk.html", context=public_context(request))


@app.get("/faq")
def faq_page(request: Request):
    return templates.TemplateResponse(request, "faq.html", context=public_context(request))


@app.head("/")
def home_head():
    return Response(status_code=200, media_type="text/html")
