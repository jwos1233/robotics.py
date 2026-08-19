"""US Census monthly imports, HTS 8483.40.8000 (ball or roller screws), by origin.

STATUS: NOT IMPLEMENTED. Phase 0 verification could not run -- this session's
network policy blocks api.census.gov -- so the request shape, the variable
names and, critically, the quantity basis are unconfirmed.

What is settled (given, not re-derived):
  * US HTS 8483.40.8000 is "Ball or roller screws", confirmed live by CBP
    ruling NY N074168 classifying a Japanese ball screw and nut to that line.
  * HS6 8483.40 is a blended bucket (gears + screws + gearboxes + torque
    converters) and must not be used to build an ASP series.
  * The resolving line is on the import side, so this is measured by country
    of origin: one series per origin country, sharing a reporter.

What Phase 0 must resolve before this is written:
  1. The exact endpoint and whether CENSUS_API_KEY is required at this volume.
  2. The variable names for value, quantity and quantity unit.
  3. THE QUANTITY BASIS. If quantity on this line is reported by weight only,
     the "unit value" is dollars per kilogram, not dollars per screw. That is
     a materially weaker instrument -- it drifts with product mix -- and it
     changes what the series means. It must be recorded in quantity_unit and
     stated in the methodology note either way.
  4. Whether general or consumption imports is the right basis, and whether
     revisions arrive as restatements (which would need new vintages).

Until then this module raises rather than guessing an endpoint.
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
from robotics_radar.models.enums import Cadence, FlowDirection

KNOWN_LIMITATIONS = (
    "Destination-side measurement. EU and US imports together miss intra-Asia "
    "flow entirely, and Chinese domestic consumption is invisible. If humanoid "
    "assembly concentrates in China, this measures the wrong basin. It is a "
    "proxy with a hole, not a clean read."
)

METHODOLOGY = (
    "Monthly US imports on HTS 8483.40.8000 (ball or roller screws) by country "
    "of origin. Unit value is value divided by reported quantity and stands in "
    "for a price series; robotics has no spot market, nothing rents and nothing "
    "trades, so there is no roller screw print to reference. The quantity basis "
    "for this line is UNVERIFIED: if quantity is reported by weight, the unit "
    "value is $/kg and moves with product mix as well as price."
)


class CensusImportsFetcher(Fetcher):
    source_name = "us_census_imports"

    def series_specs(self) -> Sequence[SeriesSpec]:
        return [
            SeriesSpec(
                name="US imports, ball or roller screws (HTS 8483.40.8000), all origins",
                node_name="Linear Actuation & Roller Screws",
                source=self.source_name,
                cadence=Cadence.monthly,
                flow_direction=FlowDirection.import_,
                geography="US",
                partner_geography=None,
                tariff_code="8483408000",
                tariff_nomenclature="HTS10",
                methodology_note=METHODOLOGY,
                known_limitations=KNOWN_LIMITATIONS,
            )
        ]

    def fetch(self, period: date) -> Iterable[RawResponse]:
        raise IngestError(
            "us_census_imports: not implemented. Phase 0 could not verify the "
            "endpoint, variable names or quantity basis for HTS 8483.40.8000 "
            "(api.census.gov unreachable from the build environment)."
        )

    def normalise(self, raw: RawResponse) -> Iterable[NormalisedObservation]:
        raise IngestError("us_census_imports: parser awaits a real payload to test against.")
