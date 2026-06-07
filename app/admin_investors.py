from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, text

from passlib.hash import argon2

from .db import get_db
from .auth import require_admin
from .models import Investor, AuditLog

router = APIRouter(prefix="/admin", tags=["admin"])


def audit(
    db: Session,
    admin_id: int,
    action: str,
    target_type: str,
    target_id: int,
    diff: dict | None = None,
):
    db.add(
        AuditLog(
            actor_admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            diff=diff,
        )
    )


@router.get("/investors", response_class=HTMLResponse)
def investors_page(
    request: Request,
    q: str | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    stmt = select(Investor)

    if not include_inactive:
        stmt = stmt.where(Investor.is_active.is_(True))

    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Investor.name.ilike(like),
                Investor.email.ilike(like),
                Investor.username.ilike(like),
            )
        )

    investors = (
        db.execute(stmt.order_by(Investor.id.desc()).limit(200))
        .scalars()
        .all()
    )

    return request.app.state.templates.TemplateResponse(
        "admin/investors_list.html",
        {
            "request": request,
            "investors": investors,
            "q": q or "",
            "include_inactive": include_inactive,
        },
    )


@router.post("/investors", response_class=HTMLResponse)
def create_investor(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    memo: str | None = Form(None),
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    name = (name or "").strip()
    email = (email or "").strip()

    if not name:
        raise HTTPException(status_code=400, detail="name required")
    if not email:
        raise HTTPException(status_code=400, detail="email required")

    # email unique enforced by DB constraint, but we fail fast for better UX
    exists = db.execute(
        select(Investor.id).where(Investor.email == email).limit(1)
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="email already exists")

    inv = Investor(
        name=name,
        email=email,
        memo=memo,
        is_active=True,
    )
    db.add(inv)
    audit(
        db=db,
        admin_id=admin_id,
        action="INVESTOR_CREATE",
        target_type="investor",
        target_id=0,  # filled after flush
        diff={"name": name, "email": email},
    )
    db.flush()  # allocate inv.id
    # update audit target_id properly
    audit(
        db=db,
        admin_id=admin_id,
        action="INVESTOR_CREATE_ID",
        target_type="investor",
        target_id=int(inv.id),
        diff=None,
    )

    db.commit()
    db.refresh(inv)

    # return one row snippet (htmx afterbegin)
    return request.app.state.templates.TemplateResponse(
        "admin/investor_row.html",
        {"request": request, "inv": inv},
    )


@router.delete("/investors/{investor_id}", response_class=HTMLResponse)
def deactivate_investor(
    request: Request,
    investor_id: int,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    inv = db.get(Investor, int(investor_id))
    if not inv:
        raise HTTPException(status_code=404, detail="Not found")

    inv.is_active = False
    db.add(inv)

    audit(
        db=db,
        admin_id=admin_id,
        action="INVESTOR_DEACTIVATE",
        target_type="investor",
        target_id=int(inv.id),
        diff=None,
    )

    db.commit()
    db.refresh(inv)

    return request.app.state.templates.TemplateResponse(
        "admin/investor_row.html",
        {"request": request, "inv": inv},
    )


@router.post("/investors/{investor_id}/restore", response_class=HTMLResponse)
def restore_investor(
    request: Request,
    investor_id: int,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    inv = db.get(Investor, int(investor_id))
    if not inv:
        raise HTTPException(status_code=404, detail="Not found")

    inv.is_active = True
    db.add(inv)

    audit(
        db=db,
        admin_id=admin_id,
        action="INVESTOR_RESTORE",
        target_type="investor",
        target_id=int(inv.id),
        diff=None,
    )

    db.commit()
    db.refresh(inv)

    return request.app.state.templates.TemplateResponse(
        "admin/investor_row.html",
        {"request": request, "inv": inv},
    )


@router.get("/investors/{investor_id}/credentials", response_class=HTMLResponse)
def credentials_page(
    request: Request,
    investor_id: int,
    msg: str = "",
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    inv = db.get(Investor, int(investor_id))
    if not inv:
        raise HTTPException(status_code=404, detail="Not found")

    return request.app.state.templates.TemplateResponse(
        "admin/credentials.html",
        {"request": request, "inv": inv, "msg": msg},
    )


@router.head("/investors/{investor_id}/credentials")
def credentials_head(investor_id: int):
    return


@router.post("/investors/{investor_id}/credentials")
def credentials_save(
    request: Request,
    investor_id: int,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    inv = db.get(Investor, int(investor_id))
    if not inv:
        raise HTTPException(status_code=404, detail="Not found")

    username = (username or "").strip()

    # basic validation
    if len(username) < 3:
        return RedirectResponse(
            url=f"/admin/investors/{inv.id}/credentials?msg=bad",
            status_code=303,
        )
    if len(password) < 6:
        return RedirectResponse(
            url=f"/admin/investors/{inv.id}/credentials?msg=bad",
            status_code=303,
        )

    # enforce unique username (matches your partial unique index)
    exists = db.execute(
        text("SELECT 1 FROM investors WHERE username=:u AND id<>:id LIMIT 1"),
        {"u": username, "id": int(inv.id)},
    ).first()
    if exists:
        return RedirectResponse(
            url=f"/admin/investors/{inv.id}/credentials?msg=dup",
            status_code=303,
        )

    inv.username = username
    inv.password_hash = argon2.hash(password)

    audit(
        db=db,
        admin_id=admin_id,
        action="INVESTOR_SET_CREDENTIALS",
        target_type="investor",
        target_id=int(inv.id),
        diff={"username": username},
    )

    db.commit()
    db.refresh(inv)
    return request.app.state.templates.TemplateResponse(
        "admin/credentials.html",
        {
            "request": request,
            "inv": inv,
            "msg": "ok",
            "saved_username": username,
            "temp_password": password,
        },
    )
