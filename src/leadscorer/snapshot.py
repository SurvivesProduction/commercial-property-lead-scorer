"""Novelty-gate support: diffing a ranked candidate list against a prior snapshot.

Pure functions over plain dicts, no I/O -- same "pure logic, DB stays a
thin untested wrapper" split as `leadscorer.scoring.basic` (see that
module's docstring). `leadscorer.db.client.latest_candidate_snapshot` /
`save_candidate_snapshot` / `save_candidate_dropouts` are the DB-touching
counterparts that read/write the `candidate_snapshots` /
`candidate_dropouts` tables (see `migrations/002_candidate_snapshots.sql`)
this module's output is meant to be persisted into.

Nothing here is client-specific -- no lighting keywords, no Maryland
field names -- so it lives in the shared package alongside
`scoring.basic`, not the full/paid overlay.
"""
from __future__ import annotations

from typing import Any

from leadscorer.scoring.basic import LeadScore


def candidate_snapshot_fields(lead: LeadScore) -> dict[str, Any]:
    """The subset of a `LeadScore` worth persisting/diffing as a snapshot row.

    Deliberately just the fields a recipient or a future report would
    want to see again for a candidate that's since dropped off (address,
    score, year, size, license status) -- not `age_component`/
    `size_component`/`reasons`, which are score-explanation detail rather
    than identifying/reporting fields.

    Includes `active_trader_license` -- already computed by `score_property`
    (it never affects `score` itself, only `rank_candidates`'s tiebreak
    order; see that function's docstring) -- so presentation layers
    downstream (e.g. the full/paid overlay's HTML badge rendering) can
    show it without needing their own copy of a `LeadScore`.
    """
    return {
        "parcel_id": lead.parcel_id,
        "address": lead.address,
        "score": lead.score,
        "effective_year": lead.effective_year,
        "square_footage": lead.square_footage,
        "active_trader_license": lead.active_trader_license,
    }


def diff_candidate_snapshots(
    current: list[dict[str, Any]], previous: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Diff two candidate-snapshot dict lists by `parcel_id`.

    Returns `(new, dropped)`:
      - `new` is every item in `current` whose `parcel_id` isn't in
        `previous` -- reflects THIS run's fresh field values.
      - `dropped` is every item in `previous` whose `parcel_id` isn't in
        `current` -- reflects the LAST-KNOWN field values, since a
        dropped candidate has no current data to report by definition
        (most likely a real Electrical Permit now excludes it, but this
        function doesn't attempt to diagnose why -- see the full/paid
        overlay's ARCHITECTURE.md for that open question).

    An empty `previous` (no prior snapshot exists yet, e.g. the very
    first run) correctly makes every current candidate "new" and nothing
    "dropped" -- the right bootstrap behavior, not a special case handled
    separately.

    Both `current` and `previous` must be `candidate_snapshot_fields`-shaped
    dicts (or at least carry a `parcel_id` key); order within each
    returned list follows the input list's own order.
    """
    previous_ids = {item["parcel_id"] for item in previous}
    current_ids = {item["parcel_id"] for item in current}
    new = [item for item in current if item["parcel_id"] not in previous_ids]
    dropped = [item for item in previous if item["parcel_id"] not in current_ids]
    return new, dropped
