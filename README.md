# RPQ Portal

Local FastAPI/PostgreSQL MVP for admin cashflow handling and investor portal views.

## Requirements

- Python 3.10+
- PostgreSQL client/server tools (`psql`, `createdb`, `createuser`)

The current Codex environment does not have PostgreSQL tools installed, so DB setup commands below are prepared but not executed here.

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

For local test development:

```bash
.venv/bin/pip install -r requirements-dev.txt
```

## Database

Create a local PostgreSQL user and database. Replace the password with a local-only value.

```bash
sudo -u postgres createuser -P rpq_user
sudo -u postgres createdb -O rpq_user rpq_db
```

Export the app database URL:

```bash
export DATABASE_URL='postgresql+psycopg://rpq_user:<password>@127.0.0.1:5432/rpq_db'
```

Initialize schema and seed MVP data:

```bash
export PSQL_DATABASE_URL='postgresql://rpq_user:<password>@127.0.0.1:5432/rpq_db'
psql "$PSQL_DATABASE_URL" -f schema.sql
psql "$PSQL_DATABASE_URL" -f scripts/seed.sql
```

The same reset can be automated with:

```bash
export RPQ_ADMIN_DATABASE_URL='postgresql://postgres:<password>@127.0.0.1:5432/postgres'
export PSQL_DATABASE_URL='postgresql://rpq_user:<password>@127.0.0.1:5432/rpq_db'
export DATABASE_URL='postgresql+psycopg://rpq_user:<password>@127.0.0.1:5432/rpq_db'
scripts/reset_local_db.sh
```

If the system PostgreSQL service is unavailable in a sandbox, a user-owned temporary cluster can be used instead:

```bash
/usr/lib/postgresql/14/bin/initdb -D /tmp/rpq_pg -A trust
/usr/lib/postgresql/14/bin/pg_ctl -D /tmp/rpq_pg -l /tmp/rpq_pg.log \
  -o "-h 127.0.0.1 -p 55432 -c unix_socket_directories=/tmp" start
export DATABASE_URL='postgresql+psycopg://rpq_user:rpq_pass@127.0.0.1:55432/rpq_db'
export PSQL_DATABASE_URL='postgresql://rpq_user:rpq_pass@127.0.0.1:55432/rpq_db'
/usr/lib/postgresql/14/bin/psql -h 127.0.0.1 -p 55432 -U "$USER" -d postgres \
  -c "CREATE ROLE rpq_user LOGIN PASSWORD 'rpq_pass';" \
  -c "CREATE DATABASE rpq_db OWNER rpq_user;"
```

Seed data creates:

- fund `id=1`
- investor `id=1`
- position of `100` units
- unit price of `10`
- one confirmed deposit cashflow
- two ledger rows (`CASH`, `UNITS`)

## Run

```bash
.venv/bin/uvicorn app.main:app --reload
```

The single app entrypoint is `app.main:app`.

## Smoke Tests

```bash
curl -i http://127.0.0.1:8000/health
curl -i http://127.0.0.1:8000/admin/investors
curl -i http://127.0.0.1:8000/admin/cashflows
curl -i http://127.0.0.1:8000/admin/unit-price
curl -i "http://127.0.0.1:8000/portal/me/summary?fund_id=1" -H "X-Investor-Id: 1"
curl -i "http://127.0.0.1:8000/portal/me/ledger?fund_id=1" -H "X-Investor-Id: 1"
```

## Pytest

Run import and route tests:

```bash
.venv/bin/pytest
```

Run live HTTP smoke tests against a running local server:

```bash
export RPQ_TEST_BASE_URL='http://127.0.0.1:8000'
.venv/bin/pytest
```

Live tests expect the seeded `fund_id=1` and `X-Investor-Id: 1` data.

## Domain Rules

- `unit_price_points` stores fund unit prices over time.
- `investor_positions.units` stores the current units per fund/investor.
- `cashflow_requests` stores admin-created deposit/withdraw requests.
- Confirming a cashflow creates two `ledger_entries`: one `CASH` row and one `UNITS` row.
- Deposit amounts are positive; withdraw confirmations create negative `CASH` and `UNITS` ledger amounts.
- Portal net flow sums only `ledger_entries.account = 'CASH'`.

Expected portal summary with seed data:

```json
{
  "fund_id": 1,
  "investor_id": 1,
  "units": 100.0,
  "latest_unit_nav": 10.0,
  "valuation": 1000.0,
  "net_flow": 1000.0,
  "pnl": 0.0,
  "return_ratio": 0.0
}
```

## Browser URLs

- http://127.0.0.1:8000/admin/investors
- http://127.0.0.1:8000/admin/cashflows
- http://127.0.0.1:8000/admin/unit-price
- http://127.0.0.1:8000/docs

## End User Test Flow

1. Open `/admin/investors`.
2. Create an investor, then use the row action to deactivate and restore it.
3. Open `/admin/unit-price`.
4. Add a newer unit price for fund `1`, for example `2026-02-01T00:00:00+09:00` at price `12`.
5. Open `/admin/cashflows`.
6. Create a `DEPOSIT` request for investor `1`, then confirm it.
7. Create a `WITHDRAW` request and cancel it.
8. Create another `WITHDRAW` request and confirm it.
9. Call `/portal/me/summary?fund_id=1` with `X-Investor-Id: 1` and confirm valuation/net flow changed.
10. Call `/portal/me/ledger?fund_id=1` with `X-Investor-Id: 1` and confirm the new `CASH` and `UNITS` ledger rows appear.
11. Open `/docs` and confirm admin, portal, health, and FX routes are listed.

## Notes

- Admin auth is still MVP-only: missing `X-Admin-Id` defaults to `1`.
- Investor portal auth is header-based: send `X-Investor-Id`.
- `.env` is ignored by git. Keep local passwords and secrets out of the repository.
