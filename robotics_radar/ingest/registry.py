"""Registry of available fetchers.

Every source here currently raises IngestError on fetch: Phase 0 verification
could not run, and a fetcher that guesses an endpoint is worse than one that
refuses. The registry exists so the scheduler and CLI have a stable surface
the moment each source is verified and filled in.
"""

from __future__ import annotations

from robotics_radar.ingest.base import Fetcher
from robotics_radar.ingest.sources.census_imports import CensusImportsFetcher
from robotics_radar.ingest.sources.comext_imports import ComextImportsFetcher
from robotics_radar.ingest.sources.equity_prices import EquityPriceFetcher
from robotics_radar.ingest.sources.jmtba_orders import JmtbaOrdersFetcher
from robotics_radar.ingest.sources.nbs_robot_output import NbsRobotOutputFetcher
from robotics_radar.ingest.sources.twse_revenue import TwseRevenueFetcher

FETCHERS: dict[str, type[Fetcher]] = {
    "census": CensusImportsFetcher,
    "comext": ComextImportsFetcher,
    "jmtba": JmtbaOrdersFetcher,
    "nbs": NbsRobotOutputFetcher,
    "equity": EquityPriceFetcher,
    "twse_revenue": TwseRevenueFetcher,
}


def get_fetcher(name: str) -> Fetcher:
    try:
        return FETCHERS[name]()
    except KeyError:
        raise KeyError(f"unknown source {name!r}; known: {sorted(FETCHERS)}") from None
