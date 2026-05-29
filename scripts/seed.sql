INSERT INTO funds (id, name, base_ccy)
VALUES (1, 'RPQ Demo Fund', 'USD')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    base_ccy = EXCLUDED.base_ccy;

INSERT INTO investors (id, name, email, memo, is_active)
VALUES (1, 'Demo Investor', 'demo.investor@example.com', 'Local seed investor', true)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    email = EXCLUDED.email,
    memo = EXCLUDED.memo,
    is_active = EXCLUDED.is_active,
    deleted_at = NULL,
    deleted_by = NULL,
    deleted_reason = NULL;

INSERT INTO investor_positions (fund_id, investor_id, units)
VALUES (1, 1, 100.0000000000)
ON CONFLICT (fund_id, investor_id) DO UPDATE SET
    units = EXCLUDED.units,
    updated_at = now();

INSERT INTO unit_price_points (id, fund_id, asof_at, price, note)
VALUES (1, 1, '2026-01-01 00:00:00+00', 10.0000000000, 'Local seed unit price')
ON CONFLICT (fund_id, asof_at) DO UPDATE SET
    price = EXCLUDED.price,
    note = EXCLUDED.note;

INSERT INTO cashflow_requests (
    id,
    fund_id,
    investor_id,
    kind,
    currency,
    amount,
    status,
    note,
    created_by_admin,
    confirmed_by_admin,
    requested_at,
    confirmed_at
)
VALUES (
    1,
    1,
    1,
    'DEPOSIT',
    'USD',
    1000.0000000000,
    'CONFIRMED',
    'Local seed deposit',
    1,
    1,
    '2026-01-01 00:00:00+00',
    '2026-01-01 00:00:00+00'
)
ON CONFLICT (id) DO UPDATE SET
    fund_id = EXCLUDED.fund_id,
    investor_id = EXCLUDED.investor_id,
    kind = EXCLUDED.kind,
    currency = EXCLUDED.currency,
    amount = EXCLUDED.amount,
    status = EXCLUDED.status,
    note = EXCLUDED.note,
    created_by_admin = EXCLUDED.created_by_admin,
    confirmed_by_admin = EXCLUDED.confirmed_by_admin,
    requested_at = EXCLUDED.requested_at,
    confirmed_at = EXCLUDED.confirmed_at;

INSERT INTO ledger_entries (
    id,
    fund_id,
    investor_id,
    source_type,
    source_id,
    account,
    currency,
    amount,
    unit_price,
    memo,
    occurred_at
)
VALUES
    (
        1,
        1,
        1,
        'CASHFLOW_REQUEST',
        1,
        'CASH',
        'USD',
        1000.0000000000,
        10.0000000000,
        'Local seed deposit',
        '2026-01-01 00:00:00+00'
    ),
    (
        2,
        1,
        1,
        'CASHFLOW_REQUEST',
        1,
        'UNITS',
        'USD',
        100.0000000000,
        10.0000000000,
        'Local seed deposit',
        '2026-01-01 00:00:00+00'
    )
ON CONFLICT (id) DO UPDATE SET
    fund_id = EXCLUDED.fund_id,
    investor_id = EXCLUDED.investor_id,
    source_type = EXCLUDED.source_type,
    source_id = EXCLUDED.source_id,
    account = EXCLUDED.account,
    currency = EXCLUDED.currency,
    amount = EXCLUDED.amount,
    unit_price = EXCLUDED.unit_price,
    memo = EXCLUDED.memo,
    occurred_at = EXCLUDED.occurred_at;

SELECT setval(pg_get_serial_sequence('funds', 'id'), GREATEST(COALESCE((SELECT max(id) FROM funds), 1), 1), true);
SELECT setval(pg_get_serial_sequence('investors', 'id'), GREATEST(COALESCE((SELECT max(id) FROM investors), 1), 1), true);
SELECT setval(pg_get_serial_sequence('unit_price_points', 'id'), GREATEST(COALESCE((SELECT max(id) FROM unit_price_points), 1), 1), true);
SELECT setval(pg_get_serial_sequence('cashflow_requests', 'id'), GREATEST(COALESCE((SELECT max(id) FROM cashflow_requests), 1), 1), true);
SELECT setval(pg_get_serial_sequence('ledger_entries', 'id'), GREATEST(COALESCE((SELECT max(id) FROM ledger_entries), 1), 1), true);
