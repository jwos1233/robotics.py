from __future__ import annotations

from itertools import combinations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from robotics_radar.api.interpretation import coverage_caveat, interpretation_for
from robotics_radar.config import get_settings
from robotics_radar.db import get_db
from robotics_radar.models.constraint import Node
from robotics_radar.models.enums import Bucket, CoverageStatus, PurityGrade, ReturnWindow
from robotics_radar.models.equity import Basket, BasketMember, BasketReturn
from robotics_radar.schemas import (
    BasketDetailOut,
    BasketOut,
    BasketReturnOut,
    OverlapPair,
    OverlapResponse,
    SecurityOut,
)

router = APIRouter(tags=["equity"])

BREADTH_FLAG_THRESHOLD = 0.5


def _live_members(basket: Basket) -> list[BasketMember]:
    return [m for m in basket.members if m.removed_at is None]


def _to_out(basket: Basket, node_name: str | None) -> BasketOut:
    members = _live_members(basket)
    priceable = sum(1 for m in members if m.security.coverage_status == CoverageStatus.ok)
    return BasketOut(
        id=basket.id,
        name=basket.name,
        node_id=basket.node_id,
        node_name=node_name,
        bucket=basket.bucket,
        constraint_label=basket.constraint_label,
        purity_grade=basket.purity_grade,
        is_demand_side=basket.is_demand_side,
        is_shared_node=basket.is_shared_node,
        thesis_note=basket.thesis_note,
        caveat_note=basket.caveat_note,
        constituents_total=len(members),
        constituents_priceable=priceable,
        interpretation=interpretation_for(basket.purity_grade, basket.is_demand_side),
    )


def _loaded(db: Session):
    return select(Basket).options(
        selectinload(Basket.members).selectinload(BasketMember.security)
    )


def _node_names(db: Session) -> dict[int, str]:
    return {n.id: n.name for n in db.scalars(select(Node))}


# Registered before /baskets/{basket_id} so the literal path wins the match.
@router.get("/baskets/overlap", response_model=OverlapResponse)
def basket_overlap(db: Session = Depends(get_db)) -> OverlapResponse:
    """Shared-membership matrix across baskets.

    Overlap is legitimate -- a name can genuinely sit in two constraints -- but
    it means constraint-side and demand-side baskets are not independent. Any
    correlation computed across baskets has to be discounted for this.
    """
    baskets = list(db.scalars(_loaded(db).order_by(Basket.name)))
    rosters = {
        b.id: {m.security.display_ticker for m in _live_members(b)} for b in baskets
    }
    names = {b.id: b.name for b in baskets}

    pairs: list[OverlapPair] = []
    for a, b in combinations(baskets, 2):
        shared = rosters[a.id] & rosters[b.id]
        if not shared:
            continue
        union = rosters[a.id] | rosters[b.id]
        pairs.append(
            OverlapPair(
                basket_a_id=a.id,
                basket_a=names[a.id],
                basket_b_id=b.id,
                basket_b=names[b.id],
                shared=sorted(shared),
                shared_count=len(shared),
                jaccard=len(shared) / len(union) if union else 0.0,
            )
        )
    pairs.sort(key=lambda p: (-p.shared_count, p.basket_a, p.basket_b))
    return OverlapResponse(
        note=(
            "Baskets sharing constituents are not independent. Discount any "
            "cross-basket correlation by this overlap before reading it as two "
            "constraints moving together."
        ),
        baskets=len(baskets),
        pairs=pairs,
    )


@router.get("/baskets", response_model=list[BasketOut])
def list_baskets(
    bucket: Bucket | None = Query(None),
    purity: PurityGrade | None = Query(None),
    demand_side: bool | None = Query(None),
    db: Session = Depends(get_db),
) -> list[BasketOut]:
    stmt = _loaded(db).order_by(Basket.name)
    if bucket is not None:
        stmt = stmt.where(Basket.bucket == bucket)
    if purity is not None:
        stmt = stmt.where(Basket.purity_grade == purity)
    if demand_side is not None:
        stmt = stmt.where(Basket.is_demand_side == demand_side)
    nodes = _node_names(db)
    return [_to_out(b, nodes.get(b.node_id)) for b in db.scalars(stmt)]


@router.get("/baskets/{basket_id}", response_model=BasketDetailOut)
def get_basket(basket_id: int, db: Session = Depends(get_db)) -> BasketDetailOut:
    basket = db.scalar(_loaded(db).where(Basket.id == basket_id))
    if basket is None:
        raise HTTPException(status_code=404, detail=f"basket {basket_id} not found")
    nodes = _node_names(db)
    base = _to_out(basket, nodes.get(basket.node_id))
    return BasketDetailOut(
        **base.model_dump(),
        members=[
            SecurityOut.model_validate(m.security) for m in _live_members(basket)
        ],
    )


@router.get("/baskets/{basket_id}/returns", response_model=BasketReturnOut)
def get_basket_returns(
    basket_id: int,
    window: ReturnWindow = Query(ReturnWindow.d1),
    db: Session = Depends(get_db),
) -> BasketReturnOut:
    basket = db.scalar(_loaded(db).where(Basket.id == basket_id))
    if basket is None:
        raise HTTPException(status_code=404, detail=f"basket {basket_id} not found")

    total = len(_live_members(basket))
    settings = get_settings()

    row = db.scalar(
        select(BasketReturn)
        .where(BasketReturn.basket_id == basket_id, BasketReturn.window == window)
        .order_by(BasketReturn.date.desc())
        .limit(1)
    )

    if row is None:
        # No computed return yet: report the shape honestly rather than zero.
        return BasketReturnOut(
            basket_id=basket.id,
            basket_name=basket.name,
            purity_grade=basket.purity_grade,
            is_demand_side=basket.is_demand_side,
            window=window,
            as_of=None,
            return_raw=None,
            return_vs_benchmark=None,
            benchmark_symbol=settings.benchmark_symbol,
            breadth=None,
            breadth_flag=False,
            constituents_priced=0,
            constituents_total=total,
            coverage_ratio=None,
            interpretation=interpretation_for(basket.purity_grade, basket.is_demand_side),
            caveat_note=(
                "No return computed. No price provider has been confirmed for "
                "this universe, so no constituent carries a price source."
            ),
        )

    ratio = (
        row.constituents_priced / row.constituents_total
        if row.constituents_total
        else None
    )
    breadth = float(row.breadth) if row.breadth is not None else None
    caveats = [coverage_caveat(row.constituents_priced, row.constituents_total)]
    if breadth is not None and breadth < BREADTH_FLAG_THRESHOLD:
        caveats.append(
            f"Breadth {breadth:.2f}: the move is one or two names, not the basket."
        )
    if basket.caveat_note:
        caveats.append(basket.caveat_note)

    return BasketReturnOut(
        basket_id=basket.id,
        basket_name=basket.name,
        purity_grade=basket.purity_grade,
        is_demand_side=basket.is_demand_side,
        window=window,
        as_of=row.date,
        return_raw=float(row.return_raw) if row.return_raw is not None else None,
        return_vs_benchmark=(
            float(row.return_vs_benchmark) if row.return_vs_benchmark is not None else None
        ),
        benchmark_symbol=settings.benchmark_symbol,
        breadth=breadth,
        breadth_flag=breadth is not None and breadth < BREADTH_FLAG_THRESHOLD,
        constituents_priced=row.constituents_priced,
        constituents_total=row.constituents_total,
        coverage_ratio=ratio,
        interpretation=interpretation_for(basket.purity_grade, basket.is_demand_side),
        caveat_note=" ".join(caveats),
    )
