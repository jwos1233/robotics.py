# Railway cron schedules

Two services share this repo:

| Service | Start command |
|---|---|
| `web` | `python -m robotics_radar.preflight && alembic upgrade head && uvicorn robotics_radar.api.main:app --host 0.0.0.0 --port $PORT` |
| `scheduler` | one cron job per source, commands below |

## Required variables (do this first)

**`DATABASE_URL` is not inherited automatically.** Adding the Postgres plugin
exposes it on the *Postgres service only*. Every other service must reference
it explicitly, or the container starts, finds no database, and dies:

> Railway -> service -> Variables -> New Variable
> `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`

Set it on **both** `web` and `scheduler`. Substitute the real Postgres service
name if it is not `Postgres`.

If the reference does not resolve — a typo in the service name resolves to
nothing rather than raising — the container sees no variable at all, which
looks identical to never having set it.

Three connection shapes are accepted, in order:

1. `DATABASE_URL`
2. `PGHOST` + `PGUSER` + `PGDATABASE` (+ `PGPORT`, `PGPASSWORD`), composed
3. `DATABASE_PUBLIC_URL` — works, but leaves the private network and is billed
   as egress, so preflight logs a warning when it falls through to this

The preflight step runs before migrations and reports which source it used. If
none is available it prints the database-related variable **names** it can see
(never their values, several are credentials), which distinguishes "Postgres
is not linked to this service at all" from "linked, but `DATABASE_URL` was
never referenced". Missing config exits 78; a database that is merely not up
yet is retried with backoff for about 40 seconds and then exits 75.

`web` has the health check wired to `/health`. The scheduler service runs no
long-lived process; each cron job is a one-shot invocation that exits.

## Jobs

All times UTC.

| Source | Cron | Command |
|---|---|---|
| Census imports | `0 14 10 * *` | `python -m robotics_radar.scheduler.run census` |
| Comext imports | `0 14 17 * *` | `python -m robotics_radar.scheduler.run comext` |
| JMTBA orders | `0 6 9 * *` | `python -m robotics_radar.scheduler.run jmtba` |
| China NBS output | `0 6 18 * *` | `python -m robotics_radar.scheduler.run nbs` |
| Equity prices | `0 23 * * 1-5` | `python -m robotics_radar.scheduler.run equity` |

## The lags are provisional

These schedules encode a *guess* at each source's release calendar, because
Phase 0 could not reach any of the providers to confirm one. Each needs
checking against the real release calendar before it can be trusted:

- **Census** — monthly FT-900 lands roughly five weeks after month end. The
  10th is a conservative placement, not a verified one.
- **Comext** — placed later than Census on the assumption of a longer lag.
  Unverified.
- **JMTBA** — "early month" per the brief; the preliminary figure and the
  final figure land on different days and only one of them is what we want.
- **NBS** — mid-month, and note that China suppresses January/February
  monthly detail in favour of a combined print. The fetcher will need to
  handle that rather than record a gap.
- **Equity** — 23:00 UTC is after the US close but *before* the next Asian
  open, which is the only window where every venue has a settled prior close.
  Confirm against each venue's calendar.

Each job re-runs safely: fetchers are idempotent and revisions append as new
vintages, so a duplicate run costs nothing. Running a job late is therefore
much cheaper than running it early against unpublished data.

## Backfill

Pass an explicit period to reload one month:

```
python -m robotics_radar.scheduler.run census --period 2026-03
```

Register series rows (idempotent, creates no observations):

```
python -m robotics_radar.scheduler.run register
```
