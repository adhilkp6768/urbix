from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from urbix_data.catalog import DATASETS, SOURCES
from urbix_db.models import (
    CrimeAggregate,
    CrimeIncident,
    DataQualityCheck,
    DataSource,
    Dataset,
    EnvironmentalObservation,
    GeoUnit,
    InfrastructureFeature,
    IngestionJob,
    PopulationObservation,
    SystemLog,
    TrafficObservation,
    TransitRidership,
    TransitStop,
    WasteObservation,
    WeatherObservation,
)


def new_id() -> str:
    return str(uuid.uuid4())


def stable_geo_id(slug: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"https://urbix.local/geo/{slug}"))


def upsert_catalog(session: Session) -> None:
    sources = {row.code: row for row in session.query(DataSource).all()}
    for item in SOURCES:
        current = sources.get(item["code"])
        if current is None:
            current = DataSource(id=new_id(), code=item["code"])
            session.add(current)
        for key, value in item.items():
            setattr(current, key, value)
    session.flush()
    source_ids = {row.code: row.id for row in session.query(DataSource).all()}
    datasets = {row.code: row for row in session.query(Dataset).all()}
    for item in DATASETS:
        current = datasets.get(item["code"])
        if current is None:
            current = Dataset(id=new_id(), code=item["code"])
            session.add(current)
        payload = dict(item)
        source_code = payload.pop("source_code")
        current.source_id = source_ids.get(source_code)
        for key, value in payload.items():
            setattr(current, key, value)
    session.flush()


def start_job(session: Session, dataset_code: str, parameters: dict | None = None) -> IngestionJob:
    job = IngestionJob(
        id=new_id(),
        dataset_code=dataset_code,
        status="running",
        started_at=datetime.now(timezone.utc),
        parameters=parameters or {},
    )
    session.add(job)
    session.flush()
    return job


def finish_job(session: Session, job: IngestionJob, *, rows: int, status: str, message: str) -> None:
    job.rows_written = rows
    job.status = status
    job.message = message
    job.finished_at = datetime.now(timezone.utc)
    session.add(
        SystemLog(
            level="error" if status == "failed" else "info",
            component="ingestion",
            message=f"{job.dataset_code}: {message}",
            context={"rows": rows, "status": status},
        )
    )


def add_quality(session: Session, dataset_code: str, job_id: str, name: str, status: str, detail: str, metrics: dict | None = None) -> None:
    session.add(
        DataQualityCheck(
            id=new_id(),
            dataset_code=dataset_code,
            job_id=job_id,
            check_name=name,
            status=status,
            detail=detail,
            metrics=metrics or {},
        )
    )


def _existing_ids(session: Session, model, dataset_code: str, ids: list[str], column: str) -> set[str]:
    found: set[str] = set()
    attr = getattr(model, column)
    for index in range(0, len(ids), 400):
        chunk = ids[index : index + 400]
        if not chunk:
            continue
        rows = session.query(attr).filter(model.dataset_code == dataset_code, attr.in_(chunk)).all()
        found.update(row[0] for row in rows)
    return found


def insert_new(session: Session, model, rows: list[dict], key: str = "source_row_id") -> int:
    if not rows:
        return 0
    written = 0
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["dataset_code"], []).append(row)
    for dataset_code, group in grouped.items():
        known = _existing_ids(session, model, dataset_code, [row[key] for row in group], key)
        for row in group:
            if row[key] in known:
                continue
            session.add(model(**row))
            known.add(row[key])
            written += 1
    return written


def get_geo(session: Session, slug: str) -> GeoUnit | None:
    return session.query(GeoUnit).filter(GeoUnit.slug == slug).one_or_none()


def save_geo(session: Session, payload: dict) -> GeoUnit:
    slug = payload["slug"]
    current = get_geo(session, slug)
    if current is None:
        current = GeoUnit(id=payload.get("id") or stable_geo_id(slug), slug=slug, level_code=payload["level_code"], name=payload["name"])
        session.add(current)
    for key, value in payload.items():
        if key == "id":
            continue
        setattr(current, key, value)
    session.flush()
    return current


TRAFFIC = TrafficObservation
ENVIRONMENT = EnvironmentalObservation
WEATHER = WeatherObservation
POPULATION = PopulationObservation
CRIME_AGG = CrimeAggregate
CRIME_POINT = CrimeIncident
WASTE = WasteObservation
STOPS = TransitStop
RIDERS = TransitRidership
INFRA = InfrastructureFeature
