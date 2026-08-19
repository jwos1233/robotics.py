"""Create series rows from the fetchers' declared specs.

Series identity lives with the source module rather than in a YAML file, so a
series and the code that populates it cannot drift apart. Running this is
idempotent and creates no observations -- it only registers what each source
is responsible for, together with its methodology note and known limitations.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from robotics_radar.ingest.base import SeriesSpec
from robotics_radar.ingest.registry import FETCHERS
from robotics_radar.logging import get_logger
from robotics_radar.models.constraint import Node, Series
from robotics_radar.models.enums import EvidenceGrade

log = get_logger(__name__)


def register_spec(session: Session, spec: SeriesSpec) -> Series:
    node = session.scalar(select(Node).where(Node.name == spec.node_name))
    if node is None:
        raise ValueError(f"series {spec.name!r} references unknown node {spec.node_name!r}")

    existing = session.scalar(
        select(Series).where(
            Series.source == spec.source,
            Series.name == spec.name,
            Series.geography == spec.geography,
            Series.partner_geography.is_(spec.partner_geography)
            if spec.partner_geography is None
            else Series.partner_geography == spec.partner_geography,
        )
    )
    series = existing or Series(source=spec.source, name=spec.name, geography=spec.geography)
    if existing is None:
        session.add(series)

    series.node_id = node.id
    series.partner_geography = spec.partner_geography
    series.source_url = spec.source_url
    series.cadence = spec.cadence
    series.unit = spec.unit
    # Customs and order releases are primary statistical output, so anything
    # registered here is 'measured'. A derived series would declare otherwise.
    series.evidence_grade = EvidenceGrade.measured
    series.tariff_code = spec.tariff_code
    series.tariff_nomenclature = spec.tariff_nomenclature
    series.flow_direction = spec.flow_direction
    series.methodology_note = spec.methodology_note
    series.known_limitations = spec.known_limitations
    session.flush()
    return series


def register_all(session: Session) -> int:
    count = 0
    for name, cls in FETCHERS.items():
        for spec in cls().series_specs():
            register_spec(session, spec)
            count += 1
        log.info("series_registered", source=name)
    return count


def main() -> None:
    from robotics_radar.db import session_scope
    from robotics_radar.logging import configure_logging

    configure_logging()
    with session_scope() as session:
        total = register_all(session)
        log.info("register_complete", series=total)


if __name__ == "__main__":
    main()
