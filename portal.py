from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
import psycopg
from psycopg.rows import dict_row

from app.db import DATABASE_URL as APP_DATABASE_URL


DATABASE_URL = APP_DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)

router = APIRouter(prefix="/portal", tags=["portal"])


# --------- DB Dependency (psycopg3) ---------
def get_conn():
    # simple per-request connection (MVP)
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def get_investor_id(x_investor_id: Optional[str] = Header(default=None)) -> int:
    """
    MVP auth: pass investor id in header X-Investor-Id
    """
    if not x_investor_id:
        raise HTTPException(status_code=401, detail="Missing X-Investor-Id header")
    try:
        return int(x_investor_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Investor-Id header")


# --------- Schemas ---------
class PortalSummaryOut(BaseModel):
    fund_id: int
    investor_id: int
    units: float
    latest_unit_nav: float
    latest_nav_time: datetime
    valuation: float
    net_flow: float
    pnl: float
    return_ratio: Optional[float] = None


class LedgerRowOut(BaseModel):
    id: int
    occurred_at: datetime
    entry_type: str
    ccy: str
    amount: float
    memo: Optional[str] = None


class LedgerListOut(BaseModel):
    fund_id: int
    investor_id: int
    limit: int
    offset: int
    rows: List[LedgerRowOut]


# --------- SQL ---------
SQL_PORTAL_SUMMARY = """
with latest_price as (
  select fund_id, price, asof_at
  from unit_price_points
  where fund_id = %(fund_id)s
  order by asof_at desc
  limit 1
),
flows as (
  select
    fund_id,
    investor_id,
    coalesce(sum(amount) filter (where account = 'CASH'), 0) as net_flow
  from ledger_entries
  where fund_id = %(fund_id)s
    and investor_id = %(investor_id)s
  group by fund_id, investor_id
)
select
  ip.fund_id,
  ip.investor_id,
  ip.units,
  lp.price as latest_unit_nav,
  lp.asof_at as latest_nav_time,
  (ip.units * lp.price) as valuation,
  coalesce(f.net_flow, 0) as net_flow,
  (ip.units * lp.price) - coalesce(f.net_flow, 0) as pnl,
  case
    when coalesce(f.net_flow, 0) > 0
    then ((ip.units * lp.price) - coalesce(f.net_flow, 0)) / coalesce(f.net_flow, 0)
    else null
  end as return_ratio
from investor_positions ip
join latest_price lp on lp.fund_id = ip.fund_id
left join flows f on f.fund_id = ip.fund_id and f.investor_id = ip.investor_id
where ip.fund_id = %(fund_id)s
  and ip.investor_id = %(investor_id)s;
"""

SQL_PORTAL_LEDGER = """
select
  id,
  occurred_at,
  account as entry_type,
  currency as ccy,
  amount,
  memo
from ledger_entries
where fund_id = %(fund_id)s
  and investor_id = %(investor_id)s
order by occurred_at desc, id desc
limit %(limit)s offset %(offset)s;
"""


# --------- Endpoints ---------
@router.get("/me/summary", response_model=PortalSummaryOut)
def me_summary(
    fund_id: int = Query(..., ge=1),
    investor_id: int = Depends(get_investor_id),
    conn=Depends(get_conn),
):
    with conn.cursor() as cur:
        cur.execute(SQL_PORTAL_SUMMARY, {"fund_id": fund_id, "investor_id": investor_id})
        row = cur.fetchone()

    if not row:
        # common causes: no unit price yet OR no investor position row yet
        raise HTTPException(
            status_code=404,
            detail="Summary not available (missing unit price or investor position).",
        )

    return PortalSummaryOut(**row)


@router.get("/me/ledger", response_model=LedgerListOut)
def me_ledger(
    fund_id: int = Query(..., ge=1),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    investor_id: int = Depends(get_investor_id),
    conn=Depends(get_conn),
):
    with conn.cursor() as cur:
        cur.execute(
            SQL_PORTAL_LEDGER,
            {"fund_id": fund_id, "investor_id": investor_id, "limit": limit, "offset": offset},
        )
        rows = cur.fetchall()

    return LedgerListOut(
        fund_id=fund_id,
        investor_id=investor_id,
        limit=limit,
        offset=offset,
        rows=[LedgerRowOut(**r) for r in rows],
    )
