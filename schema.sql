CREATE TABLE IF NOT EXISTS funds (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    base_ccy VARCHAR NOT NULL DEFAULT 'USD',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS investors (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    email VARCHAR NOT NULL UNIQUE,
    memo TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    deleted_at TIMESTAMPTZ,
    deleted_by BIGINT,
    deleted_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS investor_positions (
    fund_id BIGINT NOT NULL REFERENCES funds(id),
    investor_id BIGINT NOT NULL REFERENCES investors(id),
    units NUMERIC(30, 10) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (fund_id, investor_id)
);

CREATE TABLE IF NOT EXISTS unit_price_points (
    id BIGSERIAL PRIMARY KEY,
    fund_id BIGINT NOT NULL REFERENCES funds(id),
    asof_at TIMESTAMPTZ NOT NULL,
    price NUMERIC(30, 10) NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT unit_price_points_fund_id_asof_at_key UNIQUE (fund_id, asof_at)
);

CREATE INDEX IF NOT EXISTS ix_unit_price_points_fund_asof_desc
    ON unit_price_points (fund_id, asof_at);

CREATE TABLE IF NOT EXISTS fx_accounts (
    id BIGSERIAL PRIMARY KEY,
    fund_id BIGINT NOT NULL REFERENCES funds(id),
    broker VARCHAR NOT NULL DEFAULT 'MT5',
    account_login VARCHAR NOT NULL,
    account_server VARCHAR,
    account_ccy VARCHAR NOT NULL DEFAULT 'USD',
    is_active BOOLEAN NOT NULL DEFAULT true,
    secret VARCHAR NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_fx_accounts_fund_active
    ON fx_accounts (fund_id, is_active);

CREATE TABLE IF NOT EXISTS fx_account_snapshots (
    id BIGSERIAL PRIMARY KEY,
    fx_account_id BIGINT NOT NULL REFERENCES fx_accounts(id),
    asof_at TIMESTAMPTZ NOT NULL,
    balance NUMERIC(30, 10) NOT NULL,
    equity NUMERIC(30, 10) NOT NULL,
    margin NUMERIC(30, 10),
    free_margin NUMERIC(30, 10),
    profit NUMERIC(30, 10),
    raw JSON,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT fx_account_snapshots_fx_account_id_asof_at_key UNIQUE (fx_account_id, asof_at)
);

CREATE INDEX IF NOT EXISTS ix_fx_account_snapshots_fxid_asof_desc
    ON fx_account_snapshots (fx_account_id, asof_at);

CREATE TABLE IF NOT EXISTS cashflow_requests (
    id BIGSERIAL PRIMARY KEY,
    fund_id BIGINT NOT NULL REFERENCES funds(id),
    investor_id BIGINT NOT NULL REFERENCES investors(id),
    kind VARCHAR NOT NULL,
    currency VARCHAR NOT NULL DEFAULT 'USD',
    amount NUMERIC(30, 10) NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'PENDING',
    note TEXT,
    created_by_admin BIGINT,
    confirmed_by_admin BIGINT,
    cancelled_by_admin BIGINT,
    requested_at TIMESTAMPTZ DEFAULT now(),
    confirmed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    id BIGSERIAL PRIMARY KEY,
    fund_id BIGINT NOT NULL REFERENCES funds(id),
    investor_id BIGINT NOT NULL REFERENCES investors(id),
    source_type VARCHAR NOT NULL,
    source_id BIGINT NOT NULL,
    account VARCHAR NOT NULL,
    currency VARCHAR NOT NULL DEFAULT 'USD',
    amount NUMERIC(30, 10) NOT NULL,
    unit_price NUMERIC(30, 10),
    memo TEXT,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_ledger_entries_source
    ON ledger_entries (source_type, source_id);

CREATE INDEX IF NOT EXISTS ix_ledger_entries_investor_occurred
    ON ledger_entries (fund_id, investor_id, occurred_at);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    actor_admin_id BIGINT NOT NULL,
    action VARCHAR NOT NULL,
    target_type VARCHAR NOT NULL,
    target_id BIGINT NOT NULL,
    diff JSON,
    created_at TIMESTAMPTZ DEFAULT now()
);
