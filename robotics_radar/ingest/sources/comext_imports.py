"""Eurostat Comext monthly imports, CN 8483.40.30 (ball or roller screws), by partner.

STATUS: NOT IMPLEMENTED. Phase 0 verification could not run.

What is settled (given, not re-derived):
  * EU CN 8483.40.30 is "Ball or roller screws"; 8483.40.90 is the residual.
  * Measured by partner country for the same reason as the US line.

Partly established from documentation, NOT live-verified:
  * A Comext dissemination API is documented at
    ec.europa.eu/eurostat/api/comext/dissemination, and dataset DS-045409 is
    described as EU trade since 1988 at CN8, monthly. Access appears to be
    keyless. Unfiltered whole-dataset downloads are documented as disabled.

What Phase 0 must resolve:
  1. The exact dataset id and request shape, live.
  2. THE SUPPLEMENTARY UNIT QUESTION. Comext reports value and weight; whether
     CN 8483.40.30 carries a supplementary unit (a piece count) decides whether
     the EU unit value is EUR/unit or EUR/100kg. This is the same question as
     the Census quantity basis and has the same consequence.
  3. Revision behaviour, so vintages are dated correctly.

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
    "jurisdictions is itself the signal. Quantity basis UNVERIFIED pending "
    "confirmation of whether this CN line carries a supplementary unit."
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
            "eurostat_comext_imports: not implemented. Phase 0 could not verify "
            "the dataset id, request shape or supplementary-unit availability "
            "for CN 8483.40.30 (ec.europa.eu unreachable from the build environment)."
        )

    def normalise(self, raw: RawResponse) -> Iterable[NormalisedObservation]:
        raise IngestError("eurostat_comext_imports: parser awaits a real payload.")
