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

## Notes

- Admin auth is still MVP-only: missing `X-Admin-Id` defaults to `1`.
- Investor portal auth is header-based: send `X-Investor-Id`.
- `.env` is ignored by git. Keep local passwords and secrets out of the repository.
