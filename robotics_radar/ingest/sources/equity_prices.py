"""Equity prices, FX and benchmark.

STATUS: NOT IMPLEMENTED, and blocked on a decision Phase 0 was meant to make.

The ticker universe spans Japan, China A-shares, Hong Kong, Taiwan, Korea,
Germany, Sweden, France, Switzerland, the UK, Norway, Australia, Canada and
the US. Most free price APIs are US-only, which makes the price source the
binding constraint on the entire equity feature -- not an implementation
detail to settle later.

Phase 0 could not evaluate Stooq, EODHD, Twelve Data or Tiingo for coverage,
cost, rate limits or history depth, so no provider is wired in and no
source_symbol is populated. Every security is seeded coverage_status
='unavailable' and is excluded from basket pricing until a provider is
confirmed for it. Guessing a provider's symbol format is how you silently
price the wrong instrument.

One weak signal worth carrying forward: Stooq is documented as covering
Poland, the US, Japan, Germany and Hungary with no official API, and is not
documented for China, Taiwan or Korea. Consistent with the expectation that
A-shares and smaller Japanese lines are where free sources fail.

FX: needs one source with full free daily history for JPY, CNY, HKD, TWD, KRW,
EUR, SEK, CHF, GBP, NOK, AUD and CAD. Note that ECB reference rates do not
cover every one of those, which is why the candidate must be checked against
the full list rather than assumed.

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
