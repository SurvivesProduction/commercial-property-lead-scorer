from leadscorer.scoring.basic import (
    LeadScore,
    age_score,
    has_retrofit_permit,
    match_permits_to_property,
    rank_candidates,
    score_property,
    size_score,
)

# -- age_score ----------------------------------------------------------


def test_age_score_zero_at_threshold() -> None:
    assert age_score({"year_built": 2012}, threshold_year=2012) == 0.0


def test_age_score_zero_when_newer_than_threshold() -> None:
    assert age_score({"year_built": 2018}, threshold_year=2012) == 0.0


def test_age_score_scales_linearly_below_cap() -> None:
    # 15 years past threshold, cap at 30 -> 0.5
    assert age_score({"year_built": 1997}, threshold_year=2012, max_years_past_threshold=30) == 0.5


def test_age_score_caps_at_one() -> None:
    # 60 years past threshold, cap at 30 -> capped at 1.0, not 2.0
    assert age_score({"year_built": 1952}, threshold_year=2012, max_years_past_threshold=30) == 1.0


def test_age_score_prefers_year_renovated_over_year_built() -> None:
    # Renovated in 2015 (newer than threshold) should score 0 even though
    # originally built in 1950 -- renovation is the more relevant signal.
    prop = {"year_built": 1950, "year_renovated": 2015}
    assert age_score(prop, threshold_year=2012) == 0.0


def test_age_score_zero_when_year_unknown() -> None:
    assert age_score({}, threshold_year=2012) == 0.0


# -- size_score -----------------------------------------------------------


def test_size_score_caps_at_one() -> None:
    assert size_score({"square_footage": 40000}, reference_sqft=20000) == 1.0


def test_size_score_scales_linearly_below_cap() -> None:
    assert size_score({"square_footage": 10000}, reference_sqft=20000) == 0.5


def test_size_score_neutral_when_missing() -> None:
    # No square_footage key at all -- unknown, not "confirmed smallest".
    assert size_score({}, reference_sqft=20000) == 0.5


def test_size_score_neutral_when_zero() -> None:
    # Real assessment sources (e.g. Maryland SDAT) use 0 to mean "no
    # structure-area figure on file", not a genuine 0 sq ft building --
    # treated the same as missing.
    assert size_score({"square_footage": 0}, reference_sqft=20000) == 0.5


# -- has_retrofit_permit ----------------------------------------------------


def test_has_retrofit_permit_matches_description() -> None:
    permits = [{"permit_type": "Electrical", "description": "LED lighting retrofit"}]
    assert has_retrofit_permit(permits, retrofit_keywords=["lighting"]) is True


def test_has_retrofit_permit_matches_permit_type() -> None:
    permits = [{"permit_type": "Lighting Retrofit", "description": None}]
    assert has_retrofit_permit(permits, retrofit_keywords=["lighting"]) is True


def test_has_retrofit_permit_is_case_insensitive() -> None:
    permits = [{"permit_type": None, "description": "Full LED Retrofit"}]
    assert has_retrofit_permit(permits, retrofit_keywords=["led"]) is True


def test_has_retrofit_permit_false_when_no_match() -> None:
    permits = [{"permit_type": "Roofing", "description": "Roof replacement"}]
    assert has_retrofit_permit(permits, retrofit_keywords=["lighting", "led"]) is False


def test_has_retrofit_permit_false_for_empty_permits() -> None:
    assert has_retrofit_permit([], retrofit_keywords=["lighting"]) is False


def test_has_retrofit_permit_false_for_empty_keywords() -> None:
    permits = [{"permit_type": "Electrical", "description": "LED lighting retrofit"}]
    assert has_retrofit_permit(permits, retrofit_keywords=[]) is False


# -- match_permits_to_property ---------------------------------------------


def test_match_permits_to_property_by_parcel_id() -> None:
    prop = {"parcel_id": "P-001", "address": "100 Main St"}
    permits = [
        {"parcel_id": "P-001", "address": "different address on file"},
        {"parcel_id": "P-002", "address": "200 Unrelated Ave"},
    ]
    matched = match_permits_to_property(prop, permits)
    assert len(matched) == 1
    assert matched[0]["parcel_id"] == "P-001"


def test_match_permits_to_property_falls_back_to_address() -> None:
    prop = {"parcel_id": "P-001", "address": "100 Main St"}
    permits = [{"parcel_id": None, "address": "100 MAIN   ST"}]
    matched = match_permits_to_property(prop, permits)
    assert len(matched) == 1


def test_match_permits_to_property_no_match() -> None:
    prop = {"parcel_id": "P-001", "address": "100 Main St"}
    permits = [{"parcel_id": "P-999", "address": "200 Other Ave"}]
    assert match_permits_to_property(prop, permits) == []


def test_match_permits_to_property_matches_despite_permit_city_zip_suffix() -> None:
    # Regression test for the real bug found live: Anne Arundel's Accela
    # permit portal appends ", CITY ZIP" to ~99.9% of addresses
    # (e.g. "2839 JESSUP RD, HANOVER 21076") while Maryland's Socrata
    # property source never does ("2839 JESSUP RD") -- this alone made
    # every cross-source match fail regardless of real-world overlap.
    prop = {"parcel_id": None, "address": "2839 JESSUP RD"}
    permits = [{"parcel_id": None, "address": "2839 Jessup Rd, Hanover 21076"}]
    matched = match_permits_to_property(prop, permits)
    assert len(matched) == 1


def test_match_permits_to_property_no_match_when_street_genuinely_differs_despite_suffix() -> None:
    # The comma-stripping fix must not become a looser match than
    # intended -- a permit at a different street should still not match
    # just because both addresses happen to carry a city/zip-shaped tail.
    prop = {"parcel_id": None, "address": "100 Main St"}
    permits = [{"parcel_id": None, "address": "200 Other Ave, Glen Burnie 21061"}]
    assert match_permits_to_property(prop, permits) == []


# -- score_property -----------------------------------------------------


_OLD_LARGE_PROPERTY = {"parcel_id": "P-001", "address": "100 Main St", "year_built": 1975, "square_footage": 60000}


def test_score_property_qualifies_with_no_permits() -> None:
    lead = score_property(_OLD_LARGE_PROPERTY, permits=[], threshold_year=2012, retrofit_keywords=["lighting"])
    assert isinstance(lead, LeadScore)
    assert lead.parcel_id == "P-001"
    assert lead.score > 0


def test_score_property_excluded_by_retrofit_permit() -> None:
    permits = [{"permit_type": "Electrical", "description": "Lighting retrofit"}]
    lead = score_property(_OLD_LARGE_PROPERTY, permits, threshold_year=2012, retrofit_keywords=["lighting"])
    assert lead is None


def test_score_property_excluded_when_too_new() -> None:
    new_property = {"parcel_id": "P-002", "address": "200 New Ave", "year_built": 2018, "square_footage": 20000}
    lead = score_property(new_property, permits=[], threshold_year=2012, retrofit_keywords=["lighting"])
    assert lead is None


def test_score_property_excluded_when_year_unknown() -> None:
    unknown_year_property = {"parcel_id": "P-003", "address": "300 Unknown Ave", "square_footage": 20000}
    lead = score_property(unknown_year_property, permits=[], threshold_year=2012, retrofit_keywords=["lighting"])
    assert lead is None


def test_score_property_combines_age_and_size() -> None:
    small_old = {"parcel_id": "P-A", "address": "A", "year_built": 1975, "square_footage": 1000}
    large_old = {"parcel_id": "P-B", "address": "B", "year_built": 1975, "square_footage": 60000}
    lead_small = score_property(small_old, [], threshold_year=2012, retrofit_keywords=["lighting"])
    lead_large = score_property(large_old, [], threshold_year=2012, retrofit_keywords=["lighting"])
    assert lead_large.score > lead_small.score


def test_score_property_defaults_active_trader_license_false() -> None:
    # A property_record with no active_trader_license key at all (every
    # source except one that specifically populates it) must behave
    # exactly as before this field existed.
    lead = score_property(_OLD_LARGE_PROPERTY, permits=[], threshold_year=2012, retrofit_keywords=["lighting"])
    assert lead.active_trader_license is False


def test_score_property_carries_active_trader_license_true() -> None:
    licensed_property = {**_OLD_LARGE_PROPERTY, "active_trader_license": True}
    lead = score_property(licensed_property, permits=[], threshold_year=2012, retrofit_keywords=["lighting"])
    assert lead.active_trader_license is True


def test_score_property_does_not_change_score_based_on_active_trader_license() -> None:
    # The deprioritization signal must never touch `score` itself -- see
    # rank_candidates's docstring for where it actually applies.
    unlicensed = score_property(_OLD_LARGE_PROPERTY, [], threshold_year=2012, retrofit_keywords=["lighting"])
    licensed = score_property(
        {**_OLD_LARGE_PROPERTY, "active_trader_license": True}, [], threshold_year=2012, retrofit_keywords=["lighting"]
    )
    assert unlicensed.score == licensed.score


# -- rank_candidates ------------------------------------------------------


def test_rank_candidates_orders_highest_score_first_and_drops_excluded() -> None:
    properties = [
        {"parcel_id": "P-001", "address": "100 Warehouse Way", "year_built": 1975, "square_footage": 60000},
        {"parcel_id": "P-002", "address": "200 Small Office Dr", "year_built": 2000, "square_footage": 5000},
        {"parcel_id": "P-003", "address": "300 Retrofit Rd", "year_built": 1980, "square_footage": 30000},
        {"parcel_id": "P-004", "address": "400 New Build Blvd", "year_built": 2018, "square_footage": 15000},
    ]
    permits = [
        {"parcel_id": "P-003", "permit_type": "Electrical", "description": "LED lighting retrofit"},
    ]

    ranked = rank_candidates(properties, permits, threshold_year=2012, retrofit_keywords=["lighting", "led"])

    ranked_parcel_ids = [lead.parcel_id for lead in ranked]
    assert ranked_parcel_ids == ["P-001", "P-002"]
    assert ranked[0].score >= ranked[1].score


def test_rank_candidates_empty_when_nothing_qualifies() -> None:
    properties = [{"parcel_id": "P-001", "address": "100 Main St", "year_built": 2020, "square_footage": 5000}]
    assert rank_candidates(properties, [], threshold_year=2012, retrofit_keywords=["lighting"]) == []


def test_rank_candidates_breaks_score_ties_by_square_footage_descending() -> None:
    # Both properties are far enough past the threshold and at/over
    # reference_sqft that age_score and size_score both cap at 1.0 --
    # an exact score tie. Regression test for a real issue found against
    # live data: 214 of 2,959 real qualifying candidates tied at the max
    # score, with input order (not building size) deciding who ranked
    # first -- a 23,100 sq ft building outranked a 259,502 sq ft one.
    properties = [
        {"parcel_id": "P-SMALL", "address": "1 Small Big Box Way", "year_built": 1970, "square_footage": 21000},
        {"parcel_id": "P-LARGE", "address": "2 Massive Warehouse Blvd", "year_built": 1970, "square_footage": 250000},
    ]
    ranked = rank_candidates(properties, [], threshold_year=2012, retrofit_keywords=["lighting"])

    assert ranked[0].score == ranked[1].score == 1.0
    assert [lead.parcel_id for lead in ranked] == ["P-LARGE", "P-SMALL"]


def test_rank_candidates_treats_unknown_square_footage_as_smallest_in_tiebreak() -> None:
    properties = [
        {"parcel_id": "P-UNKNOWN", "address": "1 Mystery Size Ln", "year_built": 1970, "square_footage": None},
        {"parcel_id": "P-KNOWN", "address": "2 Known Size Ave", "year_built": 1970, "square_footage": 20000},
    ]
    ranked = rank_candidates(properties, [], threshold_year=2012, retrofit_keywords=["lighting"])

    assert [lead.parcel_id for lead in ranked] == ["P-KNOWN", "P-UNKNOWN"]


def test_rank_candidates_score_still_takes_priority_over_size() -> None:
    # A higher-scoring smaller property must still outrank a
    # lower-scoring larger one -- the tiebreaker only applies within
    # equal scores, it doesn't let size override the actual score.
    properties = [
        {"parcel_id": "P-HIGH-SCORE", "address": "1 Old Small Building", "year_built": 1970, "square_footage": 21000},
        {"parcel_id": "P-LOW-SCORE", "address": "2 Newer Huge Building", "year_built": 2008, "square_footage": 500000},
    ]
    ranked = rank_candidates(properties, [], threshold_year=2012, retrofit_keywords=["lighting"])

    assert [lead.parcel_id for lead in ranked] == ["P-HIGH-SCORE", "P-LOW-SCORE"]
    assert ranked[0].score > ranked[1].score


def test_rank_candidates_deprioritizes_active_trader_license_within_score_tie() -> None:
    # Both properties tie at the max score -- an active Trader's License
    # is a deprioritization tiebreak, not an exclusion: the licensed one
    # still appears, just ranked below its unlicensed, equally-scored peer.
    properties = [
        {
            "parcel_id": "P-LICENSED",
            "address": "1 Active Retail Store",
            "year_built": 1970,
            "square_footage": 25000,
            "active_trader_license": True,
        },
        {"parcel_id": "P-UNLICENSED", "address": "2 Quiet Warehouse", "year_built": 1970, "square_footage": 25000},
    ]
    ranked = rank_candidates(properties, [], threshold_year=2012, retrofit_keywords=["lighting"])

    assert ranked[0].score == ranked[1].score
    assert [lead.parcel_id for lead in ranked] == ["P-UNLICENSED", "P-LICENSED"]


def test_rank_candidates_active_trader_license_does_not_override_a_genuinely_higher_score() -> None:
    # The tiebreak must not become a full two-tier separation: a licensed
    # property with a real higher score still outranks an unlicensed one
    # with a lower score.
    properties = [
        {
            "parcel_id": "P-LICENSED-HIGH-SCORE",
            "address": "1 Big Old Licensed Building",
            "year_built": 1960,
            "square_footage": 300000,
            "active_trader_license": True,
        },
        {
            "parcel_id": "P-UNLICENSED-LOW-SCORE",
            "address": "2 Small Newer Unlicensed Building",
            "year_built": 2008,
            "square_footage": 21000,
        },
    ]
    ranked = rank_candidates(properties, [], threshold_year=2012, retrofit_keywords=["lighting"])

    assert ranked[0].score > ranked[1].score
    assert [lead.parcel_id for lead in ranked] == ["P-LICENSED-HIGH-SCORE", "P-UNLICENSED-LOW-SCORE"]


def test_rank_candidates_active_trader_license_tiebreak_applies_before_square_footage() -> None:
    # Tiebreak order: score, then active_trader_license, then sqft. A
    # smaller unlicensed property must still beat a larger licensed one
    # at the same score.
    properties = [
        {
            "parcel_id": "P-LICENSED-LARGER",
            "address": "1 Larger Licensed Building",
            "year_built": 1970,
            "square_footage": 100000,
            "active_trader_license": True,
        },
        {
            "parcel_id": "P-UNLICENSED-SMALLER",
            "address": "2 Smaller Unlicensed Building",
            "year_built": 1970,
            "square_footage": 25000,
        },
    ]
    ranked = rank_candidates(properties, [], threshold_year=2012, retrofit_keywords=["lighting"])

    assert ranked[0].score == ranked[1].score
    assert [lead.parcel_id for lead in ranked] == ["P-UNLICENSED-SMALLER", "P-LICENSED-LARGER"]
