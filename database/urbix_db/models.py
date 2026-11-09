"""Shared relational schema.

Geometry is stored as GeoJSON text so the same models run on SQLite and PostgreSQL.
database/migrations/001_postgis.sql adds PostGIS geometry columns and GIST indexes
when the dialect is PostgreSQL.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class GeoUnit(Base):
    __tablename__ = "geo_units"
    __table_args__ = (UniqueConstraint("level_code", "slug", name="uq_geo_level_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("geo_units.id"), index=True)
    level_code: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(256), index=True)
    slug: Mapped[str] = mapped_column(String(160), index=True)
    official_code: Mapped[str | None] = mapped_column(String(64), index=True)
    country_code: Mapped[str | None] = mapped_column(String(2), index=True)
    timezone: Mapped[str | None] = mapped_column(String(64))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    area_km2: Mapped[float | None] = mapped_column(Float)
    boundary_geojson: Mapped[str | None] = mapped_column(Text)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    integration_status: Mapped[str] = mapped_column(String(32), default="reference", index=True)


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    provider: Mapped[str] = mapped_column(String(256))
    homepage_url: Mapped[str | None] = mapped_column(Text)
    terms_url: Mapped[str | None] = mapped_column(Text)
    access_mode: Mapped[str] = mapped_column(String(32), default="public_api")
    notes: Mapped[str | None] = mapped_column(Text)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("data_sources.id"))
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    domain: Mapped[str] = mapped_column(String(40), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80), index=True)
    availability: Mapped[str] = mapped_column(String(32), index=True)
    endpoint_url: Mapped[str | None] = mapped_column(Text)
    data_format: Mapped[str | None] = mapped_column(String(40))
    geo_resolution: Mapped[str | None] = mapped_column(String(120))
    temporal_resolution: Mapped[str | None] = mapped_column(String(120))
    coverage_start: Mapped[str | None] = mapped_column(String(40))
    coverage_end: Mapped[str | None] = mapped_column(String(40))
    update_frequency: Mapped[str | None] = mapped_column(String(80))
    license_name: Mapped[str | None] = mapped_column(String(160))
    license_url: Mapped[str | None] = mapped_column(Text)
    limitations: Mapped[str] = mapped_column(Text, default="")
    verified_on: Mapped[str | None] = mapped_column(String(20))
    schema_json: Mapped[dict] = mapped_column(JSON, default=dict)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(24), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_written: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)


class DataQualityCheck(Base):
    __tablename__ = "data_quality_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    job_id: Mapped[str | None] = mapped_column(String(36))
    check_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str] = mapped_column(Text, default="")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TrafficObservation(Base):
    __tablename__ = "traffic_observations"
    __table_args__ = (
        UniqueConstraint("dataset_code", "source_row_id", name="uq_traffic_source_row"),
        Index("ix_traffic_city_time", "city_slug", "observed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80), index=True)
    geo_unit_id: Mapped[str | None] = mapped_column(String(36), index=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    borough: Mapped[str | None] = mapped_column(String(80), index=True)
    segment_id: Mapped[str | None] = mapped_column(String(64), index=True)
    street: Mapped[str | None] = mapped_column(String(256))
    direction: Mapped[str | None] = mapped_column(String(32))
    volume: Mapped[float | None] = mapped_column(Float)
    speed_mph: Mapped[float | None] = mapped_column(Float)
    travel_time_sec: Mapped[float | None] = mapped_column(Float)
    h3_index: Mapped[str | None] = mapped_column(String(20), index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    geometry_geojson: Mapped[str | None] = mapped_column(Text)
    source_row_id: Mapped[str] = mapped_column(String(128))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)


class EnvironmentalObservation(Base):
    __tablename__ = "environmental_observations"
    __table_args__ = (
        UniqueConstraint("dataset_code", "source_row_id", name="uq_env_source_row"),
        Index("ix_env_param_time", "parameter", "observed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80), index=True)
    geo_unit_id: Mapped[str | None] = mapped_column(String(36), index=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    parameter: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40))
    aggregation: Mapped[str | None] = mapped_column(String(80))
    methodology: Mapped[str] = mapped_column(Text, default="")
    place_name: Mapped[str | None] = mapped_column(String(256))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    source_row_id: Mapped[str] = mapped_column(String(160))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)


class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    __table_args__ = (
        UniqueConstraint("dataset_code", "source_row_id", name="uq_weather_source_row"),
        Index("ix_weather_city_time", "city_slug", "observed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80), index=True)
    geo_unit_id: Mapped[str | None] = mapped_column(String(36), index=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    parameter: Mapped[str] = mapped_column(String(80), index=True)
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    methodology: Mapped[str] = mapped_column(Text, default="")
    source_row_id: Mapped[str] = mapped_column(String(180))


class PopulationObservation(Base):
    __tablename__ = "population_observations"
    __table_args__ = (UniqueConstraint("dataset_code", "source_row_id", name="uq_pop_source_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80), index=True)
    geo_unit_id: Mapped[str | None] = mapped_column(String(36), index=True)
    place_name: Mapped[str | None] = mapped_column(String(256))
    place_code: Mapped[str | None] = mapped_column(String(64), index=True)
    vintage_year: Mapped[int | None] = mapped_column(Integer, index=True)
    population: Mapped[float | None] = mapped_column(Float)
    metric_kind: Mapped[str] = mapped_column(String(40), default="decennial_count")
    methodology: Mapped[str] = mapped_column(Text, default="")
    source_row_id: Mapped[str] = mapped_column(String(160))


class CrimeAggregate(Base):
    __tablename__ = "crime_aggregates"
    __table_args__ = (UniqueConstraint("dataset_code", "source_row_id", name="uq_crime_agg_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80))
    geo_unit_id: Mapped[str | None] = mapped_column(String(36))
    period_label: Mapped[str] = mapped_column(String(80))
    borough: Mapped[str | None] = mapped_column(String(80), index=True)
    category: Mapped[str | None] = mapped_column(String(80))
    offense: Mapped[str | None] = mapped_column(String(160))
    incident_count: Mapped[int | None] = mapped_column(Integer)
    completeness: Mapped[str] = mapped_column(String(40), default="complete_aggregate")
    methodology: Mapped[str] = mapped_column(Text, default="")
    source_row_id: Mapped[str] = mapped_column(String(180))


class CrimeIncident(Base):
    """Aggregated-source complaint points. Demographic fields are intentionally absent."""

    __tablename__ = "crime_incidents"
    __table_args__ = (UniqueConstraint("dataset_code", "source_row_id", name="uq_crime_incident_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80))
    geo_unit_id: Mapped[str | None] = mapped_column(String(36))
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    borough: Mapped[str | None] = mapped_column(String(80), index=True)
    precinct: Mapped[str | None] = mapped_column(String(16))
    law_category: Mapped[str | None] = mapped_column(String(40))
    offense: Mapped[str | None] = mapped_column(String(160))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    h3_index: Mapped[str | None] = mapped_column(String(20), index=True)
    completeness: Mapped[str] = mapped_column(String(40), default="partial_sample")
    source_row_id: Mapped[str] = mapped_column(String(80))


class WasteObservation(Base):
    __tablename__ = "waste_observations"
    __table_args__ = (UniqueConstraint("dataset_code", "source_row_id", name="uq_waste_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80), index=True)
    geo_unit_id: Mapped[str | None] = mapped_column(String(36))
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    borough: Mapped[str | None] = mapped_column(String(80), index=True)
    district_code: Mapped[str | None] = mapped_column(String(32), index=True)
    refuse_tons: Mapped[float | None] = mapped_column(Float)
    paper_tons: Mapped[float | None] = mapped_column(Float)
    mgp_tons: Mapped[float | None] = mapped_column(Float)
    organics_tons: Mapped[float | None] = mapped_column(Float)
    source_row_id: Mapped[str] = mapped_column(String(80))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)


class TransitStop(Base):
    __tablename__ = "transit_stops"
    __table_args__ = (UniqueConstraint("dataset_code", "stop_id", name="uq_transit_stop"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80))
    geo_unit_id: Mapped[str | None] = mapped_column(String(36))
    stop_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    route_ids: Mapped[str | None] = mapped_column(Text)
    location_type: Mapped[str | None] = mapped_column(String(16))


class TransitRidership(Base):
    __tablename__ = "transit_ridership"
    __table_args__ = (UniqueConstraint("dataset_code", "source_row_id", name="uq_ridership_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80))
    geo_unit_id: Mapped[str | None] = mapped_column(String(36))
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    borough: Mapped[str | None] = mapped_column(String(80))
    station_complex_id: Mapped[str | None] = mapped_column(String(32))
    station_name: Mapped[str | None] = mapped_column(String(256))
    riders: Mapped[float | None] = mapped_column(Float)
    transfers: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    aggregation: Mapped[str] = mapped_column(String(40), default="station_hour")
    source_row_id: Mapped[str] = mapped_column(String(180))


class InfrastructureFeature(Base):
    __tablename__ = "infrastructure_features"
    __table_args__ = (UniqueConstraint("dataset_code", "source_row_id", name="uq_infra_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_code: Mapped[str] = mapped_column(String(80), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80), index=True)
    geo_unit_id: Mapped[str | None] = mapped_column(String(36))
    feature_type: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str | None] = mapped_column(String(256))
    borough: Mapped[str | None] = mapped_column(String(80))
    district_code: Mapped[str | None] = mapped_column(String(32))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(40))
    methodology: Mapped[str] = mapped_column(Text, default="")
    geometry_geojson: Mapped[str | None] = mapped_column(Text)
    source_row_id: Mapped[str] = mapped_column(String(160))
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (UniqueConstraint("domain", "version", name="uq_model_domain_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    domain: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[str] = mapped_column(String(40))
    algorithm: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(160))
    horizon: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), index=True)
    dataset_codes: Mapped[list] = mapped_column(JSON, default=list)
    feature_names: Mapped[list] = mapped_column(JSON, default=list)
    train_start: Mapped[str | None] = mapped_column(String(40))
    train_end: Mapped[str | None] = mapped_column(String(40))
    test_start: Mapped[str | None] = mapped_column(String(40))
    test_end: Mapped[str | None] = mapped_column(String(40))
    limitations: Mapped[str] = mapped_column(Text, default="")
    artifact_path: Mapped[str | None] = mapped_column(Text)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"), index=True)
    metric_name: Mapped[str] = mapped_column(String(40))
    metric_value: Mapped[float | None] = mapped_column(Float)
    baseline_name: Mapped[str | None] = mapped_column(String(80))
    baseline_value: Mapped[float | None] = mapped_column(Float)
    n_train: Mapped[int | None] = mapped_column(Integer)
    n_test: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (Index("ix_predictions_model_time", "model_version_id", "target_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"), index=True)
    geo_unit_id: Mapped[str | None] = mapped_column(String(36))
    place_name: Mapped[str | None] = mapped_column(String(256))
    target_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    predicted_value: Mapped[float | None] = mapped_column(Float)
    lower: Mapped[float | None] = mapped_column(Float)
    upper: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    city_slug: Mapped[str | None] = mapped_column(String(80))
    district_slug: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="completed")
    answer: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str | None] = mapped_column(ForeignKey("investigations.id"))
    planner: Mapped[str] = mapped_column(String(40))
    tools_called: Mapped[list] = mapped_column(JSON, default=list)
    trace: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntelligenceReport(Base):
    __tablename__ = "intelligence_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    city_slug: Mapped[str | None] = mapped_column(String(80))
    district_slug: Mapped[str | None] = mapped_column(String(160))
    period_label: Mapped[str | None] = mapped_column(String(120))
    body: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReportEvidence(Base):
    __tablename__ = "report_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("intelligence_reports.id"), index=True)
    claim_type: Mapped[str] = mapped_column(String(32))
    statement: Mapped[str] = mapped_column(Text)
    dataset_code: Mapped[str | None] = mapped_column(String(80))
    support: Mapped[dict] = mapped_column(JSON, default=dict)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    source_path: Mapped[str] = mapped_column(String(400), unique=True)
    body: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(JSON)


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    domain: Mapped[str] = mapped_column(String(40), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80))
    geo_unit_id: Mapped[str | None] = mapped_column(String(36))
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[float | None] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    domain: Mapped[str] = mapped_column(String(40), index=True)
    city_slug: Mapped[str | None] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(256))
    detail: Mapped[str] = mapped_column(Text)
    dataset_code: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="open")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    component: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
