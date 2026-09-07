from datetime import datetime, timedelta, timezone

from leadscorer.occupancy import select_parcels_needing_check

_NOW = datetime(2026, 9, 7, tzinfo=timezone.utc)
_REFRESH_DAYS = 180


def test_never_checked_parcel_needs_check() -> None:
    result = select_parcels_needing_check(
        qualifying_parcel_ids={"P-001"},
        stored_checked_at={},
        refresh_after_days=_REFRESH_DAYS,
        now=_NOW,
    )
    assert result == {"P-001"}


def test_recently_checked_parcel_does_not_need_check() -> None:
    result = select_parcels_needing_check(
        qualifying_parcel_ids={"P-001"},
        stored_checked_at={"P-001": _NOW - timedelta(days=10)},
        refresh_after_days=_REFRESH_DAYS,
        now=_NOW,
    )
    assert result == set()


def test_stale_checked_parcel_needs_recheck() -> None:
    result = select_parcels_needing_check(
        qualifying_parcel_ids={"P-001"},
        stored_checked_at={"P-001": _NOW - timedelta(days=200)},
        refresh_after_days=_REFRESH_DAYS,
        now=_NOW,
    )
    assert result == {"P-001"}


def test_boundary_exactly_at_refresh_window_counts_as_stale() -> None:
    # checked_at exactly `refresh_after_days` ago is strictly less than
    # `now - refresh_after_days`... equal, not less -- so it should NOT
    # yet be selected (the cutoff is exclusive: only strictly older than
    # the window needs a recheck, not exactly at it).
    result = select_parcels_needing_check(
        qualifying_parcel_ids={"P-001"},
        stored_checked_at={"P-001": _NOW - timedelta(days=_REFRESH_DAYS)},
        refresh_after_days=_REFRESH_DAYS,
        now=_NOW,
    )
    assert result == set()


def test_boundary_one_day_past_refresh_window_needs_recheck() -> None:
    result = select_parcels_needing_check(
        qualifying_parcel_ids={"P-001"},
        stored_checked_at={"P-001": _NOW - timedelta(days=_REFRESH_DAYS + 1)},
        refresh_after_days=_REFRESH_DAYS,
        now=_NOW,
    )
    assert result == {"P-001"}


def test_non_qualifying_parcel_never_selected_even_with_no_history() -> None:
    # occupancy_checks may carry stale/no data for a parcel that simply
    # isn't in qualifying_parcel_ids this run (e.g. it dropped off) --
    # this function must never select anything outside that set.
    result = select_parcels_needing_check(
        qualifying_parcel_ids={"P-001"},
        stored_checked_at={},
        refresh_after_days=_REFRESH_DAYS,
        now=_NOW,
    )
    assert "P-999" not in result


def test_mixed_set_only_returns_the_ones_needing_a_check() -> None:
    result = select_parcels_needing_check(
        qualifying_parcel_ids={"P-001", "P-002", "P-003"},
        stored_checked_at={
            "P-001": _NOW - timedelta(days=10),  # fresh, skip
            "P-002": _NOW - timedelta(days=200),  # stale, recheck
            # P-003: never checked, recheck
        },
        refresh_after_days=_REFRESH_DAYS,
        now=_NOW,
    )
    assert result == {"P-002", "P-003"}


def test_empty_qualifying_set_returns_empty() -> None:
    result = select_parcels_needing_check(
        qualifying_parcel_ids=set(),
        stored_checked_at={"P-001": _NOW - timedelta(days=200)},
        refresh_after_days=_REFRESH_DAYS,
        now=_NOW,
    )
    assert result == set()
