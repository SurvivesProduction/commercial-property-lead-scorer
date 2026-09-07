-- 003_occupancy_checks.sql
-- Occupancy-check state: one row per (client, parcel) recording the most
-- recent Trader's License occupancy check result and when it happened.
-- Written to be safe to rerun (idempotent): every statement uses an
-- `if not exists` guard.
--
-- This is what makes "only check newly-qualifying candidates, plus a
-- periodic full refresh" possible: without persisted state, every run
-- would have no way to know which candidates were already checked
-- recently vs. never checked at all. One row per parcel (not per run,
-- unlike candidate_snapshots) -- each check overwrites the prior result,
-- since only the CURRENT occupancy status matters, not its history.
--
-- Lives in the public `leadscorer` package, not the full/paid overlay,
-- same reasoning as `leadscorer.snapshot`: "only check what's new or
-- stale" is a generic scoping policy, not something specific to Maryland
-- or the Trader's License source. The source-specific fetcher
-- (`leadscorer_full.scrapers.trader_license.AACOTraderLicenseFetcher`)
-- stays in the full/paid overlay; this table just persists whatever
-- result it produced.

create table if not exists occupancy_checks (
    id uuid primary key default gen_random_uuid(),
    client_id text not null,
    parcel_id text not null,
    address text not null,
    active_trader_license boolean not null default false,
    checked_at timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (client_id, parcel_id)
);

create index if not exists idx_occupancy_checks_client_parcel
    on occupancy_checks (client_id, parcel_id);
