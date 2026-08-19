"""Taiwan TWSE monthly revenue filings.

Taiwanese listed companies must file monthly revenue within 10 days of
month-end, and TWSE republishes the whole market through a keyless open API.
For a company whose business *is* a constraint, that disclosure is a direct
fundamental read where the share price is only a sentiment proxy -- so these
series sit on the CONSTRAINT side with evidence_grade='disclosed', not in a
basket.

Hiwin (2049) is the clearest case: one of the few listed pure-plays in ball
screws and linear guides, reporting monthly.

Two properties of this source shape the implementation:

* **It is a snapshot, not an archive.** The endpoint serves only the most
  recently filed month for the whole market. There is no historical endpoint,
  so history accumulates forward from first run and cannot be backfilled. The
  fetcher therefore refuses when the served month is not the month asked for,
  rather than silently storing the wrong period.
* **It dates its own release.** `出表日期` is the publication date and
  `資料年月` the reporting month, both in Republic of China calendar years
  (ROC year + 1911 = Gregorian). This is the only source so far that supplies
  a genuine release_date rather than leaving it None.
"""

from __future__ import annotations

import calendar
import json
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
from robotics_radar.models.enums import Cadence, EvidenceGrade, FlowDirection

URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"

FIELD_PERIOD = "資料年月"
FIELD_RELEASE = "出表日期"
FIELD_CODE = "公司代號"
FIELD_REVENUE = "營業收入-當月營收"

#: Revenue is filed in thousands of New Taiwan dollars.
THOUSANDS = 1000

#: Roster companies whose monthly filing reads on a constraint node. Each is
#: mapped to the node its revenue actually informs -- not to a basket.
TRACKED = {
    "2049": ("Hiwin Technologies", "Bearings & Linear Motion"),
    "2308": ("Delta Electronics", "CNC Controls & Servo"),
    "2317": ("Hon Hai Precision", "Contract Manufacture"),
    "2327": ("Yageo", "Passives & Interconnect"),
    "2382": ("Quanta Computer", "Contract Manufacture"),
    "1101": ("Taiwan Cement", "High-Rate Cells"),
    "4919": ("Nuvoton Technology", "BMS & Power Conversion"),
}

METHODOLOGY = (
    "Monthly operating revenue as filed with the Taiwan Stock Exchange, which "
    "requires disclosure within 10 days of month-end. Read as a fundamental "
    "demand signal for the linked constraint: for a company whose business is "
    "the constraint, revenue moves with orders shipped, whereas the share "
    "price moves with sentiment."
)

LIMITATIONS = (
    "Company revenue, not industry output. It covers everything the company "
    "sells, so a diversified filer's number is only loosely attached to the "
    "node, and it carries price and currency effects as well as volume. "
    "TWSE serves only the latest filed month with no historical endpoint, so "
    "this series accumulates forward from first collection and cannot be "
    "backfilled."
)


def series_name(company: str) -> str:
    return f"Taiwan monthly revenue, {company}"


def roc_to_date(value: str) -> date:
    """Convert a Republic of China calendar date string to a Gregorian date.

    Accepts YYYMM (reporting month, day defaults to the 1st) and YYYMMDD
    (publication date). ROC year 115 is Gregorian 2026.
    """
    digits = value.strip()
    if len(digits) == 5:  # YYYMM
        year, month, day = int(digits[:3]) + 1911, int(digits[3:]), 1
    elif len(digits) == 7:  # YYYMMDD
        year, month, day = int(digits[:3]) + 1911, int(digits[3:5]), int(digits[5:])
    else:
        raise IngestError(f"twse_revenue: unrecognised ROC date {value!r}")
    return date(year, month, day)


class TwseRevenueFetcher(Fetcher):
    source_name = "twse_revenue"

    def series_specs(self) -> Sequence[SeriesSpec]:
        return [
            SeriesSpec(
                name=series_name(company),
                node_name=node,
                source=self.source_name,
                cadence=Cadence.monthly,
                flow_direction=FlowDirection.revenue,
                geography="TW",
                # The company reports this about itself; nobody measured it.
                evidence_grade=EvidenceGrade.disclosed,
                unit="TWD",
                source_url=URL,
                methodology_note=METHODOLOGY,
                known_limitations=LIMITATIONS,
            )
            for company, node in TRACKED.values()
        ]

    def fetch(self, period: date) -> Iterable[RawResponse]:
        fetched_at = datetime.now(UTC)
        response = httpx.get(URL, timeout=90.0, follow_redirects=True)
        if response.status_code != 200:
            raise IngestError(f"twse_revenue: HTTP {response.status_code}")
        body = response.text
        if not body.lstrip().startswith("["):
            raise IngestError(f"twse_revenue: expected a JSON array, got {body[:120]!r}")
        yield RawResponse(
            url=URL,
            params={"period": f"{period.year:04d}-{period.month:02d}"},
            body=body,
            fetched_at=fetched_at,
        )

    def normalise(self, raw: RawResponse) -> Iterable[NormalisedObservation]:
        records = json.loads(raw.body)
        if not records:
            raise IngestError("twse_revenue: empty response")

        wanted = raw.params["period"]
        served = roc_to_date(records[0][FIELD_PERIOD])
        served_label = f"{served.year:04d}-{served.month:02d}"
        if served_label != wanted:
            # A snapshot endpoint: asking for a month it no longer serves must
            # fail, not quietly record whatever month happens to be current.
            raise IngestError(
                f"twse_revenue: requested {wanted} but the endpoint serves "
                f"{served_label}. This source has no historical endpoint; it can "
                f"only be collected in the month it is published."
            )

        vintage = raw.fetched_at.date()
        emitted = 0
        for record in records:
            code = record.get(FIELD_CODE)
            if code not in TRACKED:
                continue
            company, _node = TRACKED[code]
            raw_revenue = record.get(FIELD_REVENUE)
            if raw_revenue in (None, "", "-"):
                continue

            period_start = served
            period_end = date(
                served.year, served.month, calendar.monthrange(served.year, served.month)[1]
            )
            emitted += 1
            yield NormalisedObservation(
                series_key=series_name(company),
                period_start=period_start,
                period_end=period_end,
                vintage_date=vintage,
                release_date=roc_to_date(record[FIELD_RELEASE]),
                value=float(raw_revenue) * THOUSANDS,
                # No physical quantity is disclosed, so no unit value exists.
                suppress_unit_value=True,
            )

        if not emitted:
            raise IngestError("twse_revenue: no tracked companies in response")
