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

Still open:
  1. Revision behaviour, so vintage_date is assigned correctly.
  2. Whether an EU-aggregate reporter is preferable to summing members.

CROSS-CHECK, NOT BLEND: this series and the US Census series measure the same
node in two jurisdictions. They are deliberately kept as separate series so
divergence between them is visible. Averaging them would hide exactly the
signal that divergence carries.
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


class ComextImportsFetcher(Fetcher):
    source_name = "eurostat_comext_imports"

    def series_specs(self) -> Sequence[SeriesSpec]:
        return [
            SeriesSpec(
                name="EU imports, ball or roller screws (CN 8483.40.30), all partners",
                node_name="Linear Actuation & Roller Screws",
                source=self.source_name,
                cadence=Cadence.monthly,
                flow_direction=FlowDirection.import_,
                geography="EU",
                partner_geography=None,
                tariff_code="84834030",
                tariff_nomenclature="CN8",
                methodology_note=METHODOLOGY,
                known_limitations=KNOWN_LIMITATIONS,
            )
        ]

    def fetch(self, period: date) -> Iterable[RawResponse]:
        raise IngestError(
            "eurostat_comext_imports: not implemented. Endpoint, request shape "
            "and indicator set are verified; parser not yet written."
        )

    def normalise(self, raw: RawResponse) -> Iterable[NormalisedObservation]:
        raise IngestError("eurostat_comext_imports: parser awaits a real payload.")
