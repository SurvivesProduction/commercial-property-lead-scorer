from leadscorer.scoring.basic import LeadScore
from leadscorer.snapshot import candidate_snapshot_fields, diff_candidate_snapshots


def _snapshot_dict(**overrides) -> dict:
    defaults = dict(
        parcel_id="P-001",
        address="100 Example Warehouse Way",
        score=0.9,
        effective_year=1975,
        square_footage=60000,
    )
    defaults.update(overrides)
    return defaults


# -- candidate_snapshot_fields ------------------------------------------


def test_candidate_snapshot_fields_extracts_reportable_fields() -> None:
    lead = LeadScore(
        parcel_id="P-001",
        address="100 Example Warehouse Way",
        score=0.9,
        age_component=1.0,
        size_component=0.8,
        effective_year=1975,
        square_footage=60000,
        reasons=("example reason",),
        active_trader_license=True,
    )
    assert candidate_snapshot_fields(lead) == {
        "parcel_id": "P-001",
        "address": "100 Example Warehouse Way",
        "score": 0.9,
        "effective_year": 1975,
        "square_footage": 60000,
        "active_trader_license": True,
    }


def test_candidate_snapshot_fields_defaults_active_trader_license_false() -> None:
    lead = LeadScore(
        parcel_id="P-001",
        address="100 Example Warehouse Way",
        score=0.9,
        age_component=1.0,
        size_component=0.8,
        effective_year=1975,
        square_footage=60000,
        reasons=("example reason",),
    )
    assert candidate_snapshot_fields(lead)["active_trader_license"] is False


# -- diff_candidate_snapshots ---------------------------------------------


def test_diff_both_empty() -> None:
    new, dropped = diff_candidate_snapshots([], [])
    assert new == []
    assert dropped == []


def test_diff_new_only_no_prior_snapshot() -> None:
    # The bootstrap case: no prior snapshot exists yet, so every current
    # candidate is correctly "new" and nothing is "dropped" -- not a
    # special case, just what falls out of an empty `previous`.
    current = [_snapshot_dict(parcel_id="P-001"), _snapshot_dict(parcel_id="P-002")]
    new, dropped = diff_candidate_snapshots(current, [])
    assert {c["parcel_id"] for c in new} == {"P-001", "P-002"}
    assert dropped == []


def test_diff_dropped_only_nothing_currently_qualifies() -> None:
    previous = [_snapshot_dict(parcel_id="P-001"), _snapshot_dict(parcel_id="P-002")]
    new, dropped = diff_candidate_snapshots([], previous)
    assert new == []
    assert {c["parcel_id"] for c in dropped} == {"P-001", "P-002"}


def test_diff_both_populated_mixed_overlap() -> None:
    previous = [
        _snapshot_dict(parcel_id="P-001", address="1 Stays Qualifying St"),
        _snapshot_dict(parcel_id="P-002", address="2 Will Drop Off Ave"),
    ]
    current = [
        _snapshot_dict(parcel_id="P-001", address="1 Stays Qualifying St"),
        _snapshot_dict(parcel_id="P-003", address="3 Newly Qualifying Blvd"),
    ]
    new, dropped = diff_candidate_snapshots(current, previous)
    assert [c["parcel_id"] for c in new] == ["P-003"]
    assert [c["parcel_id"] for c in dropped] == ["P-002"]


def test_diff_no_changes_when_current_matches_previous_exactly() -> None:
    same = [_snapshot_dict(parcel_id="P-001"), _snapshot_dict(parcel_id="P-002")]
    new, dropped = diff_candidate_snapshots(list(same), list(same))
    assert new == []
    assert dropped == []


def test_diff_dropped_items_carry_last_known_fields_not_current() -> None:
    # A dropped candidate has no "current" data by definition -- the
    # returned dict must be the PREVIOUS snapshot's values verbatim.
    previous = [_snapshot_dict(parcel_id="P-001", score=0.75, square_footage=41000)]
    new, dropped = diff_candidate_snapshots([], previous)
    assert dropped[0]["score"] == 0.75
    assert dropped[0]["square_footage"] == 41000


def test_diff_new_items_carry_current_fields() -> None:
    current = [_snapshot_dict(parcel_id="P-009", score=0.6, square_footage=15000)]
    new, dropped = diff_candidate_snapshots(current, [])
    assert new[0]["score"] == 0.6
    assert new[0]["square_footage"] == 15000
