# app/main.py
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from .admin_investors import router as admin_investors_router
from .admin_cashflows import router as admin_cashflows_router
from .fx_webhook import router as fx_router

app = FastAPI(title="RPQ Portal")

templates = Jinja2Templates(directory="templates")
app.state.templates = templates

app.include_router(admin_investors_router)
app.include_router(admin_cashflows_router)
app.include_router(fx_router)

@app.get("/health")
def health():
    return {"ok": True}
