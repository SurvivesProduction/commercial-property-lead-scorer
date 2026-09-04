-- 001_init_schema.sql
-- Initial schema for leadscorer: properties + permits.
-- Written to be safe to rerun (idempotent): every statement uses an
-- `if not exists` guard.
--
-- Lives in its own migration namespace, separate from bidscraper's
-- (Tool 1) migrations -- both packages can run their own migrations
-- against the same shared Postgres database without colliding, since
-- table names don't overlap. See this repo's ARCHITECTURE.md (once
-- written in the full/paid overlay) for why Tool 2 reuses Tool 1's
-- Supabase project instead of provisioning a new one.

create extension if not exists pgcrypto;

create table if not exists properties (
    id uuid primary key default gen_random_uuid(),
    client_id text not null,
    source text not null,
    parcel_id text not null,
    address text not null,
    city text,
    county text,
    state text,
    zip_code text,
    year_built int,
    year_renovated int,
    square_footage int,
    property_use text,
    owner_name text,
    owner_mailing_address text,
    raw_data jsonb,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (client_id, source, parcel_id)
);

create index if not exists idx_properties_client_parcel
    on properties (client_id, parcel_id);

create index if not exists idx_properties_client_county
    on properties (client_id, county);

create table if not exists permits (
    id uuid primary key default gen_random_uuid(),
    client_id text not null,
    source text not null,
    permit_number text not null,
    parcel_id text,
    address text,
    permit_type text,
    description text,
    issued_date date,
    status text,
    raw_data jsonb,
    first_seen_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (client_id, source, permit_number)
);

create index if not exists idx_permits_client_parcel
    on permits (client_id, parcel_id);

create index if not exists idx_permits_client_address
    on permits (client_id, address);
