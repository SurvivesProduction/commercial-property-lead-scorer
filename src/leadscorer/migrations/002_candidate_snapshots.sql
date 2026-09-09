-- 002_candidate_snapshots.sql
-- Novelty-gate support: candidate_snapshots + candidate_dropouts.
-- Written to be safe to rerun (idempotent): every statement uses an
-- `if not exists` guard.
--
-- The RANKING step itself is stateless (rank_candidates recomputes the
-- full ranked list fresh from `properties`/`permits` every run, nothing
-- about a candidate's rank/score is stored between runs) even though
-- `properties`/`permits` themselves ARE persisted (via upsert_property/
-- upsert_permit) -- these two tables are the minimal ADDITIONAL state
-- needed to answer "which qualifying candidates are new since the last
-- run," a question the persisted property/permit rows alone can't answer
-- (they don't record which ones scored high enough to qualify on any
-- given past run). One row per (client, run, parcel) for whatever
-- qualified, plus a companion table logging whatever dropped off, so
-- that history is retained even though the digest's primary content only
-- surfaces new candidates for now (see leadscorer_full's ARCHITECTURE.md
-- for the reasoning).
--
-- candidate_snapshots always means "what qualified as of this run" --
-- no status column, so a query for "the latest snapshot" never needs a
-- WHERE filter beyond client_id/run_at. candidate_dropouts is a pure
-- historical event log: one row per candidate per run in which it
-- disappeared from the qualifying set, carrying its last-known fields
-- (there's no "current" data for a dropped candidate by definition).

create table if not exists candidate_snapshots (
    id uuid primary key default gen_random_uuid(),
    client_id text not null,
    run_at timestamptz not null,
    parcel_id text not null,
    address text not null,
    score numeric not null,
    effective_year int,
    square_footage int,
    created_at timestamptz not null default now(),
    unique (client_id, run_at, parcel_id)
);

create index if not exists idx_candidate_snapshots_client_run_at
    on candidate_snapshots (client_id, run_at desc);

create table if not exists candidate_dropouts (
    id uuid primary key default gen_random_uuid(),
    client_id text not null,
    run_at timestamptz not null,
    parcel_id text not null,
    address text not null,
    last_score numeric,
    last_effective_year int,
    last_square_footage int,
    created_at timestamptz not null default now(),
    unique (client_id, run_at, parcel_id)
);

create index if not exists idx_candidate_dropouts_client_run_at
    on candidate_dropouts (client_id, run_at desc);
