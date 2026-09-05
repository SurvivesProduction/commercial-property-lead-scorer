# commercial-property-lead-scorer

Public template: cross-references commercial property assessment records against permit history to surface buildings that are old enough to plausibly still have outdated infrastructure (e.g. pre-LED lighting) and have no permit on file showing a retrofit was ever done -- a scored, ranked lead list rather than a flat filter.

This is the generic/free version -- no real portal targets, no client-specific age thresholds or retrofit keywords, no alerting. See the full build for a real client deployment: [commercial-property-lead-scorer-full](../commercial-property-lead-scorer-full).

## What this is

`leadscorer` is a small, reusable framework for turning "a property assessment source + a permit source" into a ranked list of retrofit-lead candidates:

- `BasePropertyScraper` / `BasePermitScraper` -- abstract classes defining the `fetch -> parse -> normalize` pipeline each concrete scraper implements (two, not one, since this tool cross-references two independent source types).
- `PropertyRecord` / `PermitRecord` -- the schemas each scraper normalizes into.
- A Postgres client (`leadscorer.db.client`) that upserts both record types keyed on their real, stable native identifiers (parcel/account number, permit number) -- see that module's docstring for why this doesn't need Tool 1's fuzzy-match dedup tiers.
- `leadscorer.scoring.basic` -- generic, parametrized cross-reference and scoring logic: match a property to its permits, check whether any permit looks like the retrofit already happened, score qualifying properties by age + size, and rank them.

It intentionally does not include any real scraping targets, client identifiers, age thresholds, retrofit keywords, or hosting-provider-specific wiring (e.g. Supabase). Those live in a paid/full deployment layer that installs this package as a dependency and adds the client-specific pieces on top.

## Why no real scraper yet

The real Maryland source portals (property tax assessment -- likely Maryland SDAT or a county assessment site -- and permit history, likely a county/city permit portal) haven't been manually inspected yet. Per the same data-source-refinement workflow used for Tool 1's AACPS scraper, a scraper doesn't get built against a real portal until that inspection (static HTML vs. JS-rendered, search-form gating, CAPTCHAs, registration walls) has actually happened -- guessing at portal structure produces scrapers that silently break or silently misparse. `scripts/run_scraper.py` demonstrates the full framework against a small hardcoded synthetic dataset instead.

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

This applies every SQL file under `src/leadscorer/migrations/` (currently just `001_init_schema.sql`, which creates `properties` and `permits`) in order. Every migration is written with `if not exists` guards, so it's safe to rerun.

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
  - `rank_candidates` runs this over every property/permit pair for a client and returns the qualifying candidates sorted highest-score-first.

A downstream deployment (like the full/paid repo) adds concrete scraper subclasses for real portals, the client's actual age threshold and retrofit keywords, client_id-tagged wiring, and digest integration on top -- without needing to touch or fork this package's code.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Covers the pure scoring/cross-reference functions (`age_score`, `size_score`, `has_retrofit_permit`, `match_permits_to_property`, `score_property`, `rank_candidates`) against synthetic data, and `PropertyRecord`/`PermitRecord` schema validation -- all testable without a live database or a real scraped portal.
