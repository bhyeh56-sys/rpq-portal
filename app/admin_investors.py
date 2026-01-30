from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, func, text

from .db import get_db
from .auth import require_admin
from .models import (
    Investor,
    AuditLog,
)

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
    # 중복 이메일 방지
    exists = db.execute(
        select(func.count())
        .select_from(Investor)
        .where(Investor.email == email)
    ).scalar_one()

    if exists:
        raise HTTPException(status_code=400, detail="Email already exists")

    # 1) 투자자 생성
    investor = Investor(name=name, email=email, memo=memo)
    db.add(investor)
    db.flush()  # investor.id 확보

    # 2) 모든 fund에 대해 investor_positions 자동 생성 (DB 한방 쿼리)
    #    - funds 테이블에서 fund_id들을 뽑아서
    #    - 새 investor_id로 investor_positions를 생성
    #    - 중복은 ON CONFLICT DO NOTHING으로 무시
    db.execute(
        text("""
            INSERT INTO investor_positions (fund_id, investor_id, units)
            SELECT f.id, :investor_id, 0
            FROM funds f
            ON CONFLICT (fund_id, investor_id) DO NOTHING
        """),
        {"investor_id": investor.id},
    )

    # 3) audit log
    audit(
        db=db,
        admin_id=admin_id,
        action="INVESTOR_CREATE",
        target_type="investor",
        target_id=investor.id,
        diff={"name": name, "email": email},
    )

    db.commit()
    db.refresh(investor)

    return request.app.state.templates.TemplateResponse(
        "admin/investor_row.html",
        {"request": request, "inv": investor},
    )


@router.post("/investors/{investor_id}/backfill_positions", response_class=HTMLResponse)
def backfill_positions_for_investor(
    request: Request,
    investor_id: int,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    investor = db.get(Investor, investor_id)
    if not investor:
        raise HTTPException(status_code=404, detail="Not found")

    db.execute(
        text("""
            INSERT INTO investor_positions (fund_id, investor_id, units)
            SELECT f.id, :investor_id, 0
            FROM funds f
            ON CONFLICT (fund_id, investor_id) DO NOTHING
        """),
        {"investor_id": investor.id},
    )

    audit(
        db=db,
        admin_id=admin_id,
        action="INVESTOR_POSITIONS_BACKFILL",
        target_type="investor",
        target_id=investor.id,
    )

    db.commit()
    db.refresh(investor)

    return request.app.state.templates.TemplateResponse(
        "admin/investor_row.html",
        {"request": request, "inv": investor},
    )


@router.delete("/investors/{investor_id}", response_class=HTMLResponse)
def deactivate_investor(
    request: Request,
    investor_id: int,
    reason: str | None = None,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    investor = db.get(Investor, investor_id)
    if not investor:
        raise HTTPException(status_code=404, detail="Not found")

    if investor.is_active:
        investor.is_active = False
        investor.deleted_at = func.now()
        investor.deleted_by = admin_id
        investor.deleted_reason = reason

        audit(
            db=db,
            admin_id=admin_id,
            action="INVESTOR_DEACTIVATE",
            target_type="investor",
            target_id=investor.id,
            diff={"reason": reason},
        )

        db.commit()
        db.refresh(investor)

    return request.app.state.templates.TemplateResponse(
        "admin/investor_row.html",
        {"request": request, "inv": investor},
    )


@router.post("/investors/{investor_id}/restore", response_class=HTMLResponse)
def restore_investor(
    request: Request,
    investor_id: int,
    db: Session = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    investor = db.get(Investor, investor_id)
    if not investor:
        raise HTTPException(status_code=404, detail="Not found")

    investor.is_active = True
    investor.deleted_at = None
    investor.deleted_by = None
    investor.deleted_reason = None

    audit(
        db=db,
        admin_id=admin_id,
        action="INVESTOR_RESTORE",
        target_type="investor",
        target_id=investor.id,
    )

    db.commit()
    db.refresh(investor)

    return request.app.state.templates.TemplateResponse(
        "admin/investor_row.html",
        {"request": request, "inv": investor},
    )
