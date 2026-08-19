# Phase 0 fixtures

Drop real payloads here and the parsers get written against them. Nothing in
this directory is generated — every file must be a verbatim response or file
from the actual source, saved unedited. A hand-tidied payload defeats the
purpose: the parser needs to meet the real thing, including whatever is ugly
about it.

Naming: `<source>/<what>_<period>.<ext>`, e.g. `census/imports_2026-06.json`.

## Priority

Two answers gate the design. Everything else can follow later.

**P0 — the quantity basis.** Does the roller-screw line report quantity as a
piece count or by weight? If it is weight, both customs "unit value" series
are $/kg rather than $/screw, they drift with product mix, and they are a
materially weaker instrument than the board assumes. This affects items 1 and
2 identically.

**P0 — the JMTBA cadence.** Does the *monthly* release carry the
by-machine-type split (Grinding Machines, Gear Cutting & Finishing Machines),
or is that split annual-only? The cascade argument rests on it.

**P1** — everything else below.

---

## 1. US Census imports → `census/`

Unverified candidate call. Run it; if it errors, save the error — a 400 with
a message about an unknown variable is itself useful information.

```bash
curl -s 'https://api.census.gov/data/timeseries/intltrade/imports/hs?get=CTY_CODE,CTY_NAME,I_COMMODITY,GEN_VAL_MO,GEN_QY1_MO,UNIT_QY1&I_COMMODITY=8483408000&time=2026-06&COMM_LVL=HS10' \
  > tests/fixtures/census/imports_2026-06.json

curl -s 'https://api.census.gov/data/timeseries/intltrade/imports/hs/variables.json' \
  > tests/fixtures/census/variables.json
```

What I need out of it: whether an API key is required at this volume, the real
variable names for value/quantity/quantity-unit, and **what `UNIT_QY1`
actually contains for this line**.

## 2. Eurostat Comext → `comext/`

Same exercise for CN `84834030`, monthly, by partner. The dissemination API is
documented at `ec.europa.eu/eurostat/api/comext/dissemination` with dataset
`DS-045409`, but I could not confirm the request shape — so whatever call you
land on, save both the URL you used and the response.

Specifically needed: whether this CN line carries a **supplementary unit** (a
piece count) or only value and weight.

## 3. TARIC cycloid gear provision → `comext/`

The provision for cycloid gear sets "of a kind used in robot arms" (50–9,000
Nm, ratios 1:50–1:475, lost motion under one arc minute, efficiency above
80%). The question is narrow: **does it surface as a separately reported
statistical line carrying queryable trade volume, or does it exist only for
duty purposes?** A screenshot of the TARIC measure page is fine here. If it
carries volume it is the best series on the board and gets promoted.

## 4. Japan export statistical codes → `estat/`

The 3-digit subdivision under 8483.40 on the **export** list
(`customs.go.jp/yusyutu/`, not the import schedule). Framed narrowly: does the
exporter side add anything the import side does not already give us? If not,
say so and I will deprioritise it rather than build it.

## 5. JMTBA orders → `jmtba/`  ← P0

The most recent **monthly** release file, whatever format it comes in (PDF and
Excel both fine — commit the file itself, it is small). What I need to see:

- whether "Grinding Machines" and "Gear Cutting & Finishing Machines" appear
  as separate lines in the *monthly* file
- whether order backlog and the price index are in the monthly release
- the URL pattern, so the fetcher can construct next month's

## 6. e-Stat / METI production → `estat/`

Requires a registered `appId`. What I need are the `statsDataId`s for the
Current Survey of Production (生産動態統計) series covering reduction gears,
servo/small motors, bearings and industrial robots. A search response listing
them is enough — I will not guess these.

## 7. China NBS → `nbs/`

One `data.stats.gov.cn` easyquery response for monthly industrial robot
output, plus a note on whether it looked stable or flaky. If the endpoint is
unusable, say so and I will plan the HTML-scrape fallback instead.

## 8. Equity prices → `equity/`

This one is a **decision more than a payload**. The universe spans 14
countries and most free APIs are US-only, so the provider choice is the
binding constraint on the whole equity feature. Either:

- tell me which provider you are willing to pay for, and I will check coverage
  against the 143-name roster and report exactly which tickers cannot be
  sourced; or
- save one response per candidate for a hard case — `6324 JP`, `688017 CH`,
  `2049 TT`, `005490 KS` — and I will grade them.

China A-shares and the smaller Japanese lines are where free sources are
expected to fail. Do not assume full coverage.

## 9. FX → `fx/`

One daily-history response covering JPY, CNY, HKD, TWD, KRW, EUR, SEK, CHF,
GBP, NOK, AUD, CAD against USD. ECB and exchangerate.host are candidates, but
ECB does not publish every one of those, so the full list has to be checked
rather than assumed.

## 10. Benchmark → `equity/`

Daily history for ACWI (or URTH). Not SPY — a ~70% non-US board measured
against a USD-only benchmark is a currency bet wearing a constraint costume.
