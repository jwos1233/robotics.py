"""Equity prices, FX and benchmark.

STATUS: NOT IMPLEMENTED, and blocked on a decision Phase 0 was meant to make.

The ticker universe spans Japan, China A-shares, Hong Kong, Taiwan, Korea,
Germany, Sweden, France, Switzerland, the UK, Norway, Australia, Canada and
the US. Most free price APIs are US-only, which makes the price source the
binding constraint on the entire equity feature -- not an implementation
detail to settle later.

PHASE 0 FINDINGS SO FAR.

Stooq is NOT usable programmatically. Its CSV download endpoint serves a
JavaScript browser-verification challenge ("This site requires JavaScript to
verify your browser") instead of CSV, for every symbol tried across the US,
Japan, Taiwan, Korea and China, and resets the connection under repeated
requests. A browser User-Agent does not help. Driving a headless browser to
defeat a bot check daily is not a dependency worth taking. Ruled out.

Yahoo Finance is NOT viable, for two independent reasons.

  1. It blocks datacenter IPs. Every request returns HTTP 429 "Too Many
     Requests" -- on the first attempt, for AAPL, with a browser User-Agent,
     and with the cookie/crumb handshake. This is not per-request throttling
     we provoked; it is a block on cloud IP ranges. Railway is cloud
     infrastructure too, so the production scheduler would hit the same wall.
     A source that cannot run from a server cannot back a daily pipeline.
  2. There is no official public API. The v8 chart endpoint is undocumented
     and Yahoo's terms do not permit automated collection for redistribution.
     For a research product intended to be published, that is a standing
     risk independent of whether the block is ever lifted.

  This is a shame purely on coverage: Yahoo is the only free source that
  spans the whole roster plus ACWI and TWD=X. It does not matter, because it
  cannot be reached from a server.

EODHD is reachable from this infrastructure and its API shape is confirmed
working -- the public demo token returns real OHLCV for AAPL.US. Non-US
symbols return "Forbidden" only because the demo is limited to a handful of
US tickers, not because of an IP block. It therefore remains the leading
candidate and needs a paid plan to evaluate properly. Twelve Data and Tiingo
are untested for the same reason.

The question that matters is not "does the provider list the Taiwan exchange"
but "does it return 2049 TT". No provider is wired in and no source_symbol is
populated. Every security stays coverage_status='unavailable' and is excluded
from basket pricing until a provider is confirmed FOR THAT SECURITY.

FX: RESOLVED, with one gap. The ECB daily reference rate series
(data-api.ecb.europa.eu, SDMX, keyless) covers JPY, CNY, HKD, KRW, SEK, CHF,
GBP, NOK, AUD, CAD and USD against EUR -- 11 of the 12 needed.

  ** TWD IS NOT PUBLISHED BY THE ECB. **

  Seven Taiwanese constituents depend on it -- 2049 TT, 2317 TT, 2308 TT,
  2327 TT, 1101 TT, 4919 TT, 2382 TT -- spanning the Bearings, CNC Controls,
  Contract Manufacture, Passives, High-Rate Cells and BMS baskets. Without a
  second FX source for TWD those names cannot be converted to USD, and under
  the basket rules they must then count as unpriced rather than be carried at
  a stale or guessed rate.

  Rates are quoted per EUR, so a USD conversion goes through the EUR/USD
  cross rather than being read directly.

BENCHMARK: ACWI. SPY must never be substituted -- a ~70% non-US board measured
against a USD-only benchmark is a currency bet wearing a constraint costume.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from robotics_radar.ingest.base import (
    Fetcher,
    IngestError,
    NormalisedObservation,
    RawResponse,
    SeriesSpec,
)

REQUIRED_CURRENCIES = (
    "JPY", "CNY", "HKD", "TWD", "KRW", "EUR",
    "SEK", "CHF", "GBP", "NOK", "AUD", "CAD",
)


class EquityPriceFetcher(Fetcher):
    source_name = "equity_prices"

    def series_specs(self) -> Sequence[SeriesSpec]:
        # Equity prices land in `prices`, not in the constraint `series` table.
        return []

    def fetch(self, period: date) -> Iterable[RawResponse]:
        raise IngestError(
            "equity_prices: no provider selected. Phase 0 could not evaluate "
            "coverage for the non-US universe, and no security has a confirmed "
            "source_symbol."
        )

    def normalise(self, raw: RawResponse) -> Iterable[NormalisedObservation]:
        raise IngestError("equity_prices: parser awaits a selected provider.")
