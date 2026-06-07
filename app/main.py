# app/main.py
import os

from fastapi import Depends, FastAPI, Request
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


@app.get("/")
def home(request: Request, fx_account_id: int = 1, db: Session = Depends(get_db)):
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

    snap = dict(row) if row else None
    return templates.TemplateResponse(request, "index.html", {"snap": snap})


@app.head("/")
def home_head():
    return
