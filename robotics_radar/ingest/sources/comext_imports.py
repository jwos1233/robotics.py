"""Eurostat Comext monthly imports, CN 8483.40.30 (ball or roller screws), by partner.

STATUS: NOT IMPLEMENTED, but Phase 0 has now VERIFIED this source live.

What is settled (given, not re-derived):
  * EU CN 8483.40.30 is "Ball or roller screws"; 8483.40.90 is the residual.
  * Measured by partner country for the same reason as the US line.

Verified live, keyless:
  * Base: ec.europa.eu/eurostat/api/comext/dissemination
  * SDMX 2.1 data path works and SDMX-CSV is the easiest format:
      /sdmx/2.1/data/DS-045409/{freq}.{reporter}.{partner}.{product}.{flow}.
      with startPeriod / endPeriod. Trailing empty position = wildcard.
    Dimension order is freq.reporter.partner.product.flow.indicators;
    flow 1 = import. Real data confirmed for reporter DE, partner JP,
    product 84834030.
  * Unfiltered queries are refused with HTTP 413 naming the estimated row
    count against a 5,000,000 cap, so every request must be filtered.

  * SUPPLEMENTARY UNIT RESOLVED -- and the answer is NO. Wildcarding the
    indicators dimension for CN 84834030 returns exactly two indicators:
    QUANTITY_IN_100KG and VALUE_IN_EUROS. There is no piece count.

    CONSEQUENCE, and it is a significant one: the EU unit value can only ever
    be EUR per kilogram, while the US unit value on the matching line is
    dollars per SCREW. The two are not the same measurement and must never be
    compared to each other directly, plotted on a shared axis, or averaged.
    A EUR/kg series also drifts with product mix -- a shift toward larger
    screws moves it with no price change at all.

TARIC CYCLOID GEAR PROVISION -- RESOLVED, and the answer is no.
  The provision for cycloid gear sets "of a kind used in robot arms" exists
  for DUTY PURPOSES ONLY and carries no queryable trade volume. Verified two
  ways: Comext accepts CN8 product codes (84834090 returns data) but rejects
  a 10-digit TARIC code with an HTTP 400 fault, and the full Comext dataflow
  list is 11 datasets whose finest product granularity is CN8. No TARIC-level
  dataflow exists. It therefore cannot be promoted to a primary source, and
  robot-arm cycloid gears stay invisible inside CN 8483.40.90 "other".

OPPORTUNITY SPOTTED, not yet evaluated: the same API serves PRODCOM datasets
(DS-059367 "Production vendue, exportations et importations par liste
PRODCOM", DS-059368 "Production totale"). These are EU PRODUCTION statistics
by product, which is a different and possibly better instrument for several
constraint nodes than trade flow is. Worth a look before adding more customs
series.

Still open:
  1. Revision behaviour, so vintage_date is assigned correctly.
  2. Whether an EU-aggregate reporter is preferable to summing members.

CROSS-CHECK, NOT BLEND: this series and the US Census series measure the same
node in two jurisdictions. They are deliberately kept as separate series so
divergence between them is visible. Averaging them would hide exactly the
signal that divergence carries.
"""

from __future__ import annotations

import calendar
import csv
import io
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime

import httpx

from robotics_radar.ingest.base import (
    Fetcher,
    IngestError,
    NormalisedObservation,
    RawResponse,
    SeriesSpec,
)
from robotics_radar.ingest.sources.census_imports import KNOWN_LIMITATIONS
from robotics_radar.models.enums import Cadence, FlowDirection

METHODOLOGY = (
    "Monthly EU imports on CN 8483.40.30 (ball or roller screws) by partner "
    "country. Paired with the US Census series on HTS 8483.40.8000 as a "
    "cross-check; the two are never blended, because divergence between the "
    "jurisdictions is itself the signal. This CN line carries NO supplementary "
    "unit -- only value in euros and quantity in 100kg -- so the EU unit value "
    "is EUR per kilogram and is NOT comparable to the US dollars-per-screw "
    "figure. Cross-check the two on value and on growth rates, never on level."
)


BASE_URL = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data/DS-045409"
CN_CODE = "84834030"
REPORTER = "EU27_2020"
FLOW_IMPORT = "1"

VALUE_INDICATOR = "VALUE_IN_EUROS"
QUANTITY_INDICATOR = "QUANTITY_IN_100KG"

#: Extra-EU total: imports crossing the EU external border. This is the figure
#: comparable in spirit to the US import series; intra-EU trade is EU members
#: selling to each other and answers a different question.
EXTRA_EU = "EXT_EU27_2020"
INTRA_EU = "INT_EU27_2020"
AGGREGATES = {EXTRA_EU, INTRA_EU}

#: Eurostat pseudo-partners for unspecified or confidential origins. Real
#: countries only, or the geography of the series is a fiction.
_PSEUDO_PARTNER_PREFIX = "Q"

TRACKED_PARTNERS = {
    "JP": "Japan",
    "CH": "Switzerland",
    "TW": "Taiwan",
    "CN": "China",
    "US": "United States",
    "KR": "South Korea",
}

AGGREGATE_SERIES = "EU imports, ball or roller screws (CN 8483.40.30), extra-EU total"


def is_real_partner(code: str) -> bool:
    """True for an individual reporting country, False for any aggregate."""
    return (
        len(code) == 2
        and code not in AGGREGATES
        and not code.startswith(_PSEUDO_PARTNER_PREFIX)
    )


def partner_series_name(partner: str) -> str:
    return f"EU imports, ball or roller screws (CN 8483.40.30), from {partner}"


class ComextImportsFetcher(Fetcher):
    source_name = "eurostat_comext_imports"

    def series_specs(self) -> Sequence[SeriesSpec]:
        common = {
            "node_name": "Linear Actuation & Roller Screws",
            "source": self.source_name,
            "cadence": Cadence.monthly,
            "flow_direction": FlowDirection.import_,
            "geography": "EU",
            "tariff_code": CN_CODE,
            "tariff_nomenclature": "CN8",
            "source_url": BASE_URL,
            "unit": "EUR",
            "methodology_note": METHODOLOGY,
            "known_limitations": KNOWN_LIMITATIONS,
        }
        specs = [SeriesSpec(name=AGGREGATE_SERIES, partner_geography=None, **common)]
        specs += [
            SeriesSpec(name=partner_series_name(name), partner_geography=name, **common)
            for name in TRACKED_PARTNERS.values()
        ]
        return specs

    def fetch(self, period: date) -> Iterable[RawResponse]:
        # One request per period, wildcarding partner and indicator. Comext
        # refuses unfiltered extractions with a 413 naming the row count, so
        # the product/reporter/flow filter is not optional.
        month = f"{period.year:04d}-{period.month:02d}"
        key = f"M.{REPORTER}..{CN_CODE}.{FLOW_IMPORT}."
        params = {"startPeriod": month, "endPeriod": month, "format": "SDMX-CSV"}
        url = f"{BASE_URL}/{key}"

        fetched_at = datetime.now(UTC)
        response = httpx.get(url, params=params, timeout=120.0, follow_redirects=True)
        if response.status_code != 200:
            raise IngestError(
                f"eurostat_comext_imports: HTTP {response.status_code} for {month}"
            )
        body = response.text
        if not body.lstrip().startswith("DATAFLOW"):
            raise IngestError(
                f"eurostat_comext_imports: expected SDMX-CSV, got {body[:120]!r}"
            )
        yield RawResponse(url=url, params=params, body=body, fetched_at=fetched_at)

    def normalise(self, raw: RawResponse) -> Iterable[NormalisedObservation]:
        rows = list(csv.DictReader(io.StringIO(raw.body)))
        if not rows:
            raise IngestError("eurostat_comext_imports: empty CSV")

        # Pivot the indicators dimension: value and quantity arrive as separate
        # rows for the same partner and period.
        by_partner: dict[str, dict[str, float]] = {}
        for row in rows:
            partner = row["partner"]
            try:
                obs = float(row["OBS_VALUE"])
            except (TypeError, ValueError):
                continue
            by_partner.setdefault(partner, {})[row["indicators"]] = obs

        period_start, period_end = _period_bounds(raw.params["startPeriod"])
        vintage = raw.fetched_at.date()
        emitted = 0

        for partner, values in by_partner.items():
            if partner in AGGREGATES:
                series_key = AGGREGATE_SERIES if partner == EXTRA_EU else None
            elif is_real_partner(partner) and partner in TRACKED_PARTNERS:
                series_key = partner_series_name(TRACKED_PARTNERS[partner])
            else:
                series_key = None
            if series_key is None:
                continue

            value = values.get(VALUE_INDICATOR)
            hundred_kg = values.get(QUANTITY_INDICATOR)
            # Comext reports quantity in units of 100kg. Converting to plain
            # kilograms is lossless and makes unit_value read directly as
            # EUR/kg -- which is all this line can ever yield, since CN
            # 8483.40.30 carries no supplementary piece count.
            quantity = hundred_kg * 100 if hundred_kg is not None else None

            emitted += 1
            yield NormalisedObservation(
                series_key=series_key,
                period_start=period_start,
                period_end=period_end,
                vintage_date=vintage,
                value=value,
                quantity=quantity,
                quantity_unit="KG",
            )

        if not emitted:
            raise IngestError("eurostat_comext_imports: no tracked partners in response")


def _period_bounds(month: str) -> tuple[date, date]:
    year, mon = (int(part) for part in month.split("-"))
    return date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1])
