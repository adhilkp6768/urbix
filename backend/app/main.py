from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import ROOT, settings
from app.services import query
from app.services import refresh as refresh_service
from urbix_ai.graph import ALLOWED_CONNECTORS, build_report, investigate
from urbix_data.pipeline import run_connector
from urbix_data.repository import upsert_catalog
from urbix_db.session import init_db, make_engine, make_session_factory
from urbix_ml.trainers import train_domain

engine = make_engine(settings.database_url)
init_db(engine)
SessionLocal = make_session_factory(engine)
RATE: dict[str, deque] = defaultdict(deque)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    session = SessionLocal()
    try:
        upsert_catalog(session)
        query.index_documents(session, ROOT)
        session.commit()
    finally:
        session.close()
    if settings.urbix_bootstrap_on_start or settings.urbix_refresh_hours > 0:
        refresh_service.start_if_stale(SessionLocal, settings.urbix_refresh_hours)
    if settings.urbix_refresh_hours > 0:
        threading.Thread(
            target=refresh_service.serve,
            args=(SessionLocal, settings.urbix_refresh_hours),
            name="urbix-refresh-schedule",
            daemon=True,
        ).start()
    yield


app = FastAPI(title="URBIX", version="0.1.0", description="Global Urban Intelligence Platform API", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def require_write(api_key: str | None) -> None:
    if settings.urbix_api_key and api_key != settings.urbix_api_key:
        raise HTTPException(status_code=401, detail="API key required.")
    now = time.time()
    bucket = RATE["write"]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= 60:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
    bucket.append(now)


@app.exception_handler(Exception)
async def unexpected(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/api/v1/health")
def health():
    session = SessionLocal()
    try:
        cities = session.query(query.GeoUnit).count()
        return {"status": "ok", "dialect": engine.dialect.name, "geo_units": cities, "llm_configured": bool(settings.openai_api_key), "openaq_configured": bool(settings.openaq_api_key)}
    finally:
        session.close()


@app.get("/api/v1/geography/world")
def geography_world():
    session = SessionLocal()
    try:
        return query.world(session)
    finally:
        session.close()


@app.get("/api/v1/geography/countries")
def geography_countries():
    session = SessionLocal()
    try:
        return {"results": query.countries(session)}
    finally:
        session.close()


@app.get("/api/v1/geography/countries/{country_code}/cities")
def geography_cities(country_code: str):
    session = SessionLocal()
    try:
        return {"results": query.cities_for_country(session, country_code)}
    finally:
        session.close()


@app.get("/api/v1/geography/cities/{city_id}")
def geography_city(city_id: str):
    session = SessionLocal()
    try:
        city = query.city_detail(session, city_id)
        if city is None:
            raise HTTPException(404, "City not found.")
        return city
    finally:
        session.close()


@app.get("/api/v1/geography/cities/{city_id}/districts")
def geography_districts(city_id: str, kind: str | None = None):
    session = SessionLocal()
    try:
        return {"results": query.districts(session, city_id, kind)}
    finally:
        session.close()


@app.get("/api/v1/geography/regions/{region_id}")
def geography_region(region_id: str):
    session = SessionLocal()
    try:
        city = query.city_detail(session, region_id)
        if city is None:
            raise HTTPException(404, "Region not found.")
        return city
    finally:
        session.close()


@app.get("/api/v1/geography/search")
def geography_search(q: str = Query(min_length=2)):
    session = SessionLocal()
    try:
        return {"results": query.search_geo(session, q)}
    finally:
        session.close()


@app.get("/api/v1/cities")
def cities():
    session = SessionLocal()
    try:
        return {"results": [row for row in query.world(session)["cities"]]}
    finally:
        session.close()


@app.get("/api/v1/cities/{city_id}/overview")
def city_overview(city_id: str):
    session = SessionLocal()
    try:
        overview = query.city_overview(session, city_id)
        if overview.get("reason"):
            raise HTTPException(404, overview["reason"])
        return overview
    finally:
        session.close()


@app.get("/api/v1/cities/{city_id}/indicators")
def city_indicators(city_id: str):
    return city_overview(city_id)


@app.get("/api/v1/maps/layers")
def map_layers():
    return {
        "layers": [
            {"id": "admin", "label": "Administrative boundaries", "geometry": "polygon"},
            {"id": "traffic", "label": "Link speeds", "geometry": "line"},
            {"id": "environment", "label": "DOHMH PM2.5 boroughs", "geometry": "polygon"},
            {"id": "waste", "label": "DSNY refuse", "geometry": "polygon"},
            {"id": "transit", "label": "Subway stops", "geometry": "point"},
            {"id": "roads", "label": "OSM motorway and trunk", "geometry": "line"},
            {"id": "population", "label": "Population", "geometry": "withheld"},
            {"id": "crime", "label": "Crime points", "geometry": "withheld"},
        ]
    }


@app.get("/api/v1/maps/geojson")
def map_geojson(city: str = "nyc", layer: str = "admin"):
    session = SessionLocal()
    try:
        return query.map_layer(session, city, layer)
    finally:
        session.close()


@app.get("/api/v1/maps/features")
def map_features(city: str = "nyc", layer: str = "admin"):
    return map_geojson(city, layer)


def _domain(fn, city: str):
    session = SessionLocal()
    try:
        return fn(session, city)
    finally:
        session.close()


@app.get("/api/v1/traffic/observations")
def traffic_observations(city: str = "nyc", limit: int = 100, offset: int = 0):
    session = SessionLocal()
    try:
        rows = session.query(query.TrafficObservation).filter(query.TrafficObservation.city_slug == city).offset(offset).limit(min(limit, 500)).all()
        return {"results": [{"dataset_code": row.dataset_code, "observed_at": row.observed_at.isoformat() if row.observed_at else None, "borough": row.borough, "street": row.street, "volume": row.volume, "speed_mph": row.speed_mph, "attributes": row.attributes} for row in rows]}
    finally:
        session.close()


@app.get("/api/v1/traffic/trends")
def traffic_trends(city: str = "nyc"):
    return _domain(query.traffic_analytics, city)


@app.get("/api/v1/traffic/predictions")
def traffic_predictions(city: str = "nyc"):
    session = SessionLocal()
    try:
        models = [row for row in query.model_catalog(session) if row["domain"] == "traffic"]
        supported = [row for row in models if row["horizon"] in {"next_hour", "next_6_hours", "next_24_hours"} and row["status"] == "trained"]
        return {"city": city, "operational_horizons": supported, "models": models, "note": "ATR data supports sampled-hour evaluation only. Operational hourly horizons are returned only when a validated model exists."}
    finally:
        session.close()


@app.get("/api/v1/environment/observations")
def environment_observations(city: str = "nyc", limit: int = 100, offset: int = 0):
    session = SessionLocal()
    try:
        rows = session.query(query.EnvironmentalObservation).filter(query.EnvironmentalObservation.city_slug == city).offset(offset).limit(min(limit, 500)).all()
        return {"results": [{"dataset_code": row.dataset_code, "parameter": row.parameter, "value": row.value, "unit": row.unit, "place_name": row.place_name, "observed_at": row.observed_at.isoformat() if row.observed_at else None, "methodology": row.methodology} for row in rows]}
    finally:
        session.close()


@app.get("/api/v1/environment/trends")
def environment_trends(city: str = "nyc"):
    return _domain(query.environment_analytics, city)


@app.get("/api/v1/environment/predictions")
def environment_predictions(city: str = "nyc"):
    session = SessionLocal()
    try:
        models = [row for row in query.model_catalog(session) if row["domain"] == "environment"]
        return {"city": city, "models": models, "note": "DOHMH annual indicators are not used as hourly forecasts. A 24-hour horizon applies only to a validated grid model."}
    finally:
        session.close()


@app.get("/api/v1/crime/analytics")
def crime(city: str = "nyc"):
    return _domain(query.crime_analytics, city)


@app.get("/api/v1/population/analytics")
def population(city: str = "nyc"):
    return _domain(query.population_analytics, city)


@app.get("/api/v1/transport/analytics")
def transport(city: str = "nyc"):
    return _domain(query.transport_analytics, city)


@app.get("/api/v1/waste/analytics")
def waste(city: str = "nyc"):
    return _domain(query.waste_analytics, city)


@app.get("/api/v1/infrastructure/analytics")
def infrastructure(city: str = "nyc"):
    return _domain(query.infrastructure_analytics, city)


@app.get("/api/v1/analysis/correlations")
def analysis(city: str = "nyc"):
    return _domain(query.correlations, city)


@app.get("/api/v1/compare")
def compare(left: str, right: str):
    session = SessionLocal()
    try:
        return query.compare_geographies(session, left, right)
    finally:
        session.close()


@app.get("/api/v1/models")
def models():
    session = SessionLocal()
    try:
        return {"results": query.model_catalog(session)}
    finally:
        session.close()


@app.get("/api/v1/models/performance")
def model_performance():
    return models()


@app.post("/api/v1/predictions/run")
def run_predictions(payload: dict, x_api_key: str | None = Header(default=None)):
    require_write(x_api_key)
    domain = payload.get("domain", "traffic")
    session = SessionLocal()
    try:
        result = train_domain(session, domain)
        session.commit()
        return result
    finally:
        session.close()


@app.post("/api/v1/ai/query")
def ai_query(payload: dict, x_api_key: str | None = Header(default=None)):
    require_write(x_api_key)
    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "Question is required.")
    session = SessionLocal()
    try:
        answer = investigate(session, question, payload.get("city") or "nyc")
        session.commit()
        return answer
    finally:
        session.close()


@app.post("/api/v1/ai/investigations")
def create_investigation(payload: dict, x_api_key: str | None = Header(default=None)):
    return ai_query(payload, x_api_key)


@app.get("/api/v1/ai/investigations/{investigation_id}")
def get_investigation(investigation_id: str):
    session = SessionLocal()
    try:
        row = session.query(query.Investigation).filter(query.Investigation.id == investigation_id).one_or_none()
        if row is None:
            raise HTTPException(404, "Investigation not found.")
        return {"id": row.id, "question": row.question, "city": row.city_slug, "answer": row.answer, "created_at": row.created_at.isoformat() if row.created_at else None}
    finally:
        session.close()


@app.get("/api/v1/ai/investigations")
def investigations():
    session = SessionLocal()
    try:
        rows = session.query(query.Investigation).order_by(query.Investigation.created_at.desc()).limit(50).all()
        return {"results": [{"id": row.id, "question": row.question, "city": row.city_slug, "created_at": row.created_at.isoformat() if row.created_at else None} for row in rows]}
    finally:
        session.close()


@app.get("/api/v1/ai/reports")
def reports():
    session = SessionLocal()
    try:
        rows = session.query(query.IntelligenceReport).order_by(query.IntelligenceReport.created_at.desc()).limit(50).all()
        return {"results": [{"id": row.id, "title": row.title, "city": row.city_slug, "body": row.body, "created_at": row.created_at.isoformat() if row.created_at else None} for row in rows]}
    finally:
        session.close()


@app.post("/api/v1/ai/reports")
def create_report(payload: dict | None = None, x_api_key: str | None = Header(default=None)):
    require_write(x_api_key)
    session = SessionLocal()
    try:
        report = build_report(session, (payload or {}).get("city") or "nyc")
        session.commit()
        return report
    finally:
        session.close()


@app.get("/api/v1/alerts")
def alerts():
    session = SessionLocal()
    try:
        query.refresh_alerts(session)
        session.commit()
        return {"results": query.list_alerts(session)}
    finally:
        session.close()


@app.get("/api/v1/anomalies")
def anomalies():
    session = SessionLocal()
    try:
        return {"results": query.list_anomalies(session)}
    finally:
        session.close()


@app.get("/api/v1/data-sources")
def data_sources():
    session = SessionLocal()
    try:
        return query.list_sources(session)
    finally:
        session.close()


@app.get("/api/v1/data-quality")
def data_quality():
    session = SessionLocal()
    try:
        return {"checks": query.quality_report(session), "jobs": query.list_jobs(session)}
    finally:
        session.close()


@app.get("/api/v1/system/freshness")
def system_freshness():
    session = SessionLocal()
    try:
        return {"refresh": refresh_service.snapshot(), "datasets": query.dataset_freshness(session)}
    finally:
        session.close()


@app.post("/api/v1/system/refresh")
def system_refresh(payload: dict | None = None, x_api_key: str | None = Header(default=None)):
    require_write(x_api_key)
    scope = str((payload or {}).get("scope") or "current")
    if scope not in {"current", "full"}:
        raise HTTPException(400, "Scope must be current or full.")
    started = refresh_service.start(SessionLocal, scope)
    body = {"started": started, **refresh_service.snapshot()}
    return JSONResponse(body, status_code=202 if started else 200)


@app.get("/api/v1/connectors")
def connectors():
    return {"results": sorted(ALLOWED_CONNECTORS)}


@app.post("/api/v1/connectors/{code}/run")
def run_named_connector(code: str, payload: dict | None = None, x_api_key: str | None = Header(default=None)):
    require_write(x_api_key)
    if code not in ALLOWED_CONNECTORS:
        raise HTTPException(404, "Connector is not registered.")
    session = SessionLocal()
    try:
        result = run_connector(session, code, payload or {})
        session.commit()
        return result
    finally:
        session.close()
