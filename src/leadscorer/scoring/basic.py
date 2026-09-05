"""Generic, client-agnostic property/permit cross-reference and scoring logic.

Nothing in this module encodes any client-specific business logic -- no
hardcoded "lighting" or "LED" keywords, no hardcoded age threshold. A
downstream deployment (e.g. the full/paid overlay) supplies those as
parameters, the same way `bidscraper.insights.basic.vendor_win_counts`
takes a `category_keyword` rather than hardcoding "electric". See that
module's docstring for the reasoning -- it applies identically here.

Every function here is a pure function over plain dicts (no database
connection, no I/O) specifically so it's unit-testable against synthetic
data without a live scraped portal -- the same "pure scoring function,
DB query stays a thin untested wrapper" split used for
`bidscraper.db.client.score_match` / `classify_confidence` (Tool 1).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


def _normalize_address(address: str | None) -> str | None:
    """Strip a trailing city/zip suffix, then lowercase and collapse whitespace.

    Confirmed live against two real sources (Maryland Socrata property
    assessments and Anne Arundel County's Accela permit portal): the
    property side never includes a city/zip (`"2839 JESSUP RD"`), while
    the permit side appends one after a comma on ~99.9% of records
    (`"406 HOLLY DR, ANNAPOLIS 21403"`). That structural difference alone
    made every cross-source match fail regardless of whether the
    underlying real-world address overlapped -- confirmed live that
    stripping just this suffix recovered exact matches immediately, with
    zero abbreviation differences (e.g. "St" vs "Street") found on either
    side once it's gone, so no further normalization was needed to fix
    the real, measured problem. Safe to apply unconditionally: an address
    with no comma (either source, or a future one) is returned unchanged
    aside from case/whitespace, same as before.

    Still deliberately minimal beyond that -- no abbreviation expansion,
    no unit-number stripping -- since there's no live evidence either is
    needed yet; add them if a future source's real data shows otherwise,
    not preemptively.
    """
    if not address:
        return None
    street_only = address.split(",")[0]
    return re.sub(r"\s+", " ", street_only.strip().lower())


def match_permits_to_property(
    property_record: dict[str, Any], permits: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return the permits that belong to `property_record`.

    Matches on `parcel_id` when both the property and a permit have one
    (the more reliable link, when available), falling back to a
    normalized address match otherwise. Which key a real permit source
    actually exposes isn't known yet -- both paths are supported so
    that's a data question to answer during source inspection, not an
    assumption baked into this function.
    """
    parcel_id = property_record.get("parcel_id")
    normalized_property_address = _normalize_address(property_record.get("address"))

    matched = []
    for permit in permits:
        permit_parcel_id = permit.get("parcel_id")
        if parcel_id and permit_parcel_id and permit_parcel_id == parcel_id:
            matched.append(permit)
            continue
        normalized_permit_address = _normalize_address(permit.get("address"))
        if (
            normalized_property_address
            and normalized_permit_address
            and normalized_property_address == normalized_permit_address
        ):
            matched.append(permit)
    return matched


def has_retrofit_permit(permits: list[dict[str, Any]], retrofit_keywords: list[str]) -> bool:
    """Whether any of `permits` looks like a retrofit of the kind `retrofit_keywords` describes.

    Case-insensitive substring match against each permit's `permit_type`
    and `description` -- the same "check the field(s) that might carry
    the signal, OR them together" approach as
    `bidscraper.insights.basic.vendor_win_counts`'s title-or-vendor-name
    matching, generalized to an arbitrary keyword list instead of one
    hardcoded trade.
    """
    if not retrofit_keywords:
        return False
    lowered_keywords = [kw.lower() for kw in retrofit_keywords]
    for permit in permits:
        haystack = " ".join(
            filter(None, [permit.get("permit_type"), permit.get("description")])
        ).lower()
        if any(kw in haystack for kw in lowered_keywords):
            return True
    return False


def age_score(
    property_record: dict[str, Any], threshold_year: int, max_years_past_threshold: int = 30
) -> float:
    """Score 0-1: how far past `threshold_year` this property's last known construction event is.

    Uses `year_renovated` when present (the more recent, and therefore
    more relevant, signal for "when might lighting last have been
    touched"), falling back to `year_built`. Returns 0.0 if neither is
    known, or if the effective year isn't older than `threshold_year`.
    Scales linearly up to 1.0 at `max_years_past_threshold` years past
    the threshold, then caps -- an extra decade of age past an
    already-strong signal shouldn't keep inflating the score indefinitely.
    """
    effective_year = property_record.get("year_renovated") or property_record.get("year_built")
    if effective_year is None:
        return 0.0
    years_past = threshold_year - effective_year
    if years_past <= 0:
        return 0.0
    return min(years_past / max_years_past_threshold, 1.0)


def size_score(property_record: dict[str, Any], reference_sqft: int = 20_000) -> float:
    """Score 0-1: how large this property is relative to `reference_sqft`.

    Linear, capped at 1.0 at `reference_sqft` -- a building at or above
    that size scores the max; `reference_sqft` is a generic default for
    "large commercial building", meant to be tuned per client/region
    rather than treated as a universal truth.

    Returns a neutral 0.5 (not 0.0) when square footage isn't known --
    either missing entirely or an on-file value of 0, which real
    assessment sources use interchangeably to mean "no structure-area
    figure on file" (a building can't genuinely be 0 sq ft). Scoring
    unknown as 0.0 would treat "we don't know the size" the same as
    "confirmed smallest possible", unfairly burying an old building that
    simply lacks a square-footage figure -- common in real data (e.g.
    ~1/3 of Maryland SDAT commercial records) -- below a confirmed-small
    one it may well be larger than. 0.5 is neutral on the 0-1 scale:
    neither rewarded nor penalized for the unknown dimension.
    """
    square_footage = property_record.get("square_footage")
    if not square_footage:
        return 0.5
    return min(square_footage / reference_sqft, 1.0)


@dataclass(frozen=True)
class LeadScore:
    """A scored, ranked retrofit-lead candidate."""

    parcel_id: str
    address: str
    score: float
    age_component: float
    size_component: float
    effective_year: int | None
    square_footage: int | None
    reasons: tuple[str, ...]
    # Deprioritization signal, not a scoring input -- `score` above is
    # deliberately unaffected by this field; see `rank_candidates`'s
    # docstring for how it's used (a sort tiebreak, not a score penalty).
    # Defaults to False so any property_record that doesn't carry this
    # key (i.e. every source except one that specifically populates it)
    # behaves exactly as before this field existed.
    active_trader_license: bool = False


def score_property(
    property_record: dict[str, Any],
    permits: list[dict[str, Any]],
    threshold_year: int,
    retrofit_keywords: list[str],
    max_years_past_threshold: int = 30,
    reference_sqft: int = 20_000,
    age_weight: float = 0.5,
    size_weight: float = 0.5,
) -> LeadScore | None:
    """Score one property as a retrofit-lead candidate, or None if it doesn't qualify.

    Two hard qualifying conditions (a genuine filter, not part of the
    continuous score): the property must have no permit on file that
    looks like the retrofit already happened (`has_retrofit_permit`), and
    its effective construction year must be known and older than
    `threshold_year`. A property failing either isn't a plausible
    candidate at all, so it's excluded (returns None) rather than merely
    scored low.

    Among properties that qualify, the score is a weighted combination of
    `age_score` and `size_score` -- this is the "rank by combined signal
    strength, not just a flat filter" behavior: two buildings that both
    clear the age/permit bar are still meaningfully different leads if
    one is a 5,000 sq ft office built in 2011 and the other is a 60,000
    sq ft warehouse built in 1975.

    Reads `property_record.get("active_trader_license")` generically (no
    knowledge of where that flag came from -- e.g. the full/paid overlay
    may join it on from an occupancy-confirmation source) and carries it
    onto the returned `LeadScore` unchanged. This is deliberately NOT a
    third scoring input alongside age/size: `score` here is unaffected by
    it either way -- see `rank_candidates`'s docstring for where it
    actually affects ordering.
    """
    if has_retrofit_permit(permits, retrofit_keywords):
        return None

    effective_year = property_record.get("year_renovated") or property_record.get("year_built")
    if effective_year is None or effective_year >= threshold_year:
        return None

    age_component = age_score(property_record, threshold_year, max_years_past_threshold)
    size_component = size_score(property_record, reference_sqft)
    score = age_weight * age_component + size_weight * size_component

    square_footage = property_record.get("square_footage")
    reasons = [
        f"Last known construction/renovation year is {effective_year}, "
        f"{threshold_year - effective_year} years before the {threshold_year} threshold.",
        f"{square_footage:,} sq ft on file." if square_footage else "No square footage on file.",
        "No permit on file matching a retrofit.",
    ]

    return LeadScore(
        parcel_id=property_record.get("parcel_id", ""),
        address=property_record.get("address", ""),
        score=score,
        age_component=age_component,
        size_component=size_component,
        effective_year=effective_year,
        square_footage=square_footage,
        reasons=tuple(reasons),
        active_trader_license=bool(property_record.get("active_trader_license", False)),
    )


def rank_candidates(
    properties: list[dict[str, Any]],
    permits: list[dict[str, Any]],
    threshold_year: int,
    retrofit_keywords: list[str],
    max_years_past_threshold: int = 30,
    reference_sqft: int = 20_000,
    age_weight: float = 0.5,
    size_weight: float = 0.5,
) -> list[LeadScore]:
    """Score and rank every qualifying property, highest score first.

    `permits` is the full permit list for the client; each property's own
    permits are resolved via `match_permits_to_property` before scoring.

    Ties break on two factors, in order: first whether the property has
    an `active_trader_license` (see `LeadScore`), then `square_footage`
    (largest first, unknown treated as smallest) -- rather than left in
    whatever order `properties` happened to arrive in. The square-footage
    tiebreak matters more than it sounds like it should: both `age_score`
    and `size_score` cap at 1.0 (any property at/older than
    `max_years_past_threshold` past `threshold_year`; any property at/over
    `reference_sqft`), so it's common for a large fraction of qualifying
    candidates to tie at the exact maximum combined score -- confirmed
    live against real Anne Arundel data, 214 of 2,959 qualifying
    candidates tied at score 1.0, with square footage ranging from
    19,990 to 216,344 *within that one tie group*. Leaving ties in input
    order let a 23,100 sq ft building outrank a 259,502 sq ft one for no
    reason connected to the actual business signal (a bigger building is
    a bigger potential retrofit contract) -- the whole point of ranking
    at all.

    The `active_trader_license` tiebreak is a genuine deprioritization
    signal, not a scoring input: an active Trader's License (Maryland
    requires one only for retail/goods-selling businesses) is a strong
    positive occupancy signal a candidate shouldn't be excluded or
    score-penalized for -- most legitimate targets (warehouses, offices,
    industrial) will never have one, so its *absence* means nothing. Its
    *presence*, though, is worth deprioritizing slightly: among
    similarly-scored candidates, one without any sign of an active
    retail tenant is a more promising outreach target than one that's
    evidently already an operating retail business. This only breaks
    ties/near-ties -- a candidate with a genuinely higher `score` still
    outranks one without, regardless of license status; this can't
    override the primary age+size signal, only nudge within it.

    Neither tiebreaker changes any individual `score` or the age/size
    weighting, only how equal (or near-equal) scores are ordered against
    each other.
    """
    scored = []
    for property_record in properties:
        property_permits = match_permits_to_property(property_record, permits)
        lead = score_property(
            property_record,
            property_permits,
            threshold_year,
            retrofit_keywords,
            max_years_past_threshold=max_years_past_threshold,
            reference_sqft=reference_sqft,
            age_weight=age_weight,
            size_weight=size_weight,
        )
        if lead is not None:
            scored.append(lead)

    return sorted(
        scored,
        key=lambda lead: (lead.score, not lead.active_trader_license, lead.square_footage or 0),
        reverse=True,
    )
