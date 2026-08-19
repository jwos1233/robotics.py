"""US Census monthly imports, HTS 8483.40.8000 (ball or roller screws), by origin.

STATUS: NOT IMPLEMENTED, but Phase 0 has now VERIFIED this source live.

Verified:
  * Endpoint live: api.census.gov/data/timeseries/intltrade/imports/hs
  * An API key IS required. Without one the API returns **HTTP 200 with an
    HTML "Missing Key" page**, not a 4xx and not JSON. The fetcher must
    content-type check and reject non-JSON rather than trusting the status
    code -- this is the single most likely way to silently ingest garbage.
  * variables.json is keyless. Confirmed names: GEN_VAL_MO, GEN_QY1_MO,
    UNIT_QY1, CTY_CODE, CTY_NAME, I_COMMODITY, COMM_LVL, time. Also CON_*
    (imports for consumption) alongside GEN_* (general imports), and
    *_MO_FLAG true-zero flags that distinguish a real zero from a missing
    value. Those flags must be read; treating a blank as zero would invent
    data.
  * QUANTITY BASIS RESOLVED: USITC HTS reports 8483.40.80.00 with
    units = ["No."] -- a piece count. The US unit value is therefore
    genuinely dollars per screw, not dollars per kilogram. This is the good
    outcome and the series means what the board wants it to mean.

What is settled (given, not re-derived):
  * US HTS 8483.40.8000 is "Ball or roller screws", confirmed live by CBP
    ruling NY N074168 classifying a Japanese ball screw and nut to that line.
  * HS6 8483.40 is a blended bucket (gears + screws + gearboxes + torque
    converters) and must not be used to build an ASP series.
  * The resolving line is on the import side, so this is measured by country
    of origin: one series per origin country, sharing a reporter.

  * Real data pulled for 2026-06: USD 13.48m across 626,176 units from 40
    origins. Japan USD 2.66m, Switzerland USD 2.75m, Germany USD 2.62m,
    Taiwan USD 0.61m, China USD 0.30m.

  * AGGREGATE ROWS ARE MIXED INTO THE SAME RESPONSE. See is_country_code().

  * THE UNIT VALUE IS DOMINATED BY PRODUCT MIX, not price. Across origins in
    a single month it spans USD 0.45/unit (Poland, 172,800 units) to
    USD 6,374/unit (Czech Republic, 7 units) -- a 14,000x spread. The line
    plainly carries both commodity ball screws and large specialist screws
    under one code.

    So a blended ASP over this line is not a price signal and must not be
    published as one. What IS coherent is a per-origin series within the
    precision band: Japan USD 242, Taiwan USD 242, Italy USD 201, Germany
    USD 178 cluster tightly, while Poland, Canada and Switzerland sit two to
    three orders of magnitude below and are evidently a different product.
    Even within one origin, a mix shift moves the number with no price change.

Still open:
  1. Whether to measure on the general-imports (GEN_*) or
     imports-for-consumption (CON_*) basis. Both are published; they answer
     different questions and must not be mixed within one series.
  2. Revision behaviour, so vintage_date is assigned correctly.
"""

from __future__ import annotations

import re
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
    "trades, so there is no roller screw print to reference. Quantity on this "
    "line is reported as a piece count (HTS unit of quantity 'No.'), so the "
    "unit value is dollars per screw."
)


#: Census returns individual countries, economic groupings (0003 EU, 0022
#: OECD, 0023 NATO...), continent aggregates (4XXX EUROPE) and a world total
#: ('-') in the SAME response, undifferentiated. Summing the rows naively
#: double-counts by roughly 3x. Verified against the 2026-06 fixture: the 40
#: rows matching this pattern reconcile exactly to the TOTAL row on both value
#: and quantity, while the other 20 rows are aggregates of them.
_COUNTRY_CODE = re.compile(r"\d{4}")


def is_country_code(code: str) -> bool:
    """True for an individual country, False for any aggregate row."""
    return bool(_COUNTRY_CODE.fullmatch(code)) and not code.startswith("00")


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
            "us_census_imports: not implemented. Endpoint and quantity basis are "
            "verified; needs CENSUS_API_KEY and a decision on the general vs "
            "consumption basis before it can be written."
        )

    def normalise(self, raw: RawResponse) -> Iterable[NormalisedObservation]:
        raise IngestError("us_census_imports: parser awaits a real payload to test against.")
