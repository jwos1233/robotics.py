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

Phase 0 ran on 2026-08-19 once the build environment's network policy was
opened. Findings below are **live-verified** unless marked otherwise.

| # | Item | Status |
|---|---|---|
| 1 | US Census imports | **VERIFIED with real data.** Key required. Piece counts. Aggregate rows mixed in. |
| 2 | Eurostat Comext | **VERIFIED.** Keyless, SDMX 2.1. **No supplementary unit — weight only.** |
| 3 | TARIC cycloid gear provision | **RESOLVED: duty only.** Comext has no TARIC-level dataset. |
| 4 | Japan export statistical codes | **RESOLVED: deprioritise.** No ball/roller screw code exists. |
| 5 | JMTBA monthly breakdown | **VERIFIED.** Machine-type orders are a paid product; free monthly data gives NC grinding *production*. |
| 6 | e-Stat / METI `statsDataId`s | not yet checked — needs `ESTAT_APP_ID` |
| 7 | China NBS easyquery | **BLOCKED.** HTTP 403, IP-level block at the NBS end. |
| 8 | Equity price coverage | **Stooq and Yahoo both ruled out** (bot challenge / datacenter IP block). EODHD reachable, needs a plan. |
| 9 | FX to USD | **VERIFIED.** ECB keyless SDMX covers 11 of 12. **TWD not published.** |
| 10 | ACWI / URTH benchmark | blocked behind item 8 — no reachable free source found |

### The two findings that change the design

**The US and EU unit values are not the same measurement.** USITC reports
HTS 8483.40.80.00 with unit of quantity `No.`, a piece count, so the US unit
value is dollars per *screw*. Comext returns exactly two indicators for CN
8483.40.30 — `QUANTITY_IN_100KG` and `VALUE_IN_EUROS` — with no supplementary
unit, so the EU unit value can only be euros per *kilogram*. These must never
be compared on level, shared on an axis, or averaged. The EU figure also
drifts with product mix: a shift toward larger screws moves it with no price
change at all. Cross-check the two jurisdictions on value and growth rate
only.

**The JMTBA machine-type order split is behind a paywall.** No free monthly
release carries it — not the English NOTES, not the Japanese 確報. JMTBA sells
the 受注確報 monthly package by email at JPY 20,000/year. What is free and
monthly is NC grinding machine *production* from the 主要統計 PDF, which is a
coincident read on output rather than a forward read on capacity being
ordered, and there is no gear-cutting split in the free data at all.

### Japan exports add nothing for screws — but may for reducers

Japan's export statistical subdivisions under 8483.40 are `-100` CVTs,
`-200` gears, `-300` gear transmissions and `-900` other. Ball screws and
roller screws are named in the heading but have **no code of their own**;
they fall into `-900` "other". The exporter side is therefore *coarser* than
the US import side for this node, and item 4 is deprioritised as the brief
anticipated.

Worth noting for a different node: `-300` 歯車伝動機 (gear transmissions) is a
separate line reported in both units and kilograms, which is a plausible
instrument for **Precision Reducers** — the node Nabtesco and Harmonic Drive
sit in. Not yet evaluated.

### Free equity sources are ruled out, on access rather than coverage

Yahoo Finance would have solved everything — the full roster, ACWI, and the
TWD gap — but it returns HTTP 429 to every request from a datacenter IP,
including AAPL, with a browser User-Agent and the cookie/crumb handshake.
**Railway is cloud infrastructure too**, so the scheduler would hit the same
wall; this is not a sandbox artefact. Separately, the v8 endpoint is
undocumented and Yahoo's terms do not permit automated collection for
redistribution, which is a standing risk for a published product.

Stooq serves a JavaScript browser-verification challenge. EODHD, by contrast,
is reachable from here and its API shape is confirmed working on the public
demo token, so it is the leading candidate and needs a paid plan to evaluate
per-ticker.

### The TWD gap

ECB daily reference rates are keyless, have deep history, and cover every
required currency except **TWD**. Seven Taiwanese constituents across six
baskets depend on it. Until a second FX source covers TWD, those names count
as unpriced rather than being carried at a guessed rate — which also drags
those baskets' `constituents_priced` ratio down, visibly, by design.

### The unit value is a mix indicator, not a price

Getting a piece count was the good outcome, but it is not sufficient. In a
single month, unit value across origins on HTS 8483.40.8000 spans **$0.45/unit
(Poland, 172,800 units) to $6,374/unit (Czech Republic, 7 units)** — a
14,000x spread. The line plainly carries commodity ball screws and large
specialist screws under one code.

A blended ASP over this line is therefore **not a price signal and must not be
published as one**. What is coherent is a per-origin series inside the
precision band, where Japan ($242), Taiwan ($242), Italy ($201) and Germany
($178) cluster within a factor of two, while Poland, Canada and Switzerland
sit two to three orders of magnitude below and are evidently a different
product. Even within one origin, a mix shift moves the number with no price
change at all.

### Two traps worth naming

**Aggregates are mixed into the country rows.** A single Census response
carries individual countries, economic groupings (EU, OECD, NATO, APEC),
continent aggregates (`4XXX EUROPE`) and a world total (`-`) with nothing
distinguishing them. Summing naively roughly triples the true figure. The
filter is pinned by a test that reconciles the 40 country rows exactly against
the TOTAL row.

**The Census API returns HTTP 200 with an HTML error page** when the key is
absent or inactive — not a 4xx, not JSON. Any fetcher that trusts the status code
will ingest an HTML error page as data. The saved fixture pins this.

### Contributing Phase 0 evidence

`tests/fixtures/README.md` lists exactly what each source needs, in priority
order, with the capture commands where they are known. Save real payloads
verbatim under `tests/fixtures/<source>/` and open a PR; parsers get written
against them and their tests skip until the payload lands, so the gap stays
visible rather than hidden.

Alternatively, allowing the source hosts through the build environment's
network policy lets Phase 0 be run directly. Each fetcher docstring records
what its own source still needs.

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
