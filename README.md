# Robotics Constraint Radar

A research product tracking supply-chain bottlenecks in the humanoid and
mobile-manipulation buildout, plus an equity baskets layer mapping listed
companies to each constraint.

**Status: Phase 1 (schema) and Phase 3 (API) are built and verified. Phase 0
(source verification) did not run, and Phase 2 (ingestion) is therefore
deliberately unimplemented.** Every fetcher refuses rather than guessing an
endpoint. See [Phase 0](#phase-0-what-is-verified-and-what-is-not).

## What this is, and what it is not

Robotics has no spot price series. Nothing rents, nothing trades, there is no
roller screw print. The constraint side rests on two substitutes:

1. **Customs unit values** — value divided by quantity on a tariff line, acting
   as a synthetic monthly price series.
2. **Machine-tool order data** — read one layer *below* the visible constraint.
   Grinding machines gate roller screw and reducer output, so grinding order
   intake leads actuation capacity.

Nothing in robotics is tight today; unit volumes are trivial. This is a forward
map of what breaks first as volume scales, **not** a live tightness gauge.
Cadence is monthly.

The equity layer has a matching honesty problem: almost no listed name derives
more than low single-digit revenue from humanoids. `purity_grade` is a
first-class field and travels with every basket number the API returns.

## Quickstart

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"
cp .env.example .env          # DATABASE_URL is REQUIRED; there is no default
python -m robotics_radar.preflight    # verifies the database is configured and up
alembic upgrade head
python -m robotics_radar.seeds.load        # nodes, securities, baskets
python -m robotics_radar.scheduler.run register   # series rows from fetcher specs
uvicorn robotics_radar.api.main:app --reload
```

Tests:

```bash
pytest                        # 46 unit tests, no database needed
DATABASE_URL=... pytest       # +19 API integration tests
```

## API

Read-only JSON. OpenAPI at `/openapi.json`, docs at `/docs`.

| Endpoint | Notes |
|---|---|
| `GET /nodes`, `GET /nodes/{id}` | `severity` and `break_point_tier` are always `null` |
| `GET /series?node=&geography=&flow=` | every response carries `methodology_note` and `known_limitations` |
| `GET /series/{id}/observations?from=&to=&vintage=` | defaults to latest vintage |
| `GET /baskets?bucket=&purity=&demand_side=` | every response carries `purity_grade` and an `interpretation` |
| `GET /baskets/{id}` | thesis, caveat, roster, linked node **by name only** |
| `GET /baskets/{id}/returns?window=` | `breadth`, `breadth_flag`, `constituents_priced`/`total` |
| `GET /baskets/overlap` | shared-membership matrix |
| `GET /health` | Railway health check; reports database reachability |

`GET /` returns a small index (`name`, `docs`, `openapi`) — that is the whole
response, not a truncated page. There is no frontend yet. Start at `/docs`.

### Deliberately absent

These are omissions, not gaps:

- **No "what flipped this week" banner.** It needs constraint state changes,
  which need severity scoring, which does not exist.
- **No constraint score on a basket.** Baskets link a node by name only.
- **No top-mover attribution.** `top_movers()` exists in the computation layer
  and returns `None` unless coverage is complete for that basket. A top mover
  computed on partial coverage is wrong and looks precise.

## Basket computation

- **Equal weight, never cap weight.** Cap weighting collapses several baskets
  into a single mega-cap. Pinned by test.
- **USD before returns.** A return averaged across mixed local currencies is
  not a number.
- **Benchmark is ACWI.** SPY is wrong for a ~70% non-US board — a JPY basket
  against a USD benchmark is a currency bet wearing a constraint costume.
- **breadth** = share of priced constituents moving with the basket. Below 0.5
  the API sets `breadth_flag`.
- **Staleness**: constituents are aligned to the benchmark calendar, stale
  closes forward-filled for at most 3 sessions, then the constituent is marked
  stale and dropped from the return rather than silently carried.
- `constituents_priced` vs `constituents_total` is part of the number's
  meaning, not diagnostics.

## Phase 0: what is verified, and what is not

Phase 0 **could not run**. This build environment's network policy blocks all
outbound HTTPS except GitHub and package registries; every data host
(`api.census.gov`, `ec.europa.eu`, `jmtba.or.jp`, `data.stats.gov.cn`,
`stooq.com`, and the rest) fails at CONNECT with a 403 from the egress proxy.
WebSearch was the only working channel and returns summaries, not payloads.

**No API call was made against any source.** Nothing below is live-verified.

| # | Item | Status |
|---|---|---|
| 1 | US Census imports | Endpoint documented. **Quantity basis for HTS 8483.40.8000 UNRESOLVED.** |
| 2 | Eurostat Comext | `DS-045409`, CN8 monthly, keyless — documented only. **Supplementary unit for CN 8483.40.30 UNRESOLVED.** |
| 3 | TARIC cycloid gear provision | **UNRESOLVED** — cannot tell whether it carries queryable volume |
| 4 | Japan export statistical codes | **UNRESOLVED** |
| 5 | JMTBA monthly breakdown | **UNCONFIRMED** — search suggests the monthly release carries the machine-type split, but not from the file itself |
| 6 | e-Stat / METI `statsDataId`s | **UNRESOLVED** — not guessed |
| 7 | China NBS easyquery | **UNRESOLVED** |
| 8 | Equity price coverage | **UNRESOLVED** — the per-ticker unavailable list could not be produced |
| 9 | FX to USD | **UNRESOLVED** |
| 10 | ACWI / URTH benchmark | **UNRESOLVED** |

Two consequences worth stating plainly:

- **Items 1 and 2 are the same question twice.** If Census reports quantity by
  weight only, and CN 8483.40.30 carries no supplementary unit, both "unit
  value" series are $/kg rather than $/unit. That drifts with product mix and
  is a materially weaker instrument than the design assumes. Settle this before
  ingestion, not after.
- **Item 5 is the most load-bearing series on the board.** If the machine-type
  split is annual-only, the cascade argument weakens substantially.

To unblock, the environment's network policy needs to allow the source hosts;
see `deploy/cron.md` and the fetcher docstrings, each of which records exactly
what its source still needs.

## Schema notes

Postgres, Alembic. Point-in-time correct: customs data revises, so
`observations` is append-only on `UNIQUE (series_id, period_start,
vintage_date)` and a `latest_observations` view sits on top. `release_date`,
`vintage_date` and `retrieved_at` are three different facts and are never
conflated. `raw_payloads` keeps every response verbatim — being able to prove
where a number came from is the product.

### Deviations from the specified schema

Each of these is a judgement call, flagged rather than made silently:

1. **`series.partner_geography` added.** The brief requires measuring imports
   *by country of origin*, and `geography` alone cannot express a
   reporter/partner pair. Without this the by-origin requirement is
   inexpressible.
2. **`baskets.bucket` made nullable.** Demand-side baskets are not constraints
   and do not belong in a constraint bucket. They carry `bucket = NULL` and
   `is_demand_side = true`.
3. **`securities.data_source` and `source_symbol` made nullable**, and left
   NULL for every row. No price provider is confirmed, and a guessed symbol
   silently prices the wrong instrument.
4. **`securities.exchange_mic` nullable**, and NULL for US listings. The
   specific venue (XNYS vs XNAS) was not verifiable offline and is not guessed.
   Non-US MICs derive deterministically from the Bloomberg country suffix.
5. **`fx_rates` and `benchmark_prices` tables added.** Both are implied by "convert
   to USD" and "benchmark is ACWI" but were not in the listed schema. Keeping
   FX separate means a missing rate is diagnosable as an FX gap rather than
   looking like a missing price.
6. **Two demand nodes added** (`Humanoid OEM Demand`, `Mobile Manipulation
   Demand`) so the demand baskets have something to link to. They carry
   methodology notes marking them as reference nodes, not constraints.

### Seed metadata requiring verification

Seeded structure is complete: 26 nodes, 143 securities, 25 baskets, 163
memberships. `severity`, `break_point_tier`, `source_symbol` and `data_source`
are NULL everywhere by design. The following still need a human check:

- **`6141 GY` is an anomaly in the source list.** `6141` is a Tokyo local code
  (DMG Mori Co Ltd), but the suffix says Germany. It is seeded verbatim with
  the suffix-derived German attributes and the name field flags the conflict.
  Someone should decide whether it was meant to be `6141 JP`.
- **Company names were populated offline** from knowledge, not from a reference
  source. They are display labels only — nothing keys off them — but a few of
  the smaller China A-share lines (`603009`, `300100`, `605133`) are worth
  confirming against a security master.
- **US listing venues** are NULL pending a reference source, as above.

## Deployment

Railway, two services from one repo. `web` runs preflight, migrations, the
seed, series registration, then uvicorn with the health check on `/health`;
`scheduler` runs one cron job per source.

Seeding runs on every boot rather than as a one-off step, so the deployed
reference data always matches the repo. It is idempotent and guarded by a
Postgres advisory lock, so overlapping boots across replicas cannot
double-write. Schedules and their (provisional) release-lag assumptions are in
`deploy/cron.md`. Logging is structured JSON to stdout.

### `DATABASE_URL` must be set on every service

Adding the Postgres plugin exposes `DATABASE_URL` on the **Postgres service
only**. It is not inherited. Each service needs its own reference:

> Railway -> service -> Variables -> New Variable
> `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`

Set it on both `web` and `scheduler`. There is deliberately no default in
`config.py`: a localhost fallback would turn an unset variable into a
"connection refused to 127.0.0.1" traceback from inside the driver, which
reads like a broken database instead of a missing setting.

Three connection shapes are accepted, in order: `DATABASE_URL`; then
`PGHOST`/`PGUSER`/`PGDATABASE` (+ `PGPORT`, `PGPASSWORD`) composed into a URL;
then `DATABASE_PUBLIC_URL`, which works but leaves the private network and is
billed as egress, so preflight warns when it falls through to it.

The preflight step runs before migrations and separates the failure cases — a
missing configuration exits 78 after printing the database-related variable
*names* it can see (never their values), which distinguishes "Postgres is not
linked to this service" from "linked, but `DATABASE_URL` was never
referenced". A database that is simply not up yet is retried with backoff for
roughly 40 seconds before exiting 75.
