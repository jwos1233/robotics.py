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

import calendar
import json
import re
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime

import httpx

from robotics_radar.config import get_settings
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

AGGREGATE_METHODOLOGY = (
    "Monthly US import VALUE and unit COUNT on HTS 8483.40.8000 summed across "
    "all origins. No unit value is published for this series: the product mix "
    "across origins spans four orders of magnitude, so value divided by count "
    "is not a price. Use the per-origin series for unit values."
)

AGGREGATE_LIMITATIONS = KNOWN_LIMITATIONS + (
    " Aggregate only: no unit value is meaningful at this level."
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


#: Origins tracked as their own series. Chosen because the roller-screw read
#: is a by-origin measurement and because a blended ASP over this line is not
#: interpretable -- see the mix note above. The first four are the precision
#: band; CH, CN and KR are carried to watch whether they enter it.
TRACKED_ORIGINS = {
    "5880": "Japan",
    "4280": "Germany",
    "4759": "Italy",
    "5830": "Taiwan",
    "4419": "Switzerland",
    "5700": "China",
    "5800": "South Korea",
}

AGGREGATE_SERIES = "US imports, ball or roller screws (HTS 8483.40.8000), all origins"
BASE_URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"
HTS_CODE = "8483408000"

#: Census marks a value it could not publish rather than a true zero.
MISSING_FLAG = "M"


def origin_series_name(origin: str) -> str:
    return f"US imports, ball or roller screws (HTS 8483.40.8000), from {origin}"


class CensusImportsFetcher(Fetcher):
    source_name = "us_census_imports"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or get_settings().census_api_key

    def series_specs(self) -> Sequence[SeriesSpec]:
        common = {
            "node_name": "Linear Actuation & Roller Screws",
            "source": self.source_name,
            "cadence": Cadence.monthly,
            "flow_direction": FlowDirection.import_,
            "geography": "US",
            "tariff_code": HTS_CODE,
            "tariff_nomenclature": "HTS10",
            "source_url": BASE_URL,
            "unit": "USD",
        }
        specs = [
            SeriesSpec(
                name=AGGREGATE_SERIES,
                partner_geography=None,
                methodology_note=AGGREGATE_METHODOLOGY,
                known_limitations=AGGREGATE_LIMITATIONS,
                **common,
            )
        ]
        specs += [
            SeriesSpec(
                name=origin_series_name(origin),
                partner_geography=origin,
                methodology_note=METHODOLOGY,
                known_limitations=KNOWN_LIMITATIONS,
                **common,
            )
            for origin in TRACKED_ORIGINS.values()
        ]
        return specs

    def fetch(self, period: date) -> Iterable[RawResponse]:
        if not self._api_key:
            raise IngestError(
                "us_census_imports: CENSUS_API_KEY is not set. The API answers "
                "an unauthenticated request with HTTP 200 and an HTML page, so "
                "this refuses up front rather than parsing an error page."
            )

        params = {
            "get": ",".join(
                [
                    "CTY_CODE",
                    "CTY_NAME",
                    "GEN_VAL_MO",
                    "GEN_QY1_MO",
                    "UNIT_QY1",
                    "GEN_QY1_MO_FLAG",
                ]
            ),
            "I_COMMODITY": HTS_CODE,
            "time": f"{period.year:04d}-{period.month:02d}",
            "COMM_LVL": "HS10",
        }
        fetched_at = datetime.now(UTC)
        response = httpx.get(
            BASE_URL, params={**params, "key": self._api_key}, timeout=90.0,
            follow_redirects=True,
        )

        # The status code is NOT a reliable success signal here: a missing or
        # inactive key returns HTTP 200 with an HTML error page. Validate the
        # body shape before anything downstream trusts it.
        body = response.text
        if response.status_code != 200 or not body.lstrip().startswith("["):
            title = re.search(r"<title>([^<]*)</title>", body)
            detail = title.group(1).strip() if title else body[:120]
            raise IngestError(
                f"us_census_imports: expected a JSON array, got "
                f"HTTP {response.status_code} ({detail!r}). Check CENSUS_API_KEY "
                f"is set and activated."
            )

        # The key is deliberately excluded from the stored params: raw_payloads
        # is a permanent record and must not become a credential store.
        yield RawResponse(url=BASE_URL, params=params, body=body, fetched_at=fetched_at)

    def normalise(self, raw: RawResponse) -> Iterable[NormalisedObservation]:
        table = json.loads(raw.body)
        if not table:
            raise IngestError("us_census_imports: empty response table")

        header, rows = table[0], table[1:]
        idx = {name: n for n, name in enumerate(header)}
        for required in ("CTY_CODE", "GEN_VAL_MO", "GEN_QY1_MO", "UNIT_QY1"):
            if required not in idx:
                raise IngestError(f"us_census_imports: response lacks {required}")

        period_start, period_end = _period_bounds(raw.params["time"])
        # The API serves only the current vintage and does not date it, so the
        # retrieval date is the best honest vintage stamp. release_date stays
        # None rather than being guessed from the publication calendar.
        vintage = raw.fetched_at.date()

        seen_total: dict[str, int] = {}
        emitted = 0
        for row in rows:
            code = row[idx["CTY_CODE"]]
            value = _to_int(row[idx["GEN_VAL_MO"]])
            quantity = _to_int(row[idx["GEN_QY1_MO"]])
            unit = row[idx["UNIT_QY1"]] or None
            flag = row[idx["GEN_QY1_MO_FLAG"]] if "GEN_QY1_MO_FLAG" in idx else None
            if flag == MISSING_FLAG:
                quantity = None

            if code == "-":
                seen_total = {"value": value, "quantity": quantity}
                continue
            if not is_country_code(code):
                continue  # economic grouping or continent aggregate

            emitted += 1
            origin = TRACKED_ORIGINS.get(code)
            if origin is None:
                continue
            yield NormalisedObservation(
                series_key=origin_series_name(origin),
                period_start=period_start,
                period_end=period_end,
                vintage_date=vintage,
                value=value,
                quantity=quantity,
                quantity_unit=unit,
            )

        if not emitted:
            raise IngestError("us_census_imports: no country rows in response")

        # The aggregate carries value and quantity but never a unit value: the
        # product mix across origins spans four orders of magnitude, so the
        # ratio is not a price.
        if seen_total:
            yield NormalisedObservation(
                series_key=AGGREGATE_SERIES,
                period_start=period_start,
                period_end=period_end,
                vintage_date=vintage,
                value=seen_total["value"],
                quantity=seen_total["quantity"],
                quantity_unit="NO",
                suppress_unit_value=True,
            )


def _to_int(raw: str | None) -> int | None:
    if raw in (None, "", "-"):
        return None
    return int(raw)


def _period_bounds(time_value: str) -> tuple[date, date]:
    year, month = (int(part) for part in time_value.split("-"))
    start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    return start, date(year, month, last_day)
