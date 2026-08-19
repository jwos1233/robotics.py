"""China NBS monthly industrial robot output (demand side).

STATUS: NOT IMPLEMENTED.

Unresolved: whether the data.stats.gov.cn easyquery endpoint is usable and
stable enough to depend on, or whether this needs HTML scraping with a
fallback path. Neither could be tested (host unreachable).

Note on interpretation: NBS industrial robot output is a demand-side read, not
a constraint. It exists so tightness elsewhere on the board can be judged
demand-led or supply-led. Chinese output series are also subject to definitional
changes and base-year revisions, which is exactly why observations are
vintaged.
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


class NbsRobotOutputFetcher(Fetcher):
    source_name = "china_nbs_robot_output"

    def series_specs(self) -> Sequence[SeriesSpec]:
        return [
            SeriesSpec(
                name="China industrial robot output, monthly",
                node_name="Humanoid OEM Demand",
                source=self.source_name,
                cadence=Cadence.monthly,
                flow_direction=FlowDirection.production,
                geography="CN",
                unit="units",
                methodology_note=(
                    "Demand-side reference series, not a constraint. Used to "
                    "read whether tightness elsewhere is demand-led."
                ),
                known_limitations=(
                    "Endpoint stability UNVERIFIED. Subject to definitional and "
                    "base-year revisions, which is why every figure is vintaged."
                ),
            )
        ]

    def fetch(self, period: date) -> Iterable[RawResponse]:
        raise IngestError(
            "china_nbs_robot_output: not implemented. Phase 0 could not verify "
            "the easyquery endpoint (data.stats.gov.cn unreachable)."
        )

    def normalise(self, raw: RawResponse) -> Iterable[NormalisedObservation]:
        raise IngestError("china_nbs_robot_output: parser awaits a real payload.")
