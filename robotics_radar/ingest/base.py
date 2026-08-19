"""Common fetcher interface: fetch -> normalise -> upsert.

Every source implements this contract. The invariants are not optional:

* Idempotent and re-runnable. Running a fetcher twice over the same period
  must not create a second copy of the same vintage.
* The raw payload is written *before* parsing, so a parser crash still leaves
  the evidence needed to debug it.
* release_date and vintage_date are recorded separately from retrieved_at.
  They answer different questions and conflating them destroys the
  point-in-time property.
* Fail loudly. A fetcher that cannot produce a trustworthy value raises
  IngestError rather than writing a guess or a partial batch.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from robotics_radar.logging import get_logger
from robotics_radar.models.constraint import Observation, RawPayload
from robotics_radar.models.enums import Cadence, FlowDirection

log = get_logger(__name__)


class IngestError(RuntimeError):
    """Raised when a fetch or parse cannot produce a trustworthy result."""


@dataclass(frozen=True)
class SeriesSpec:
    """Identity of a series a fetcher is responsible for."""

    name: str
    node_name: str
    source: str
    cadence: Cadence
    flow_direction: FlowDirection
    geography: str
    partner_geography: str | None = None
    unit: str | None = None
    tariff_code: str | None = None
    tariff_nomenclature: str | None = None
    source_url: str | None = None
    methodology_note: str | None = None
    known_limitations: str | None = None


@dataclass(frozen=True)
class RawResponse:
    url: str
    params: dict
    body: str
    fetched_at: datetime

    @property
    def params_hash(self) -> str:
        blob = json.dumps(self.params, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()


@dataclass(frozen=True)
class NormalisedObservation:
    """One parsed datapoint, before it is attached to a series row."""

    series_key: str
    period_start: date
    period_end: date
    vintage_date: date
    value: float | None = None
    quantity: float | None = None
    quantity_unit: str | None = None
    unit_value: float | None = None
    release_date: date | None = None
    #: Set when a unit value would be arithmetically computable but not
    #: interpretable -- e.g. an aggregate across origins whose product mix
    #: makes the ratio meaningless. Keeps a misleading number out of the store.
    suppress_unit_value: bool = False

    def with_unit_value(self) -> NormalisedObservation:
        """Derive unit value where both legs exist, else leave it None.

        A unit value is only meaningful when value and quantity are on the
        same tariff line for the same period. We never synthesise one from a
        neighbouring period or a different quantity basis, and we decline to
        compute one at all where the caller has marked it uninterpretable.
        """
        if self.suppress_unit_value or self.unit_value is not None:
            return self
        if self.value is None or self.quantity in (None, 0):
            return self
        object.__setattr__(self, "unit_value", self.value / self.quantity)
        return self


class Fetcher(ABC):
    """Base class for a single data source."""

    source_name: str
    #: Set False on sources whose licence forbids storing the raw body.
    persist_raw: bool = True

    @abstractmethod
    def series_specs(self) -> Sequence[SeriesSpec]:
        """Declare the series this fetcher owns."""

    @abstractmethod
    def fetch(self, period: date) -> Iterable[RawResponse]:
        """Retrieve raw payloads for a period. Must not parse."""

    @abstractmethod
    def normalise(self, raw: RawResponse) -> Iterable[NormalisedObservation]:
        """Parse a raw payload into observations. Must not perform I/O."""

    def store_raw(self, session: Session, raw: RawResponse) -> None:
        session.add(
            RawPayload(
                source=self.source_name,
                url=raw.url,
                params_hash=raw.params_hash,
                fetched_at=raw.fetched_at,
                body=raw.body,
                meta={"params": raw.params},
            )
        )
        session.flush()

    def upsert(
        self,
        session: Session,
        series_ids: dict[str, int],
        observations: Iterable[NormalisedObservation],
    ) -> int:
        """Append observations, keyed on (series, period, vintage).

        A repeat run of the same vintage refreshes retrieved_at and nothing
        else. A genuine revision arrives with a later vintage_date and lands
        as a new row, leaving the prior vintage intact.
        """
        rows = []
        for obs in observations:
            series_id = series_ids.get(obs.series_key)
            if series_id is None:
                raise IngestError(
                    f"{self.source_name}: no series registered for key {obs.series_key!r}"
                )
            rows.append(
                {
                    "series_id": series_id,
                    "period_start": obs.period_start,
                    "period_end": obs.period_end,
                    "value": obs.value,
                    "quantity": obs.quantity,
                    "quantity_unit": obs.quantity_unit,
                    "unit_value": obs.unit_value,
                    "vintage_date": obs.vintage_date,
                    "release_date": obs.release_date,
                }
            )
        if not rows:
            return 0

        stmt = insert(Observation).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_observations_vintage",
            set_={"retrieved_at": datetime.now().astimezone()},
        )
        session.execute(stmt)
        return len(rows)

    def run(self, session: Session, series_ids: dict[str, int], period: date) -> int:
        """fetch -> store raw -> normalise -> upsert, as one transaction."""
        written = 0
        for raw in self.fetch(period):
            if self.persist_raw:
                self.store_raw(session, raw)
            try:
                observations = [o.with_unit_value() for o in self.normalise(raw)]
            except IngestError:
                raise
            except Exception as exc:  # noqa: BLE001 - re-raised as IngestError
                log.error(
                    "normalise_failed",
                    source=self.source_name,
                    url=raw.url,
                    period=str(period),
                    error=str(exc),
                )
                raise IngestError(f"{self.source_name}: normalise failed for {raw.url}") from exc
            written += self.upsert(session, series_ids, observations)
        log.info("ingest_complete", source=self.source_name, period=str(period), rows=written)
        return written
