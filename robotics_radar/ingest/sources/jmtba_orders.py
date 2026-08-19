"""JMTBA machine tool orders -- grinding and gear cutting machines.

STATUS: NOT IMPLEMENTED, and the underlying question is still open.

This is the most load-bearing series on the board. The cascade argument is
that machine-tool orders read capacity expansion one layer BELOW the visible
constraint: grinding machines gate roller screw and reducer output, so
grinding order intake leads actuation capacity.

PHASE 0 RESOLVED THIS, and the answer is mixed.

The by-machine-type ORDER breakdown is NOT in any free monthly release:
  * The English "JMTBA NOTES" monthly news release breaks orders down by
    destination country and by customer industry only. No machine types.
  * The Japanese monthly 確報 (kakuhou) PDF likewise carries no machine-type
    split.
  * JMTBA sells it. The 受注確報 monthly statistics package is distributed by
    email on an annual contract at JPY 20,000/year (tax included) per
    delivery address, as PDF. Contact: stat31@jmtba.or.jp. That is the only
    route to monthly orders by machine type.

What IS free and monthly, from the Japanese 主要統計 (syuyoutoukei) PDF:
  * NC研削盤 -- NC grinding machine **PRODUCTION**, monthly, by value.
    Production, not orders. It is a coincident read on grinding output rather
    than a forward read on grinding capacity being bought, so it is a weaker
    instrument for the cascade argument than order intake would be.
  * No gear-cutting or gear-finishing split appears in the free data at all.

URL patterns are IRREGULAR and must not be constructed:
  * English: /english/wjmtbap/wp-content/uploads/YYYY/MM/JMTBA-NOTES-YYYY-MM.pdf
    but 2024 files omit the YYYY/MM directory and at least one 2025 file uses
    underscores instead of hyphens.
  * Japanese: /wjmtbap/wp-content/uploads/YYYY/MM/{kakuhou,syuyoutoukei}YYMM.pdf
    with the directory frequently not matching the reporting month.
  The fetcher must scrape the index page and follow links.

Order backlog (受注残) appears in the free Japanese releases. No machine-tool
price index was found in them.
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


class JmtbaOrdersFetcher(Fetcher):
    source_name = "jmtba_orders"

    def series_specs(self) -> Sequence[SeriesSpec]:
        return [
            SeriesSpec(
                name="Japan machine tool orders, grinding machines",
                node_name="Grinding & Gear Machines",
                source=self.source_name,
                cadence=Cadence.monthly,
                flow_direction=FlowDirection.orders,
                geography="JP",
                unit="JPY",
                methodology_note=(
                    "Order intake for grinding machines, read as a lead indicator "
                    "on actuation capacity: thread grinding gates roller screw "
                    "output, so orders here precede screw capacity by the "
                    "machine build and commissioning lag."
                ),
                known_limitations=(
                    "Cadence UNCONFIRMED: whether the by-machine-type split is "
                    "published monthly or only annually was not verified. "
                    "Reishauer, Kapp Niles, Gleason and Studer are private, so "
                    "the highest-signal builders are outside this aggregate."
                ),
            ),
            SeriesSpec(
                name="Japan machine tool orders, gear cutting & finishing machines",
                node_name="Grinding & Gear Machines",
                source=self.source_name,
                cadence=Cadence.monthly,
                flow_direction=FlowDirection.orders,
                geography="JP",
                unit="JPY",
                methodology_note=(
                    "Order intake for gear cutting and finishing machines, read "
                    "as a lead indicator on reducer capacity."
                ),
                known_limitations="Cadence UNCONFIRMED, as above.",
            ),
        ]

    def fetch(self, period: date) -> Iterable[RawResponse]:
        raise IngestError(
            "jmtba_orders: not implemented. Phase 0 could not confirm whether the "
            "monthly release carries the grinding / gear-cutting breakdown, nor "
            "the file format or URL pattern (jmtba.or.jp unreachable)."
        )

    def normalise(self, raw: RawResponse) -> Iterable[NormalisedObservation]:
        raise IngestError("jmtba_orders: parser awaits a real monthly file.")
