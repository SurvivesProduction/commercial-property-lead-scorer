# commercial-property-lead-scorer

Public template: cross-references commercial property assessment records against permit history to surface buildings that are old enough to plausibly still have outdated infrastructure (e.g. pre-LED lighting) and have no permit on file showing a retrofit was ever done -- a scored, ranked lead list rather than a flat filter.

This is the generic/free version -- no real portal targets, no client-specific age thresholds or retrofit keywords, no alerting. See the full build for a real client deployment: [commercial-property-lead-scorer-full](../commercial-property-lead-scorer-full).

**Deployment note:** this repo also exists as a second clone on the deployment machine (under `Desktop\SurvivesProduction-001\...\tool2-commercial-property-lead-scorer\commercial-property-lead-scorer`), installed editable into the deploy venvs the scheduled jobs use. GitHub is the single source of truth -- that copy must only be updated via `git pull`, never edited directly. See `commercial-property-lead-scorer-full`'s README for the full deployment picture.

## What this is

`leadscorer` is a small, reusable framework for turning "a property assessment source + a permit source" into a ranked list of retrofit-lead candidates:

- `BasePropertyScraper` / `BasePermitScraper` -- abstract classes defining the `fetch -> parse -> normalize` pipeline each concrete scraper implements (two, not one, since this tool cross-references two independent source types).
- `PropertyRecord` / `PermitRecord` -- the schemas each scraper normalizes into.
- A Postgres client (`leadscorer.db.client`) that upserts both record types keyed on their real, stable native identifiers (parcel/account number, permit number) -- see that module's docstring for why this doesn't need Tool 1's fuzzy-match dedup tiers.
- `leadscorer.scoring.basic` -- generic, parametrized cross-reference and scoring logic: match a property to its permits, check whether any permit looks like the retrofit already happened, score qualifying properties by age + size, and rank them.

It intentionally does not include any real scraping targets, client identifiers, age thresholds, retrofit keywords, or hosting-provider-specific wiring (e.g. Supabase). Those live in a paid/full deployment layer that installs this package as a dependency and adds the client-specific pieces on top.

## Real scrapers live in the full repo

This public package still ships no real scraping targets by design (see "What this is" above) -- but real ones do exist now, in [commercial-property-lead-scorer-full](../commercial-property-lead-scorer-full): a property-assessment scraper against Maryland's Socrata open-data API (Anne Arundel County commercial parcels) and a permit scraper against Anne Arundel County's Accela permit portal. Both were built only after manually inspecting the real portal first (per the same data-source-refinement workflow used for Tool 1's AACPS scraper) -- Socrata turned out to be a documented, queryable open-data API rather than an HTML portal, worth checking for before assuming a scraper is the only option for a government data source. `scripts/run_scraper.py` here still demonstrates the generic framework against a small hardcoded synthetic dataset, independent of either real scraper.

## Install

Requires Python >=3.11 and a Postgres database.

```bash
pip install -e .
# or, with test dependencies:
pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and fill in your own values:

```bash
cp .env.example .env
```

`DATABASE_URL` is the preferred way to configure the connection; if it's unset, the standard `PGHOST`/`PGPORT`/`PGDATABASE`/`PGUSER`/`PGPASSWORD` variables are used instead.

## Run migrations

```bash
python scripts/migrate.py
```

This applies every SQL file under `src/leadscorer/migrations/` in order: `001_init_schema.sql` (creates `properties` and `permits`), `002_candidate_snapshots.sql` (novelty-gate history), `003_occupancy_checks.sql` (cached live occupancy checks), and `004_add_needs_review.sql` (`needs_review`/`review_reason` on `properties`). Every migration is written with `if not exists` guards, so it's safe to rerun.

## Run the demo scraper

```bash
python scripts/run_scraper.py --client-id demo
```

This runs two template scraper subclasses that read from small hardcoded in-memory datasets -- not a real portal -- upserts the results, then scores and prints a ranked candidate list using example threshold/keyword values. It's meant to be a working, runnable demonstration of the full framework end to end (including the scoring/ranking layer), and a reference for what real scrapers' `fetch`/`parse`/`normalize` methods should look like.

## How the pieces fit together

- **`leadscorer.scrapers.base.BasePropertyScraper` / `BasePermitScraper`** -- subclass once per portal type per source kind. `fetch()` retrieves raw content, `parse()` turns it into a list of raw record dicts, `normalize()` turns one raw record into a `PropertyRecord`/`PermitRecord`. `run()` orchestrates all three.
- **`leadscorer.normalize.schema.PropertyRecord` / `PermitRecord`** -- the normalized shapes every scraper must produce.
- **`leadscorer.db.client.upsert_property` / `upsert_permit`** -- write to Postgres, keyed on the source's own stable identifier (`parcel_id` / `permit_number`). No fuzzy-match tier -- see the module docstring for why that's a deliberate difference from Tool 1, not a missing feature.
- **`leadscorer.scoring.basic`** -- the cross-reference and scoring layer:
  - `match_permits_to_property` links a property to its permits (by `parcel_id` if both sources expose one, falling back to a normalized address match).
  - `has_retrofit_permit` checks whether any linked permit's type/description matches a caller-supplied keyword list.
  - `score_property` applies two hard qualifying conditions (no retrofit permit on file, and a known construction/renovation year older than a caller-supplied threshold) and, for properties that qualify, a continuous weighted score combining building age and square footage -- so results are a ranked list, not a flat yes/no filter. `size_score` treats unknown/zero square footage as neutral (0.5), not smallest-possible (0.0) -- a real assessment source can easily have a construction year on file with no square-footage figure, and scoring that the same as a confirmed-tiny building would be wrong.
  - `rank_candidates` runs this over every property/permit pair for a client and returns the qualifying candidates sorted highest-score-first. Ties break first on `active_trader_license` (candidates without one rank higher -- an active retail license is a mild deprioritization signal, not a scoring input), then on square footage.
- **`leadscorer.snapshot`** -- novelty-gate support: `candidate_snapshot_fields`/`diff_candidate_snapshots` diff a ranked candidate list against a prior run's snapshot (persisted via `leadscorer.db.client.save_candidate_snapshot`/`save_candidate_dropouts`) so a digest can report only what's newly qualifying or newly dropped off, not the full list every time.
- **`leadscorer.occupancy`** -- `select_parcels_needing_check` decides which currently-qualifying candidates need a fresh live occupancy check this run (never checked before, or the last check aged past a refresh window), bounding how often an external live-occupancy source needs to be hit.
- **`PropertyRecord.needs_review`/`review_reason`** -- set directly by a scraper's own `normalize()` (unlike Tool 1's DB-computed `needs_review`, since this tool has no fuzzy-match tier to derive a review-worthiness signal from) when a required field comes back missing or unparseable, so a bad record surfaces for a human instead of silently shipping something unusable.

A downstream deployment (like the full/paid repo) adds concrete scraper subclasses for real portals, the client's actual age threshold and retrofit keywords, client_id-tagged wiring, and digest integration on top -- without needing to touch or fork this package's code.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Covers the pure scoring/cross-reference functions (`age_score`, `size_score`, `has_retrofit_permit`, `match_permits_to_property`, `score_property`, `rank_candidates`), the novelty-gate diff logic (`diff_candidate_snapshots`), the occupancy-check scoping logic (`select_parcels_needing_check`), and `PropertyRecord`/`PermitRecord` schema validation -- all testable without a live database or a real scraped portal.
