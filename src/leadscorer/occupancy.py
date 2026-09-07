"""Occupancy-check scoping: which candidates need a fresh live check.

Pure function, no I/O -- same "pure logic, DB stays a thin untested
wrapper" split as `leadscorer.scoring.basic` and `leadscorer.snapshot`
(see those modules' docstrings). The DB-touching counterpart
(`leadscorer.db.client.occupancy_checks_for_client` /
`save_occupancy_checks`) reads/writes the `occupancy_checks` table (see
`migrations/003_occupancy_checks.sql`) this module's output is meant to
be computed against.

Nothing here is client- or source-specific (no Trader's License field
names, no Maryland portal knowledge) -- it lives in the shared package
alongside `scoring.basic`/`snapshot`, not the full/paid overlay, same
reasoning as both of those.

Exists to bound occupancy-check volume: checking every currently-
qualifying candidate on every run means re-hitting an external county
portal for the full qualifying set (thousands of candidates) every
single cycle, most of which haven't changed. Instead, a candidate is
only checked when it has no stored check yet (which is exactly what
"newly-qualifying, piggyback on the novelty gate" means in practice --
a brand-new candidate has no prior occupancy history by definition, and
a candidate re-qualifying after a stale-enough gap gets re-checked for
the same reason) or its last check has aged past a configurable refresh
window -- see `leadscorer_full.config.OCCUPANCY_REFRESH_DAYS` for the
deployed default and the reasoning behind it. There's deliberately no
separate "is this parcel new this run" input: `occupancy_checks` already
persists per-parcel across runs, so "no stored check" and "newly
qualifying with no history" are the same condition -- adding a second,
redundant novelty-gate diff just to detect the same thing would be
duplicated state that could drift out of sync with this table.
"""
from __future__ import annotations

from datetime import datetime, timedelta


def select_parcels_needing_check(
    qualifying_parcel_ids: set[str],
    stored_checked_at: dict[str, datetime],
    refresh_after_days: int,
    now: datetime,
) -> set[str]:
    """Return the subset of `qualifying_parcel_ids` that need a fresh live check this run.

    A parcel needs checking if its `stored_checked_at` entry is missing
    (never checked before -- covers every newly-qualifying candidate,
    since a brand-new candidate has no prior row in `occupancy_checks` by
    definition) or older than `refresh_after_days` relative to `now`
    (the periodic full-refresh case for anyone whose check has aged out,
    regardless of whether they're new this run).

    Only ever considers `qualifying_parcel_ids` -- a candidate that
    doesn't currently qualify is never checked, matching
    `annotate_active_trader_license`'s existing "only annotate what
    qualifies" bound on live network cost (occupancy is a tiebreak that
    `score_property` never reads for a non-qualifying property anyway).
    """
    stale_cutoff = now - timedelta(days=refresh_after_days)
    needing_check: set[str] = set()

    for parcel_id in qualifying_parcel_ids:
        checked_at = stored_checked_at.get(parcel_id)
        if checked_at is None or checked_at < stale_cutoff:
            needing_check.add(parcel_id)

    return needing_check
