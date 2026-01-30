from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = "postgresql://rpq_user:rpq_pass@127.0.0.1:5432/rpq_db"

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
with latest_nav as (
  select fund_id, unit_nav, nav_time
  from nav_snapshots
  where fund_id = %(fund_id)s
  order by nav_time desc
  limit 1
),
flows as (
  select
    fund_id,
    investor_id,
    coalesce(sum(amount) filter (where entry_type in ('DEPOSIT','WITHDRAWAL')), 0) as net_flow
  from ledger_entries
  where fund_id = %(fund_id)s
    and investor_id = %(investor_id)s
  group by fund_id, investor_id
)
select
  iu.fund_id,
  iu.investor_id,
  iu.units,
  ln.unit_nav as latest_unit_nav,
  ln.nav_time as latest_nav_time,
  (iu.units * ln.unit_nav) as valuation,
  coalesce(f.net_flow, 0) as net_flow,
  (iu.units * ln.unit_nav) - coalesce(f.net_flow, 0) as pnl,
  case
    when coalesce(f.net_flow, 0) > 0
    then ((iu.units * ln.unit_nav) - coalesce(f.net_flow, 0)) / coalesce(f.net_flow, 0)
    else null
  end as return_ratio
from investor_units iu
join latest_nav ln on ln.fund_id = iu.fund_id
left join flows f on f.fund_id = iu.fund_id and f.investor_id = iu.investor_id
where iu.fund_id = %(fund_id)s
  and iu.investor_id = %(investor_id)s;
"""

SQL_PORTAL_LEDGER = """
select
  id, occurred_at, entry_type, ccy, amount, memo
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
        # common causes: no nav yet OR no investor_units row yet
        raise HTTPException(
            status_code=404,
            detail="Summary not available (missing NAV snapshot or investor units).",
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
