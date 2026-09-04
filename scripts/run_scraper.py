#!/usr/bin/env python
"""Example end-to-end run of the leadscorer framework.

This is a template/demo, NOT a real scraper. `ExampleStaticPropertyScraper`
and `ExampleStaticPermitScraper` below fetch from small hardcoded
in-memory datasets instead of a real portal, to demonstrate how concrete
`BasePropertyScraper`/`BasePermitScraper` subclasses plug into
fetch -> parse -> normalize -> upsert -> rank. Real portal scrapers
belong in a downstream client deployment package (e.g.
`leadscorer_full.scrapers`), once a real target has been manually
inspected -- see this repo's README for why none is wired up yet.

The age threshold (2012) and retrofit keywords used below are example
values for the demo dataset only, not a recommendation -- a real
deployment's actual threshold and keywords are a client-specific config
decision (see `leadscorer_full`).

Usage:
    python scripts/run_scraper.py --client-id demo
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from dotenv import load_dotenv

from leadscorer.db.client import (
    get_connection,
    permits_for_client,
    properties_for_client,
    upsert_permit,
    upsert_property,
)
from leadscorer.normalize.schema import PermitRecord, PropertyRecord
from leadscorer.scoring.basic import rank_candidates
from leadscorer.scrapers.base import BasePermitScraper, BasePropertyScraper

_EXAMPLE_PROPERTY_SOURCE = "example-static-assessment-source"
_EXAMPLE_PERMIT_SOURCE = "example-static-permit-source"

# Four synthetic properties: an old, large, never-retrofitted warehouse
# (should rank #1), an old, smaller, never-retrofitted office (should
# rank #2, lower than the warehouse on size alone), a building that's
# old but already has a lighting-retrofit permit on file (excluded), and
# a building too new to qualify at all (excluded).
_EXAMPLE_PROPERTIES: list[dict[str, Any]] = [
    {
        "parcel_id": "EX-P-001",
        "address": "100 Example Warehouse Way",
        "county": "Example County",
        "year_built": 1975,
        "square_footage": 60000,
        "property_use": "Warehouse",
        "owner_name": "Example Logistics LLC",
    },
    {
        "parcel_id": "EX-P-002",
        "address": "200 Example Office Park Dr",
        "county": "Example County",
        "year_built": 2005,
        "square_footage": 8000,
        "property_use": "Office",
        "owner_name": "Example Office Holdings LLC",
    },
    {
        "parcel_id": "EX-P-003",
        "address": "300 Example Retrofit Rd",
        "county": "Example County",
        "year_built": 1980,
        "square_footage": 30000,
        "property_use": "Retail",
        "owner_name": "Example Retail Corp",
    },
    {
        "parcel_id": "EX-P-004",
        "address": "400 Example New Build Blvd",
        "county": "Example County",
        "year_built": 2018,
        "square_footage": 15000,
        "property_use": "Office",
        "owner_name": "Example New Build LLC",
    },
]

_EXAMPLE_PERMITS: list[dict[str, Any]] = [
    {
        "permit_number": "EX-PM-001",
        "parcel_id": "EX-P-003",
        "permit_type": "Electrical",
        "description": "LED lighting retrofit, full building",
        "issued_date": "2019-06-01",
        "status": "Finaled",
    },
]


class ExampleStaticPropertyScraper(BasePropertyScraper):
    """Template scraper demonstrating the `BasePropertyScraper` interface."""

    def fetch(self) -> list[dict[str, Any]]:
        return _EXAMPLE_PROPERTIES

    def parse(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return raw

    def normalize(self, raw_record: dict[str, Any]) -> PropertyRecord:
        return PropertyRecord(
            client_id=self.client_id,
            source=self.source,
            raw_data=raw_record,
            **raw_record,
        )


class ExampleStaticPermitScraper(BasePermitScraper):
    """Template scraper demonstrating the `BasePermitScraper` interface."""

    def fetch(self) -> list[dict[str, Any]]:
        return _EXAMPLE_PERMITS

    def parse(self, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return raw

    def normalize(self, raw_record: dict[str, Any]) -> PermitRecord:
        return PermitRecord(
            client_id=self.client_id,
            source=self.source,
            raw_data=raw_record,
            **raw_record,
        )


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run the example leadscorer demo scraper.")
    parser.add_argument("--client-id", required=True, help="Client id to tag records with.")
    args = parser.parse_args()

    property_scraper = ExampleStaticPropertyScraper(client_id=args.client_id, source=_EXAMPLE_PROPERTY_SOURCE)
    permit_scraper = ExampleStaticPermitScraper(client_id=args.client_id, source=_EXAMPLE_PERMIT_SOURCE)

    conn = get_connection()
    try:
        prop_count = 0
        for record in property_scraper.run():
            row = upsert_property(conn, record)
            prop_count += 1
            print(f"Upserted property: {row['address']} (parcel_id={row['parcel_id']})")

        permit_count = 0
        for record in permit_scraper.run():
            row = upsert_permit(conn, record)
            permit_count += 1
            print(f"Upserted permit: {row['permit_number']} (parcel_id={row['parcel_id']})")

        print(f"Done. Processed {prop_count} propert(y/ies) and {permit_count} permit(s).")

        properties = properties_for_client(conn, args.client_id)
        permits = permits_for_client(conn, args.client_id)
        ranked = rank_candidates(
            properties,
            permits,
            threshold_year=2012,
            retrofit_keywords=["lighting", "led"],
        )

        print("\nRanked retrofit-lead candidates (demo threshold/keywords):")
        if not ranked:
            print("  No qualifying candidates.")
        for i, lead in enumerate(ranked, start=1):
            print(f"  {i}. {lead.address} -- score {lead.score:.2f}")
            for reason in lead.reasons:
                print(f"       - {reason}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
