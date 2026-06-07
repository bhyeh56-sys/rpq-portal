# app/main.py
import os

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import admin_dashboard
from .admin_cashflows import router as admin_cashflows_router
from .admin_investors import router as admin_investors_router
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


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", public_context(request))


@app.get("/copy")
def copy_page(request: Request):
    return templates.TemplateResponse("copy.html", public_context(request))


@app.get("/risk")
def risk_page(request: Request):
    return templates.TemplateResponse("risk.html", public_context(request))


@app.get("/faq")
def faq_page(request: Request):
    return templates.TemplateResponse("faq.html", public_context(request))


@app.head("/")
def home_head():
    return
