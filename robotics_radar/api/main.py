"""FastAPI application. Read-only JSON.

Deliberately absent, and not oversights:

* No "what flipped this week" banner. It would require constraint state
  changes, which require severity scoring, which does not exist.
* No constraint score on a basket card. Baskets link a node by name only.
* No top-mover attribution. It is guarded in the computation layer and stays
  off until price coverage is confirmed complete for the basket in question.
"""

from __future__ import annotations

from fastapi import FastAPI

from robotics_radar.api.routes import baskets, health, nodes, series
from robotics_radar.config import get_settings
from robotics_radar.logging import configure_logging

DESCRIPTION = """
Research API tracking supply-chain bottlenecks in the humanoid and
mobile-manipulation buildout, plus an equity baskets layer mapping listed
companies to each constraint.

**Read this before reading any number.**

Robotics has no spot price series: nothing rents, nothing trades, there is no
roller screw print. The constraint side therefore rests on two substitutes --
customs unit values as a synthetic monthly price series, and machine-tool
order data reading capacity expansion one layer below the visible constraint.
Cadence is monthly, not daily.

Nothing in robotics is tight today and unit volumes are trivial. This is a
forward map of what breaks first as volume scales, **not** a live tightness
gauge.

On the equity side, almost no listed name derives more than low single-digit
revenue from humanoids. `purity_grade` is a first-class field: a NARRATIVE
basket moving is sentiment, not constraint.
"""

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="Robotics Constraint Radar",
    description=DESCRIPTION,
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.include_router(health.router)
app.include_router(nodes.router)
app.include_router(series.router)
app.include_router(baskets.router)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "name": "Robotics Constraint Radar",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
