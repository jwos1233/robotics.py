"""JMTBA machine tool orders -- grinding and gear cutting machines.

STATUS: NOT IMPLEMENTED, and the underlying question is still open.

This is the most load-bearing series on the board. The cascade argument is
that machine-tool orders read capacity expansion one layer BELOW the visible
constraint: grinding machines gate roller screw and reducer output, so
grinding order intake leads actuation capacity.

WHAT PHASE 0 COULD NOT SETTLE: whether the MONTHLY release carries the
by-machine-type breakdown ("Grinding Machines", "Gear Cutting & Finishing
Machines") or whether that split appears only in the annual statistics.
Searching suggests the monthly release does carry a machine-type breakdown,
but that came from a search summary rather than from the monthly file itself,
so it is NOT confirmed. If the split turns out to be annual-only, the cascade
argument weakens substantially and this node needs a different instrument.

Also unresolved: file format and URL pattern, and whether order backlog and
the machine-tool price index appear in the monthly release or only annually.
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
