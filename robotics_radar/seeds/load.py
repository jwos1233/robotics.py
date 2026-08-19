"""Idempotent seed loader for nodes, securities and baskets.

Re-running this is safe: existing rows are updated in place and membership is
reconciled rather than duplicated. It seeds structure only. It does not seed
severity, break_point_tier, prices or observations -- those either await a
methodology or await verified sources.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from robotics_radar.logging import get_logger
from robotics_radar.models.constraint import Node
from robotics_radar.models.enums import Bucket, CoverageStatus, PurityGrade
from robotics_radar.models.equity import Basket, BasketMember, Security

log = get_logger(__name__)
SEED_DIR = Path(__file__).parent


def _load(name: str):
    with open(SEED_DIR / name) as fh:
        return yaml.safe_load(fh)


def seed_nodes(session: Session) -> int:
    existing = {n.name: n for n in session.scalars(select(Node))}
    count = 0
    for row in _load("nodes.yaml"):
        node = existing.get(row["name"])
        if node is None:
            node = Node(name=row["name"])
            session.add(node)
        node.bucket = Bucket(row["bucket"])
        node.methodology_note = row.get("methodology_note")
        # severity and break_point_tier are intentionally never written here.
        count += 1
    session.flush()
    return count


def seed_securities(session: Session) -> int:
    existing = {s.display_ticker: s for s in session.scalars(select(Security))}
    count = 0
    for row in _load("securities.yaml"):
        sec = existing.get(row["display_ticker"])
        if sec is None:
            sec = Security(display_ticker=row["display_ticker"])
            session.add(sec)
        sec.local_code = row["local_code"]
        sec.exchange_mic = row["exchange_mic"]
        sec.currency = row["currency"]
        sec.country = row["country"]
        sec.name = row["name"]
        sec.isin = row.get("isin")
        # data_source / source_symbol stay unset: no price provider is
        # confirmed, and a guessed symbol prices the wrong instrument.
        sec.coverage_status = CoverageStatus(row["coverage_status"])
        count += 1
    session.flush()
    return count


def seed_baskets(session: Session) -> int:
    nodes = {n.name: n for n in session.scalars(select(Node))}
    securities = {s.display_ticker: s for s in session.scalars(select(Security))}
    existing = {b.name: b for b in session.scalars(select(Basket))}
    today = date.today()
    count = 0

    for row in _load("baskets.yaml"):
        basket = existing.get(row["name"])
        if basket is None:
            basket = Basket(name=row["name"])
            session.add(basket)
        node = nodes.get(row["node"]) if row.get("node") else None
        if row.get("node") and node is None:
            raise ValueError(f"basket {row['name']!r} references unknown node {row['node']!r}")
        basket.node_id = node.id if node else None
        basket.bucket = Bucket(row["bucket"]) if row.get("bucket") else None
        basket.constraint_label = row["constraint_label"]
        basket.purity_grade = PurityGrade(row["purity_grade"])
        basket.is_demand_side = bool(row.get("is_demand_side", False))
        basket.is_shared_node = bool(row.get("is_shared_node", False))
        basket.thesis_note = row.get("thesis_note")
        basket.caveat_note = row.get("caveat_note")
        session.flush()

        wanted = set(row["members"])
        unknown = wanted - securities.keys()
        if unknown:
            raise ValueError(f"basket {row['name']!r} references unknown tickers {sorted(unknown)}")

        current = {
            m.security.display_ticker: m
            for m in session.scalars(
                select(BasketMember).where(
                    BasketMember.basket_id == basket.id, BasketMember.removed_at.is_(None)
                )
            )
        }
        for ticker in wanted - current.keys():
            session.add(
                BasketMember(
                    basket_id=basket.id,
                    security_id=securities[ticker].id,
                    added_at=today,
                )
            )
        # Membership history is preserved: a dropped name is closed out with
        # removed_at rather than deleted.
        for ticker in current.keys() - wanted:
            current[ticker].removed_at = today
        count += 1

    session.flush()
    return count


def seed_all(session: Session) -> dict[str, int]:
    result = {
        "nodes": seed_nodes(session),
        "securities": seed_securities(session),
        "baskets": seed_baskets(session),
    }
    log.info("seed_complete", **result)
    return result


def main() -> None:
    from robotics_radar.db import session_scope
    from robotics_radar.logging import configure_logging

    configure_logging()
    with session_scope() as session:
        seed_all(session)


if __name__ == "__main__":
    main()
