-- 004_add_needs_review.sql
-- Adds a review-flagging pair to `properties`, following Tool 1's
-- `bid_awards.needs_review` / Tool 3's `opportunities.needs_review`
-- precedent: a scraper that hits missing or unparseable data on an
-- otherwise-required field flags the row for a human instead of
-- silently shipping a useless value.
--
-- Scoped to `properties` only (not `permits`) -- the real gap this fixes
-- (a fully blank address, primary field and every fallback field empty)
-- was found in leadscorer_full.scrapers.property_socrata specifically;
-- no analogous permit-side gap has been found, so this isn't extended
-- there speculatively.
--
-- Like Tool 3 (and unlike Tool 1, which computes this from dedup-match
-- confidence), this is populated directly from
-- `PropertyRecord.needs_review`/`review_reason` by the scraper's own
-- normalize() -- Tool 2's upsert has no fuzzy-match tier to derive a
-- review-worthiness signal from instead.

alter table properties
    add column if not exists needs_review boolean not null default false;

alter table properties
    add column if not exists review_reason text;

create index if not exists idx_properties_needs_review
    on properties (client_id, needs_review)
    where needs_review;
