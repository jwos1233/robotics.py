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

EODHD, Twelve Data and Tiingo remain unevaluated: each needs an account
before coverage can be tested against the roster, and the question that
matters is not "does it list an exchange" but "does it return this specific
ticker". No provider is wired in and no source_symbol is populated. Every
security stays coverage_status='unavailable' and is excluded from basket
pricing until a provider is confirmed FOR THAT SECURITY.

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
