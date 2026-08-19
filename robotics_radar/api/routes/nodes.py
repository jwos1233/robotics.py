from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from robotics_radar.db import get_db
from robotics_radar.models.constraint import Node
from robotics_radar.models.enums import Bucket
from robotics_radar.schemas import NodeOut

router = APIRouter(tags=["constraints"])


@router.get("/nodes", response_model=list[NodeOut])
def list_nodes(
    bucket: Bucket | None = Query(None),
    db: Session = Depends(get_db),
) -> list[Node]:
    stmt = select(Node).order_by(Node.bucket, Node.name)
    if bucket is not None:
        stmt = stmt.where(Node.bucket == bucket)
    return list(db.scalars(stmt))


@router.get("/nodes/{node_id}", response_model=NodeOut)
def get_node(node_id: int, db: Session = Depends(get_db)) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"node {node_id} not found")
    return node
