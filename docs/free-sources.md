# Free data sources — what was tested and what it gives

Every entry was tested live from cloud infrastructure on 2026-08-19. "Free"
here means no payment; some sources still need a free registration.

## Verified working, no key

| Source | Gives | Status |
|---|---|---|
| **Eurostat Comext** | EU trade at CN8, monthly, since 1988 | **Implemented.** `DS-045409`, SDMX 2.1 |
| **USITC HTS** | US tariff schedule, units of quantity | Used to settle the piece-count question |
| **ECB SDMX** | Daily FX reference rates, deep history | 11 of 12 currencies — **no TWD** |
| **Taiwan TWSE OpenAPI** | Daily closes for all TWSE-listed stocks | **All 7 Taiwanese roster tickers returned** |
| **UN Comtrade (public preview)** | Trade at **HS6**, annual | Works keyless; HS6 too coarse for screws |
| **JMTBA (free releases)** | NC grinding machine *production*, monthly | Orders by machine type are paid |
| **Japan Customs export schedule** | Export statistical subdivisions | No ball/roller screw code exists |

## Verified working, free registration

| Source | Gives | Status |
|---|---|---|
| **US Census trade API** | US imports at HTS10 by origin, monthly | **Implemented.** Key must be *activated* |
| Japan e-Stat | METI production statistics | Needs `ESTAT_APP_ID`; not yet tested |
| Korea data.go.kr | Korean trade statistics, 10-digit HS | Needs a key; not yet tested |

## Ruled out — access, not coverage

These fail at the network layer, where no amount of engineering helps. All
three would fail from Railway too, since it is also cloud infrastructure.

| Source | Failure |
|---|---|
| **Yahoo Finance** | HTTP 429 on every request incl. AAPL — datacenter IP block. Also no official API, and terms disallow automated collection |
| **Stooq** | JavaScript browser-verification challenge instead of CSV |
| **China NBS** | HTTP 403 echoing the client IP — IP-level block |

## Exchange-native APIs: mostly unreachable from here

Tested for a per-exchange strategy. Only Taiwan is currently reachable; the
rest are blocked by this environment's network allowlist, not by the venues
themselves, so they remain untested rather than ruled out.

| Host | Market | Status |
|---|---|---|
| `openapi.twse.com.tw` | Taiwan | **Reachable, keyless, working** |
| `api.twelvedata.com` | multi-market | Reachable; demo key works for US only, needs a free key |
| `api.jquants.com` | Japan (JPX official) | blocked by allowlist — untested |
| `push2his.eastmoney.com` | China A / HK | blocked by allowlist — untested |
| `hq.sinajs.cn` | China A | blocked by allowlist — untested |
| `data.krx.co.kr` | Korea | blocked by allowlist — untested |
| `www.hkex.com.hk` | Hong Kong | blocked by allowlist — untested |
| `www.alphavantage.co`, `finnhub.io` | multi-market | blocked by allowlist — untested |
| `data.sec.gov` | US filings | blocked by allowlist — untested |

## TWSE gives more than prices

The Taiwan OpenAPI exposes 143 endpoints. Two matter here:

- `/exchangeReport/STOCK_DAY_ALL` — daily closes for every listed stock.
  Appears to be a **same-day snapshot**: no historical endpoint exists in the
  spec, so price history accumulates forward and cannot be backfilled.
- `/opendata/t187ap05_L` — **monthly revenue filings**, 1,085 companies, with
  month-on-month and year-on-year changes already computed.

The revenue feed is arguably the more valuable of the two, and it is a
CONSTRAINT-side signal rather than an equity one. Taiwanese listed companies
must file monthly revenue within 10 days of month-end, so for a name whose
business *is* the constraint, revenue is a direct fundamental read where the
share price is only a sentiment proxy.

The clearest case is **Hiwin (2049)**, one of the few listed pure-plays in
ball screws and linear guides. Its monthly revenue is a direct read on linear
motion demand:

| company | monthly revenue (TWD k) | YoY |
|---|---|---|
| Hiwin | 2,681,646 | +33.9% |
| Delta Electronics | 67,073,192 | +47.7% |
| Yageo | 16,131,188 | +51.5% |
| Nuvoton | 2,566,187 | +7.9% |

This belongs on the constraint side with `evidence_grade='disclosed'`, feeding
the Bearings & Linear Motion node — not in a basket. It is free, keyless and
monthly, which matches the board's cadence exactly.

## Promising, unresolved

- **PRODCOM** (`DS-059367`, `DS-059368`, same Comext API): EU *production* by
  product, a different and possibly better instrument than trade flow for
  several nodes. The dataflow exists with dimensions
  `freq/reporter/product/indicators`, but the product codelist could not be
  retrieved from the paths tried, so no series is confirmed.
- **FRED**: US producer price indices for bearings and power transmission
  equipment. Free with a key. Not yet tested.

## The strategic point

Taiwan changed the picture. A keyless exchange-native API returned every
Taiwanese name on the roster, which makes **per-exchange free sources** a real
alternative to one paid global provider — at the cost of one adapter per
market, each able to change independently.

Two caveats before betting on it. TWSE's `STOCK_DAY_ALL` appears to be a
same-day snapshot, so history would accumulate forward rather than backfill;
a historical endpoint was not confirmed. And the same trick has to work for
Japan, Korea, China A-shares and Hong Kong before the equity layer is
actually unblocked — Taiwan alone prices no basket, because every basket it
touches also holds names from other markets.
