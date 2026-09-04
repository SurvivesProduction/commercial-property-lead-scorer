"""Generic Postgres client wrapper for leadscorer.

Handles connecting to Postgres via standard environment variables and the
upsert logic shared by every scraper. Nothing in this module is specific
to any hosting provider (e.g. Supabase) or client -- that kind of wiring
belongs in a downstream "full" deployment package.

Deliberately simpler dedup than Tool 1's `bidscraper.db.client`: that
module needs a 3-tier fuzzy-match strategy because government bid-award
portals often don't expose a reliable native record id, and the same
award can drift in formatting across re-scrapes with no stable key to
anchor on. Property assessment rolls and permit systems are built around
a genuine stable identifier instead -- a parcel/account number and a
permit number, respectively -- so a plain exact-match upsert on that
identifier is the correct dedup strategy here, not a simplification that
skips real work. If a real source turns out not to expose a reliable
native id, that's a reason to revisit this (potentially borrowing Tool
1's fuzzy-match approach for that source specifically), not to force a
hash-based key where a real one should exist.
"""
from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from leadscorer.config import DatabaseConfig
from leadscorer.normalize.schema import PermitRecord, PropertyRecord


def get_connection(dsn: str | None = None) -> psycopg.Connection:
    """Open a Postgres connection.

    Uses `dsn` if given, otherwise resolves connection settings from the
    environment via `DatabaseConfig.from_env()`.
    """
    resolved_dsn = dsn or DatabaseConfig.from_env().dsn
    return psycopg.connect(resolved_dsn)


def _property_content_params(record: PropertyRecord) -> dict[str, Any]:
    return {
        "address": record.address,
        "city": record.city,
        "county": record.county,
        "state": record.state,
        "zip_code": record.zip_code,
        "year_built": record.year_built,
        "year_renovated": record.year_renovated,
        "square_footage": record.square_footage,
        "property_use": record.property_use,
        "owner_name": record.owner_name,
        "owner_mailing_address": record.owner_mailing_address,
        "raw_data": Jsonb(record.raw_data),
    }


def upsert_property(conn: psycopg.Connection, record: PropertyRecord) -> dict[str, Any]:
    """Insert or update a property record, keyed on (client_id, source, parcel_id).

    An exact match refreshes the row's content and bumps `last_seen_at`;
    no match inserts a new row (`first_seen_at` set by the column
    default). See the module docstring for why this doesn't need Tool 1's
    fuzzy-match tiers.
    """
    query = """
        insert into properties (
            client_id, source, parcel_id, address, city, county, state,
            zip_code, year_built, year_renovated, square_footage,
            property_use, owner_name, owner_mailing_address, raw_data
        ) values (
            %(client_id)s, %(source)s, %(parcel_id)s, %(address)s, %(city)s,
            %(county)s, %(state)s, %(zip_code)s, %(year_built)s,
            %(year_renovated)s, %(square_footage)s, %(property_use)s,
            %(owner_name)s, %(owner_mailing_address)s, %(raw_data)s
        )
        on conflict (client_id, source, parcel_id) do update set
            address = excluded.address,
            city = excluded.city,
            county = excluded.county,
            state = excluded.state,
            zip_code = excluded.zip_code,
            year_built = excluded.year_built,
            year_renovated = excluded.year_renovated,
            square_footage = excluded.square_footage,
            property_use = excluded.property_use,
            owner_name = excluded.owner_name,
            owner_mailing_address = excluded.owner_mailing_address,
            raw_data = excluded.raw_data,
            last_seen_at = now(),
            updated_at = now()
        returning *
    """
    params = {
        "client_id": record.client_id,
        "source": record.source,
        "parcel_id": record.parcel_id,
        **_property_content_params(record),
    }
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row


def _permit_content_params(record: PermitRecord) -> dict[str, Any]:
    return {
        "parcel_id": record.parcel_id,
        "address": record.address,
        "permit_type": record.permit_type,
        "description": record.description,
        "issued_date": record.issued_date,
        "status": record.status,
        "raw_data": Jsonb(record.raw_data),
    }


def upsert_permit(conn: psycopg.Connection, record: PermitRecord) -> dict[str, Any]:
    """Insert or update a permit record, keyed on (client_id, source, permit_number)."""
    query = """
        insert into permits (
            client_id, source, permit_number, parcel_id, address,
            permit_type, description, issued_date, status, raw_data
        ) values (
            %(client_id)s, %(source)s, %(permit_number)s, %(parcel_id)s,
            %(address)s, %(permit_type)s, %(description)s, %(issued_date)s,
            %(status)s, %(raw_data)s
        )
        on conflict (client_id, source, permit_number) do update set
            parcel_id = excluded.parcel_id,
            address = excluded.address,
            permit_type = excluded.permit_type,
            description = excluded.description,
            issued_date = excluded.issued_date,
            status = excluded.status,
            raw_data = excluded.raw_data,
            last_seen_at = now(),
            updated_at = now()
        returning *
    """
    params = {
        "client_id": record.client_id,
        "source": record.source,
        "permit_number": record.permit_number,
        **_permit_content_params(record),
    }
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        row = cur.fetchone()
    conn.commit()
    assert row is not None
    return row


def properties_for_client(conn: psycopg.Connection, client_id: str) -> list[dict[str, Any]]:
    """Return every property record for `client_id`."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("select * from properties where client_id = %(client_id)s", {"client_id": client_id})
        return cur.fetchall()


def permits_for_client(conn: psycopg.Connection, client_id: str) -> list[dict[str, Any]]:
    """Return every permit record for `client_id`."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("select * from permits where client_id = %(client_id)s", {"client_id": client_id})
        return cur.fetchall()
