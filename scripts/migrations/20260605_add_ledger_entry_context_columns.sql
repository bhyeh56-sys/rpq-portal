-- Add context columns expected by the schema check.
-- Safe to run more than once. Existing rows are preserved.

alter table if exists public.ledger_entries
  add column if not exists fund_id bigint,
  add column if not exists investor_id bigint,
  add column if not exists currency text default 'USD';
