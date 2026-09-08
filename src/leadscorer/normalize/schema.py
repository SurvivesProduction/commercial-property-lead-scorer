"""The normalized output contracts every scraper must produce.

Two independent sources feed this tool -- property assessment records and
permit records -- so there are two schemas, not one, mirroring how
`bidscraper.normalize.schema.BidAward` is the single contract for Tool 1's
single source type. Both are linked at the scoring layer, not the
ingestion layer -- see `leadscorer.scoring.basic` for how.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PropertyRecord(BaseModel):
    """A normalized commercial property assessment record.

    `parcel_id` is required: unlike Tool 1's bid awards (which often lack
    a reliable native id and need fuzzy-match dedup), government property
    assessment rolls are built around a stable parcel/account identifier,
    so this schema assumes one exists and dedups on it directly -- see
    `leadscorer.db.client.upsert_property`. If a real source turns out not
    to expose one, that's a reason to revisit this assumption before
    wiring up that source, not to fake an id.

    `needs_review`/`review_reason` (added 2026-09-07, migration
    `004_add_needs_review.sql`) follow Tool 1's and Tool 3's precedent: a
    scraper that hits missing/unparseable data on an otherwise-required
    field flags the row for a human instead of silently shipping a
    useless value. Added specifically after a real live Anne Arundel
    commercial parcel came back with `address` fully blank -- primary
    field AND every fallback field empty (see
    `leadscorer_full.scrapers.property_socrata`'s `_build_address`
    docstring) -- with no way to surface that before this. Like Tool 3
    (and unlike Tool 1's DB-computed flag), this is populated directly by
    a scraper's own `normalize()`, since Tool 2 has no fuzzy-dedup tier
    to compute a review-worthiness signal from either.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    client_id: str
    source: str
    parcel_id: str
    address: str
    city: str | None = None
    county: str | None = None
    state: str | None = None
    zip_code: str | None = None
    year_built: int | None = None
    year_renovated: int | None = None
    square_footage: int | None = None
    property_use: str | None = None
    owner_name: str | None = None
    owner_mailing_address: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)
    needs_review: bool = False
    review_reason: str | None = None


class PermitRecord(BaseModel):
    """A normalized building/electrical permit record.

    `parcel_id` and `address` are both optional and both present: which
    field actually links a permit back to a property varies by portal
    (some expose the same parcel/account id used by the assessment
    source, some only expose a street address) -- this isn't yet known
    for any real target, so both are carried and the scoring layer
    matches on whichever is available rather than assuming one.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    client_id: str
    source: str
    permit_number: str
    parcel_id: str | None = None
    address: str | None = None
    permit_type: str | None = None
    description: str | None = None
    issued_date: date | None = None
    status: str | None = None
    raw_data: dict[str, Any] = Field(default_factory=dict)
