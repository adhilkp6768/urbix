from __future__ import annotations

import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from urbix_db.models import (
    Alert,
    Anomaly,
    CrimeAggregate,
    CrimeIncident,
    DataQualityCheck,
    DataSource,
    Dataset,
    EnvironmentalObservation,
    GeoUnit,
    InfrastructureFeature,
    IngestionJob,
    IntelligenceReport,
    Investigation,
    KnowledgeDocument,
    ModelEvaluation,
    ModelVersion,
    PopulationObservation,
    ReportEvidence,
    TrafficObservation,
    TransitRidership,
    TransitStop,
    WasteObservation,
    WeatherObservation,
)
from urbix_ml.metrics import pearson

from app.services import city_domains

NYC_PROFILE = "nyc"

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def _mean(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _round(value: float | None, digits: int = 1) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def kpi(label: str, value, unit: str, dataset_code: str, methodology: str, period: str | None = None, availability: str = "available") -> dict:
    if value is None:
        availability = "unavailable"
    return {
        "label": label,
        "value": _round(value) if isinstance(value, float) else value,
        "unit": unit,
        "dataset_code": dataset_code,
        "methodology": methodology,
        "period": period,
        "availability": availability,
    }


def source_card(session: Session, code: str) -> dict | None:
    dataset = session.query(Dataset).filter(Dataset.code == code).one_or_none()
    if dataset is None:
        return None
    return {
        "code": dataset.code,
        "name": dataset.name,
        "availability": dataset.availability,
        "endpoint_url": dataset.endpoint_url,
        "limitations": dataset.limitations,
        "license_name": dataset.license_name,
        "temporal_resolution": dataset.temporal_resolution,
        "geo_resolution": dataset.geo_resolution,
        "coverage_start": dataset.coverage_start,
        "coverage_end": dataset.coverage_end,
    }


def _city(session: Session, slug: str) -> GeoUnit | None:
    return session.query(GeoUnit).filter(GeoUnit.slug == slug).one_or_none()


def _descendants(session: Session, root: GeoUnit) -> list[GeoUnit]:
    children = session.query(GeoUnit).filter(GeoUnit.parent_id == root.id).all()
    output = list(children)
    for child in children:
        output.extend(_descendants(session, child))
    return output


def _feature(geo: GeoUnit, value=None, extra: dict | None = None) -> dict | None:
    if not geo.boundary_geojson:
        if geo.latitude is None:
            return None
        geometry = {"type": "Point", "coordinates": [geo.longitude, geo.latitude]}
    else:
        geometry = json.loads(geo.boundary_geojson)
    properties = {
        "id": geo.id,
        "slug": geo.slug,
        "name": geo.name,
        "level": geo.level_code,
        "kind": (geo.properties or {}).get("kind"),
        "value": value,
        "availability": "available" if value is not None else "unavailable",
    }
    if extra:
        properties.update(extra)
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def _city_coverage(session: Session) -> dict[str, dict]:
    """Count connected domains per city so the UI can separate deep extracts from weather-only stubs."""
    domains: dict[str, set[str]] = defaultdict(set)
    for slug, in session.query(TrafficObservation.city_slug).filter(TrafficObservation.city_slug.isnot(None)).distinct():
        domains[slug].add("traffic")
    for slug, in session.query(CrimeAggregate.city_slug).filter(CrimeAggregate.city_slug.isnot(None)).distinct():
        domains[slug].add("crime")
    for slug, in session.query(CrimeIncident.city_slug).filter(CrimeIncident.city_slug.isnot(None)).distinct():
        domains[slug].add("crime")
    for slug, in session.query(PopulationObservation.city_slug).filter(PopulationObservation.city_slug.isnot(None)).distinct():
        domains[slug].add("population")
    for slug, in session.query(WasteObservation.city_slug).filter(WasteObservation.city_slug.isnot(None)).distinct():
        domains[slug].add("waste")
    for slug, in session.query(TransitStop.city_slug).filter(TransitStop.city_slug.isnot(None)).distinct():
        domains[slug].add("transport")
    for slug, in (
        session.query(InfrastructureFeature.city_slug)
        .filter(InfrastructureFeature.city_slug.isnot(None), InfrastructureFeature.feature_type == "major_road")
        .distinct()
    ):
        domains[slug].add("infrastructure")
    for slug, in (
        session.query(EnvironmentalObservation.city_slug)
        .filter(EnvironmentalObservation.city_slug.isnot(None), EnvironmentalObservation.dataset_code != "open-meteo-air-quality")
        .distinct()
    ):
        domains[slug].add("environment")
    weather_only = {
        slug
        for (slug,) in session.query(WeatherObservation.city_slug).filter(WeatherObservation.city_slug.isnot(None)).distinct()
    }
    coverage = {}
    for slug in set(domains) | weather_only:
        connected = sorted(domains.get(slug, set()))
        if "environment" not in connected and slug in weather_only:
            # Modelled Open-Meteo weather/air alone counts as a thin environment stub.
            pass
        depth = "deep" if len(connected) >= 4 else ("broad" if len(connected) >= 2 else ("thin" if connected or slug in weather_only else "reference"))
        if not connected and slug in weather_only:
            depth = "weather"
        coverage[slug] = {"domains": connected, "domain_count": len(connected), "depth": depth, "has_weather": slug in weather_only}
    return coverage


def world(session: Session) -> dict:
    cities = session.query(GeoUnit).filter(GeoUnit.level_code == "city").all()
    countries = session.query(GeoUnit).filter(GeoUnit.level_code == "country").all()
    integrated = [city for city in cities if city.integration_status in {"partial", "integrated"}]
    coverage = _city_coverage(session)
    serialized = []
    for city in cities:
        item = serialize_geo(city)
        info = coverage.get(city.slug) or {"domains": [], "domain_count": 0, "depth": "reference", "has_weather": False}
        item.update(info)
        serialized.append(item)
    deep = sum(1 for item in serialized if item.get("depth") in {"deep", "broad"})
    return {
        "availability": "partial" if integrated else "unavailable",
        "countries": len(countries),
        "cities_referenced": len(cities),
        "cities_with_data": len(integrated),
        "cities_with_broad_extracts": deep,
        "note": "Global figures count integrated cities only. Deep extracts cover several official domains; weather-only cities still show modelled Open-Meteo readings and stay blank elsewhere.",
        "cities": serialized,
    }


def serialize_geo(geo: GeoUnit) -> dict:
    return {
        "id": geo.id,
        "slug": geo.slug,
        "name": geo.name,
        "level": geo.level_code,
        "country_code": geo.country_code,
        "latitude": geo.latitude,
        "longitude": geo.longitude,
        "area_km2": _round(geo.area_km2, 2),
        "integration_status": geo.integration_status,
        "parent_id": geo.parent_id,
        "official_code": geo.official_code,
        "kind": (geo.properties or {}).get("kind"),
        "centroid_method": (geo.properties or {}).get("centroid_method"),
    }


def countries(session: Session) -> list[dict]:
    return [serialize_geo(row) for row in session.query(GeoUnit).filter(GeoUnit.level_code == "country").order_by(GeoUnit.name).all()]


def cities_for_country(session: Session, country_code: str) -> list[dict]:
    return [
        serialize_geo(row)
        for row in session.query(GeoUnit).filter(GeoUnit.level_code == "city", GeoUnit.country_code == country_code.upper()).order_by(GeoUnit.name).all()
    ]


def city_detail(session: Session, slug: str) -> dict | None:
    city = _city(session, slug)
    if city is None:
        return None
    return serialize_geo(city)


def districts(session: Session, slug: str, kind: str | None = None) -> list[dict]:
    city = _city(session, slug)
    if city is None:
        return []
    rows = [row for row in _descendants(session, city) if row.level_code in {"district", "neighbourhood"}]
    if kind:
        rows = [row for row in rows if (row.properties or {}).get("kind") == kind]
    return [serialize_geo(row) for row in rows]


def search_geo(session: Session, text: str) -> list[dict]:
    like = f"%{text.strip()}%"
    rows = session.query(GeoUnit).filter(GeoUnit.name.ilike(like)).limit(20).all()
    return [serialize_geo(row) for row in rows]


def traffic_analytics(session: Session, slug: str) -> dict:
    if slug != NYC_PROFILE:
        return city_domains.traffic(session, slug)
    speeds = session.query(TrafficObservation).filter(TrafficObservation.city_slug == slug, TrafficObservation.dataset_code == "nyc-traffic-speeds").all()
    samples = session.query(TrafficObservation).filter(TrafficObservation.city_slug == slug, TrafficObservation.dataset_code == "nyc-atr-counts").all()
    crashes = session.query(TrafficObservation).filter(TrafficObservation.city_slug == slug, TrafficObservation.dataset_code == "nypd-crashes").all()
    speed_values = [row.speed_mph for row in speeds]
    snapshot = max((row.observed_at for row in speeds if row.observed_at), default=None)
    by_borough: dict[str, list[float]] = defaultdict(list)
    for row in speeds:
        if row.borough and row.speed_mph is not None:
            by_borough[row.borough].append(row.speed_mph)
    hour_bins: dict[int, list[float]] = defaultdict(list)
    for row in samples:
        if row.observed_at and row.volume is not None:
            hour_bins[row.observed_at.hour].append(row.volume)
    peak = None
    if hour_bins:
        hour, values = max(hour_bins.items(), key=lambda item: _mean(item[1]) or -1)
        peak = {"hour": hour, "mean_volume": _round(_mean(values)), "n": len(values), "definition": "Highest mean ATR sample volume by hour. Samples do not cover every road-hour."}
    rankings = [
        {"name": name, "value": _round(_mean(values)), "unit": "mph", "n": len(values)}
        for name, values in sorted(by_borough.items(), key=lambda item: _mean(item[1]) or -1)
    ]
    crash_total = sum((row.attributes or {}).get("crash_count") or 0 for row in crashes) or None
    if crashes and crash_total == 0:
        crash_total = None
    return {
        "availability": "partial" if speeds or samples else "unavailable",
        "kpis": [
            kpi("Mean link speed", _mean(speed_values), "mph", "nyc-traffic-speeds", "Unweighted mean of links in the current DOT snapshot, including published zeros. A zero is a reported value, not a missing measurement. This is not a citywide congestion index.", snapshot.isoformat() if snapshot else None),
            kpi("Links in snapshot", len(speeds) or None, "links", "nyc-traffic-speeds", "Count of speed links returned by the current extract.", snapshot.isoformat() if snapshot else None),
            kpi("ATR samples loaded", len(samples) or None, "samples", "nyc-atr-counts", "Bounded extract of automated counts. Absence of a sample is not zero volume.", None),
            kpi("Reported crashes in aggregate window", crash_total, "crashes", "nypd-crashes", "Borough sum of police-reported collisions for the ingested window.", crashes[0].attributes.get("window_start") if crashes else None),
        ],
        "series": [{"name": f"{hour:02d}:00", "value": _round(_mean(values)), "n": len(values)} for hour, values in sorted(hour_bins.items())],
        "series_label": "Mean ATR sample volume by hour",
        "rankings": rankings,
        "peak": peak,
        "sources": [card for card in (source_card(session, code) for code in ("nyc-traffic-speeds", "nyc-atr-counts", "nypd-crashes")) if card],
        "limitations": [
            "Link speeds are a current snapshot, not a historical time series.",
            "ATR counts are samples. Peak hour is the peak among sampled bins only.",
            "No next-hour traffic forecast is published unless a model version with that horizon has been validated.",
        ],
    }


def environment_analytics(session: Session, slug: str) -> dict:
    if slug != NYC_PROFILE:
        return city_domains.environment(session, slug)
    official = (
        session.query(EnvironmentalObservation)
        .filter(EnvironmentalObservation.city_slug == slug, EnvironmentalObservation.dataset_code == "nyc-air-quality", EnvironmentalObservation.parameter == "Fine particles (PM 2.5)", EnvironmentalObservation.value.isnot(None))
        .all()
    )
    latest_period = max((row.attributes or {}).get("time_period") or "" for row in official) if official else None
    current = [row for row in official if latest_period and (row.attributes or {}).get("time_period") == latest_period and (row.attributes or {}).get("geo_type") in {"CD", "Borough", "Citywide"}]
    annual = [row for row in current if (row.aggregation or "").lower().startswith("annual")]
    chosen = annual or current
    weather_query = session.query(WeatherObservation).filter(WeatherObservation.city_slug == slug, WeatherObservation.parameter == "temperature_2m", WeatherObservation.value.isnot(None))
    city = _city(session, slug)
    city_weather = []
    if city is not None:
        city_weather = weather_query.filter(WeatherObservation.geo_unit_id == city.id).order_by(WeatherObservation.observed_at.desc()).limit(72).all()
    weather = city_weather or weather_query.order_by(WeatherObservation.observed_at.desc()).limit(48).all()
    modelled = (
        session.query(EnvironmentalObservation)
        .filter(EnvironmentalObservation.city_slug == slug, EnvironmentalObservation.dataset_code == "open-meteo-air-quality", EnvironmentalObservation.parameter == "pm2_5", EnvironmentalObservation.value.isnot(None))
        .order_by(EnvironmentalObservation.observed_at.desc())
        .limit(48)
        .all()
    )
    rankings = [
        {"name": row.place_name, "value": _round(row.value, 2), "unit": row.unit, "geo_type": (row.attributes or {}).get("geo_type")}
        for row in sorted(chosen, key=lambda item: item.value or -1, reverse=True)[:15]
    ]
    return {
        "availability": "available" if chosen or weather else "unavailable",
        "kpis": [
            kpi("DOHMH PM2.5 places in latest loaded period", len(chosen) or None, "places", "nyc-air-quality", "Count of annual or seasonal PM2.5 indicator rows in the latest ingested time_period. Not a citywide average unless a citywide row is present.", latest_period),
            kpi("Latest grid temperature", weather[0].value if weather else None, weather[0].unit if weather else "°C", "open-meteo-weather", "Most recent stored Open-Meteo grid value. Not a borough average.", weather[0].observed_at.isoformat() if weather else None),
            kpi("Latest CAMS PM2.5", modelled[0].value if modelled else None, modelled[0].unit if modelled else "µg/m³", "open-meteo-air-quality", "Model grid value. It is not a DOHMH estimate and not a monitor.", modelled[0].observed_at.isoformat() if modelled else None),
        ],
        "rankings": rankings,
        "series": [{"name": row.observed_at.strftime("%m-%d %H:%M"), "value": row.value} for row in reversed(weather) if row.observed_at],
        "series_label": "City grid temperature (°C)",
        "sources": [card for card in (source_card(session, code) for code in ("nyc-air-quality", "open-meteo-weather", "open-meteo-air-quality", "openaq-locations", "nyccas-rasters")) if card],
        "limitations": [
            "DOHMH indicators are annual or seasonal neighbourhood estimates.",
            "Open-Meteo air quality is a separate model product and is not blended into DOHMH values.",
            "NYCCAS rasters are historical files and are not displayed as current.",
            "OpenAQ stations load only when an API key is configured.",
        ],
    }


def crime_analytics(session: Session, slug: str) -> dict:
    if slug != NYC_PROFILE:
        return city_domains.crime(session, slug)
    aggregates = session.query(CrimeAggregate).filter(CrimeAggregate.city_slug == slug).all()
    sample_count = session.query(func.count(CrimeIncident.id)).filter(CrimeIncident.city_slug == slug).scalar() or 0
    by_category: dict[str, int] = defaultdict(int)
    by_borough: dict[str, int] = defaultdict(int)
    for row in aggregates:
        if row.completeness != "complete_aggregate" or row.incident_count is None:
            continue
        if row.dataset_code != "nypd-complaints-ytd":
            continue
        by_category[row.category or "Unspecified"] += row.incident_count
        by_borough[row.borough or "Unspecified"] += row.incident_count
    return {
        "availability": "partial" if aggregates else "unavailable",
        "kpis": [
            kpi("YTD complaint aggregate", sum(by_category.values()) or None, "complaints", "nypd-complaints-ytd", "Sum of server-side borough and law-category counts for the published YTD extract. This is reported complaints, not a victimization rate.", "published year-to-date quarters"),
        ],
        "rankings": [{"name": name, "value": value, "unit": "complaints"} for name, value in sorted(by_borough.items(), key=lambda item: item[1], reverse=True)],
        "categories": [{"name": name, "value": value} for name, value in sorted(by_category.items(), key=lambda item: item[1], reverse=True)],
        "series": [{"name": name, "value": value} for name, value in sorted(by_category.items(), key=lambda item: item[1], reverse=True)],
        "series_label": "YTD complaints by law category",
        "point_sample_rows": sample_count,
        "hotspots_available": False,
        "sources": [card for card in (source_card(session, code) for code in ("nypd-complaints-ytd", "nypd-complaints-historic")) if card],
        "limitations": [
            "No individual-level prediction is implemented.",
            "Suspect and victim demographic fields are not stored.",
            "The geocoded point extract is a capped recent sample, so DBSCAN hotspots are withheld.",
            "Complaint totals reflect reporting and enforcement, not a complete measure of harm.",
        ],
    }


def population_analytics(session: Session, slug: str) -> dict:
    if slug != NYC_PROFILE:
        return city_domains.population(session, slug)
    rows = session.query(PopulationObservation).filter(PopulationObservation.city_slug == slug).all()
    acs = [row for row in rows if row.metric_kind == "acs5_estimate"]
    decennial = [row for row in rows if row.metric_kind == "decennial_count" and row.vintage_year == 2010]
    by_year: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        if row.metric_kind == "decennial_count" and row.vintage_year and row.population is not None:
            by_year[row.vintage_year].append(row.population)
    return {
        "availability": "partial" if rows else "unavailable",
        "map_choropleth": "withheld",
        "kpis": [
            kpi("ACS 5-year borough estimates loaded", len(acs) or None, "boroughs", "census-acs5-borough", "Survey estimates. They are not displayed as neighbourhood population.", str(acs[0].vintage_year) if acs else None),
            kpi("2010 community-district counts", len(decennial) or None, "districts", "nyc-population-cd-decennial", "Latest decennial district table in the connected DCP dataset. Not painted on current boundaries.", "2010"),
        ],
        "rankings": [{"name": row.place_name, "value": row.population, "unit": "people", "vintage": row.vintage_year, "kind": row.metric_kind} for row in sorted(acs or decennial, key=lambda item: item.population or -1, reverse=True)],
        "series": [{"name": str(year), "value": round(sum(values), 1), "n": len(values)} for year, values in sorted(by_year.items())],
        "series_label": "Sum of stored district counts by census year",
        "sources": [card for card in (source_card(session, code) for code in ("nyc-population-cd-decennial", "census-acs5-borough", "nyc-population-projections", "worldpop-raster")) if card],
        "limitations": [
            "2010 counts are historical. They are not joined to 2026 boundaries.",
            "The chart adds the stored district rows for each census year. It is not an official citywide population.",
            "DCP projection fields were left unloaded because the API column names do not identify the year safely.",
            "WorldPop rasters are not connected.",
            "PLUTO residential units are housing stock and are not shown here as population.",
        ],
    }


def waste_analytics(session: Session, slug: str) -> dict:
    if slug != NYC_PROFILE:
        return city_domains.waste(session, slug)
    rows = session.query(WasteObservation).filter(WasteObservation.city_slug == slug).all()
    latest = max((row.period_start for row in rows if row.period_start), default=None)
    current = [row for row in rows if latest and row.period_start == latest]
    refuse = _mean([row.refuse_tons for row in current])
    by_month: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.period_start and row.refuse_tons is not None:
            by_month[row.period_start.date().isoformat()].append(row.refuse_tons)
    return {
        "availability": "available" if rows else "unavailable",
        "kpis": [
            kpi("Districts in latest month", len(current) or None, "districts", "nyc-waste-tonnage", "Count of community districts with a DSNY tonnage row in the latest loaded month.", latest.date().isoformat() if latest else None),
            kpi("Mean district refuse", refuse, "tons", "nyc-waste-tonnage", "Unweighted mean of district refuse tons. Districts without a row are excluded, not treated as zero.", latest.date().isoformat() if latest else None),
        ],
        "rankings": [
            {"name": f"{row.borough} CD {row.district_code}", "value": _round(row.refuse_tons), "unit": "tons"}
            for row in sorted(current, key=lambda item: item.refuse_tons or -1, reverse=True)[:12]
        ],
        "series": [{"name": month, "value": _round(sum(values) / len(values))} for month, values in sorted(by_month.items())],
        "series_label": "Mean district refuse tons by month",
        "sources": [source_card(session, "nyc-waste-tonnage")],
        "limitations": ["Tonnage is DSNY-collected residential and institutional waste. No schedule or missed-pickup events are inferred."],
    }


def transport_analytics(session: Session, slug: str) -> dict:
    if slug != NYC_PROFILE:
        return city_domains.transport(session, slug)
    stops = session.query(func.count(TransitStop.id)).filter(TransitStop.city_slug == slug).scalar() or 0
    riders = session.query(TransitRidership).filter(TransitRidership.city_slug == slug).all()
    total = sum(row.riders or 0 for row in riders) if riders else None
    window = None
    if riders:
        stamps = [row.observed_at for row in riders if row.observed_at]
        if stamps:
            window = f"{min(stamps).isoformat()} to {max(stamps).isoformat()}"
    routes = session.query(InfrastructureFeature).filter(InfrastructureFeature.city_slug == slug, InfrastructureFeature.dataset_code == "mta-subway-gtfs", InfrastructureFeature.feature_type == "scheduled_route_trips").all()
    buckets: dict[str, float] = defaultdict(float)
    for row in riders:
        if row.observed_at and row.riders is not None:
            buckets[row.observed_at.strftime("%m-%d %H:%M")] += float(row.riders)
    return {
        "availability": "partial" if stops or riders else "unavailable",
        "kpis": [
            kpi("Subway stops in GTFS", stops or None, "stops", "mta-subway-gtfs", "Stops in the regular static GTFS feed, including station and platform records as published.", None),
            kpi("Scheduled trips in feed", sum(row.value or 0 for row in routes) or None, "trips", "mta-subway-gtfs", "Trip rows in the regular GTFS file. Not observed frequency.", None),
            kpi("Ridership in loaded window", _round(total) if total else None, "estimated rides", "mta-subway-ridership", "Sum of station-hour estimates over the short ingested window, after summing fare classes.", window),
        ],
        "rankings": [
            {"name": row.name, "value": row.value, "unit": "scheduled trips"}
            for row in sorted(routes, key=lambda item: item.value or -1, reverse=True)[:12]
        ],
        "series": [{"name": name, "value": round(value, 1)} for name, value in sorted(buckets.items())],
        "series_label": "Estimated rides in the loaded window",
        "sources": [card for card in (source_card(session, code) for code in ("mta-subway-gtfs", "mta-subway-ridership")) if card],
        "limitations": [
            "Straight-line distance is the accessibility measure. Walking time is not claimed.",
            "GTFS-Realtime is not connected, so the platform does not claim live train positions.",
            "The ridership table is a short window of a multi-year hourly dataset.",
        ],
    }


def infrastructure_analytics(session: Session, slug: str) -> dict:
    if slug != NYC_PROFILE:
        return city_domains.infrastructure(session, slug)
    rows = session.query(InfrastructureFeature).filter(InfrastructureFeature.city_slug == slug).all()
    lots = [row for row in rows if row.feature_type == "pluto_lot_aggregate"]
    shelters = [row for row in rows if row.feature_type == "shelter_buildings"]
    roads = [row for row in rows if row.feature_type == "major_road"]
    return {
        "availability": "partial" if rows else "unavailable",
        "kpis": [
            kpi("PLUTO district groups", len(lots) or None, "groups", "nyc-pluto-aggregates", "SODA group-by of tax lots. Not a footprint map.", None),
            kpi("Residential units summed from PLUTO", sum((row.attributes or {}).get("residential_units") or 0 for row in lots) or None, "units", "nyc-pluto-aggregates", "Sum of PLUTO unitsres. This is housing stock, not population.", None),
            kpi("Shelter buildings in latest report", sum(row.value or 0 for row in shelters) or None, "buildings", "nyc-shelter-buildings", "Shelter facilities only. Not the city building stock.", None),
            kpi("OSM motorway and trunk ways", len(roads) or None, "ways", "osm-major-roads", "Bounded Overpass extract. Local streets are not included.", None),
        ],
        "rankings": [
            {"name": row.name, "value": (row.attributes or {}).get("residential_units"), "unit": "residential units"}
            for row in sorted(lots, key=lambda item: (item.attributes or {}).get("residential_units") or -1, reverse=True)[:12]
        ],
        "sources": [card for card in (source_card(session, code) for code in ("nyc-pluto-aggregates", "nyc-shelter-buildings", "osm-major-roads")) if card],
        "limitations": ["Building footprints are not loaded. Shelter counts must not be read as total buildings."],
    }


def city_overview(session: Session, slug: str) -> dict:
    city = _city(session, slug)
    if city is None:
        return {"availability": "unavailable", "reason": "City is not in the geographical registry."}
    domains = {
        "traffic": traffic_analytics(session, slug),
        "environment": environment_analytics(session, slug),
        "crime": crime_analytics(session, slug),
        "population": population_analytics(session, slug),
        "waste": waste_analytics(session, slug),
        "transport": transport_analytics(session, slug),
        "infrastructure": infrastructure_analytics(session, slug),
    }
    return {"city": serialize_geo(city), "availability": city.integration_status, "domains": {key: {"availability": value["availability"], "kpis": value["kpis"], "limitations": value["limitations"]} for key, value in domains.items()}}


def map_layer(session: Session, slug: str, layer: str) -> dict:
    city = _city(session, slug)
    if city is None:
        return {"type": "FeatureCollection", "features": [], "availability": "unavailable", "reason": "Unknown city."}
    features = []
    note = ""
    generic = city_domains.map_layer(session, city, layer, _feature) if slug != NYC_PROFILE else None
    if generic is not None:
        features, note = generic
    elif layer == "admin":
        rows = [row for row in _descendants(session, city) if (row.properties or {}).get("kind") in {"borough", "community_district"}]
        features = [feature for feature in (_feature(row) for row in rows) if feature]
        if features:
            note = "Official DCP polygons. Joint interest areas are omitted from this layer."
        else:
            feature = _feature(city)
            features = [feature] if feature else []
            source = (city.properties or {}).get("boundary_source")
            note = f"Stored geography for {city.name}" + (f" from {source}." if source else ". District polygons are loaded for New York.")
    elif layer == "traffic":
        speeds = session.query(TrafficObservation).filter(TrafficObservation.city_slug == slug, TrafficObservation.dataset_code == "nyc-traffic-speeds", TrafficObservation.geometry_geojson.isnot(None)).limit(800).all()
        for row in speeds:
            geometry = json.loads(row.geometry_geojson)
            coordinates = [point for point in geometry.get("coordinates") or [] if isinstance(point, list) and len(point) >= 2 and -74.35 <= point[0] <= -73.65 and 40.45 <= point[1] <= 41.05]
            if len(coordinates) < 2:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                    "properties": {"name": row.street, "value": row.speed_mph, "unit": "mph", "borough": row.borough, "availability": "available", "dataset_code": row.dataset_code, "observed_at": row.observed_at.isoformat() if row.observed_at else None},
                }
            )
        note = "Current DOT link snapshot. Speed is not a free-flow congestion index."
    elif layer == "environment":
        rows = session.query(EnvironmentalObservation).filter(EnvironmentalObservation.dataset_code == "nyc-air-quality", EnvironmentalObservation.parameter == "Fine particles (PM 2.5)", EnvironmentalObservation.value.isnot(None)).all()
        latest = max(((row.attributes or {}).get("time_period") or "" for row in rows), default="")
        boroughs = {row.name: row for row in _descendants(session, city) if (row.properties or {}).get("kind") == "borough"}
        for row in rows:
            if (row.attributes or {}).get("time_period") != latest:
                continue
            if (row.attributes or {}).get("geo_type") != "Borough":
                continue
            if not (row.aggregation or "").lower().startswith("annual"):
                continue
            geo = boroughs.get(row.place_name or "")
            if geo is None:
                continue
            feature = _feature(geo, row.value, {"unit": row.unit, "period": latest, "dataset_code": row.dataset_code, "parameter": row.parameter})
            if feature:
                features.append(feature)
        if features:
            note = "Annual DOHMH PM2.5 at borough geography only. Community-district and UHF rows stay in the table because their geographies are not assumed to match these polygons."
        else:
            latest_model = (
                session.query(EnvironmentalObservation)
                .filter(EnvironmentalObservation.city_slug == slug, EnvironmentalObservation.dataset_code == "open-meteo-air-quality", EnvironmentalObservation.parameter == "pm2_5", EnvironmentalObservation.value.isnot(None))
                .order_by(EnvironmentalObservation.observed_at.desc())
                .first()
            )
            feature = _feature(city, latest_model.value, {"unit": latest_model.unit, "dataset_code": latest_model.dataset_code, "parameter": latest_model.parameter}) if latest_model else None
            features = [feature] if feature else []
            note = "Latest stored CAMS PM2.5 grid value drawn on the city geography. It is not a monitor and not a neighbourhood average." if features else f"No air-quality geography is stored for {city.name}."
    elif layer == "waste":
        waste_rows = session.query(WasteObservation).filter(WasteObservation.city_slug == slug).all()
        latest = max((row.period_start for row in waste_rows if row.period_start), default=None)
        lookup = {}
        for row in _descendants(session, city):
            if (row.properties or {}).get("kind") == "community_district":
                lookup[row.official_code] = row
        digits = {"Manhattan": "1", "Bronx": "2", "Brooklyn": "3", "Queens": "4", "Staten Island": "5"}
        for row in waste_rows:
            if row.period_start != latest or not row.district_code or not row.borough:
                continue
            try:
                code = f"{digits[row.borough]}{int(float(row.district_code)):02d}"
            except (KeyError, ValueError):
                continue
            geo = lookup.get(code)
            if geo is None:
                continue
            feature = _feature(geo, row.refuse_tons, {"unit": "tons", "period": latest.date().isoformat(), "dataset_code": row.dataset_code})
            if feature:
                features.append(feature)
        note = "Latest loaded DSNY refuse tons joined on borough and community-district number." if features else f"No waste polygons are stored for {city.name}."
    elif layer == "transit":
        stops = session.query(TransitStop).filter(TransitStop.city_slug == slug, TransitStop.latitude.isnot(None)).limit(2500).all()
        for stop in stops:
            features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [stop.longitude, stop.latitude]}, "properties": {"name": stop.name, "value": None, "availability": "available", "dataset_code": stop.dataset_code, "stop_id": stop.stop_id}})
        note = "Static GTFS subway stops. Not live train positions." if features else f"No transit stops are stored for {city.name}."
    elif layer == "crime":
        note = "Individual complaint points are not drawn. The capped sample is not a hotspot layer."
    elif layer == "population":
        note = "Population choropleth is withheld. The district census table ends in 2010 and the boundaries are current."
    elif layer == "roads":
        roads = session.query(InfrastructureFeature).filter(InfrastructureFeature.city_slug == slug, InfrastructureFeature.feature_type == "major_road", InfrastructureFeature.geometry_geojson.isnot(None)).limit(400).all()
        for row in roads:
            features.append({"type": "Feature", "geometry": json.loads(row.geometry_geojson), "properties": {"name": row.name, "value": None, "availability": "available", "dataset_code": row.dataset_code}})
        note = "OSM motorway and trunk extract. © OpenStreetMap contributors." if features else f"No major-road lines are stored for {city.name}."
    else:
        note = "Unknown layer."
    if layer == "traffic" and not features and slug == NYC_PROFILE:
        note = f"No speed links are stored for {city.name}. The DOT snapshot is a New York extract."
    center = [city.longitude, city.latitude] if city.longitude is not None and city.latitude is not None else None
    return {"type": "FeatureCollection", "features": features, "layer": layer, "note": note, "count": len(features), "center": center}


def correlations(session: Session, slug: str) -> dict:
    weather = session.query(WeatherObservation).filter(WeatherObservation.city_slug == slug, WeatherObservation.parameter == "temperature_2m", WeatherObservation.value.isnot(None)).all()
    air = session.query(EnvironmentalObservation).filter(EnvironmentalObservation.city_slug == slug, EnvironmentalObservation.dataset_code == "open-meteo-air-quality", EnvironmentalObservation.parameter == "pm2_5", EnvironmentalObservation.value.isnot(None)).all()
    air_index = {(row.geo_unit_id, row.observed_at): row.value for row in air}
    xs, ys = [], []
    for row in weather:
        key = (row.geo_unit_id, row.observed_at)
        if key in air_index:
            xs.append(float(row.value))
            ys.append(float(air_index[key]))
    result = pearson(xs, ys)
    return {
        "availability": "available" if result else "unavailable",
        "relationship": "temperature_2m vs pm2_5",
        "result": result,
        "interpretation": "This is an association between two aligned model products at the same grid and hour. It is not a causal claim and it is not a relationship between traffic and regulatory monitors.",
        "sources": ["open-meteo-weather", "open-meteo-air-quality"],
    }


def model_catalog(session: Session) -> list[dict]:
    versions = session.query(ModelVersion).order_by(ModelVersion.trained_at.desc()).all()
    output = []
    for version in versions:
        metrics = session.query(ModelEvaluation).filter(ModelEvaluation.model_version_id == version.id).all()
        output.append(
            {
                "id": version.id,
                "domain": version.domain,
                "name": version.name,
                "version": version.version,
                "algorithm": version.algorithm,
                "target": version.target,
                "horizon": version.horizon,
                "status": version.status,
                "datasets": version.dataset_codes,
                "features": version.feature_names,
                "train_period": [version.train_start, version.train_end],
                "test_period": [version.test_start, version.test_end],
                "limitations": version.limitations,
                "metrics": [
                    {"name": metric.metric_name, "value": metric.metric_value, "baseline_name": metric.baseline_name, "baseline_value": metric.baseline_value, "n_train": metric.n_train, "n_test": metric.n_test, "details": metric.details}
                    for metric in metrics
                ],
            }
        )
    return output


def list_sources(session: Session) -> dict:
    sources = session.query(DataSource).order_by(DataSource.name).all()
    datasets = session.query(Dataset).order_by(Dataset.domain, Dataset.name).all()
    return {
        "sources": [{"code": row.code, "name": row.name, "provider": row.provider, "access_mode": row.access_mode, "homepage_url": row.homepage_url, "terms_url": row.terms_url, "notes": row.notes} for row in sources],
        "datasets": [
            {
                "code": row.code,
                "name": row.name,
                "domain": row.domain,
                "city_slug": row.city_slug,
                "availability": row.availability,
                "endpoint_url": row.endpoint_url,
                "geo_resolution": row.geo_resolution,
                "temporal_resolution": row.temporal_resolution,
                "update_frequency": row.update_frequency,
                "license_name": row.license_name,
                "limitations": row.limitations,
                "verified_on": row.verified_on,
            }
            for row in datasets
        ],
    }


def quality_report(session: Session) -> list[dict]:
    rows = session.query(DataQualityCheck).order_by(DataQualityCheck.created_at.desc()).limit(200).all()
    return [{"dataset_code": row.dataset_code, "check": row.check_name, "status": row.status, "detail": row.detail, "metrics": row.metrics, "created_at": row.created_at.isoformat() if row.created_at else None} for row in rows]


def list_alerts(session: Session) -> list[dict]:
    rows = session.query(Alert).order_by(Alert.created_at.desc()).limit(100).all()
    return [{"id": row.id, "severity": row.severity, "domain": row.domain, "title": row.title, "detail": row.detail, "dataset_code": row.dataset_code, "status": row.status, "evidence": row.evidence, "created_at": row.created_at.isoformat() if row.created_at else None} for row in rows]


def list_anomalies(session: Session) -> list[dict]:
    rows = session.query(Anomaly).order_by(Anomaly.created_at.desc()).limit(100).all()
    return [{"id": row.id, "domain": row.domain, "method": row.method, "score": row.score, "summary": row.summary, "evidence": row.evidence} for row in rows]


def list_jobs(session: Session) -> list[dict]:
    rows = session.query(IngestionJob).order_by(IngestionJob.started_at.desc()).limit(100).all()
    return [{"id": row.id, "dataset_code": row.dataset_code, "status": row.status, "rows_written": row.rows_written, "message": row.message, "started_at": row.started_at.isoformat() if row.started_at else None, "finished_at": row.finished_at.isoformat() if row.finished_at else None} for row in rows]


def dataset_freshness(session: Session) -> list[dict]:
    rows = session.query(IngestionJob).order_by(IngestionJob.started_at.desc()).limit(500).all()
    latest: dict[str, dict] = {}
    for row in rows:
        if row.dataset_code in latest:
            continue
        latest[row.dataset_code] = {
            "dataset_code": row.dataset_code,
            "status": row.status,
            "rows_written": row.rows_written,
            "message": row.message,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        }
    return list(latest.values())


def refresh_alerts(session: Session) -> int:
    session.query(Alert).filter(Alert.domain.in_(["traffic", "ingestion"])).delete(synchronize_session=False)
    created = 0
    speeds = session.query(TrafficObservation).filter(TrafficObservation.dataset_code == "nyc-traffic-speeds", TrafficObservation.speed_mph.isnot(None)).all()
    slow = sorted([row for row in speeds if row.speed_mph is not None and row.speed_mph < 10], key=lambda row: row.speed_mph)[:15]
    for row in slow:
        session.add(
            Alert(
                id=str(uuid.uuid4()),
                severity="high" if row.speed_mph < 5 else "warning",
                domain="traffic",
                city_slug="nyc",
                title=f"Low published speed on {row.street or row.segment_id}",
                detail="The current DOT snapshot reports a link speed below 10 mph. This is one link at one timestamp, not a corridor forecast.",
                dataset_code="nyc-traffic-speeds",
                evidence={"speed_mph": row.speed_mph, "observed_at": row.observed_at.isoformat() if row.observed_at else None, "borough": row.borough, "link": row.street},
            )
        )
        created += 1
    recent = session.query(IngestionJob).order_by(IngestionJob.finished_at.desc()).limit(300).all()
    seen: set[str] = set()
    failed = []
    for job in recent:
        if job.dataset_code in seen:
            continue
        seen.add(job.dataset_code)
        if job.status == "failed":
            failed.append(job)
        if len(failed) >= 10:
            break
    for job in failed:
        session.add(
            Alert(
                id=str(uuid.uuid4()),
                severity="warning",
                domain="ingestion",
                title=f"Ingestion failed for {job.dataset_code}",
                detail=job.message or "The connector failed.",
                dataset_code=job.dataset_code,
                evidence={"job_id": job.id},
            )
        )
        created += 1
    return created


def _latest_grid(session: Session, slug: str, kind: str):
    if kind == "temperature":
        row = (
            session.query(WeatherObservation)
            .filter(WeatherObservation.city_slug == slug, WeatherObservation.parameter == "temperature_2m", WeatherObservation.value.isnot(None))
            .order_by(WeatherObservation.observed_at.desc())
            .first()
        )
    else:
        row = (
            session.query(EnvironmentalObservation)
            .filter(EnvironmentalObservation.city_slug == slug, EnvironmentalObservation.dataset_code == "open-meteo-air-quality", EnvironmentalObservation.parameter == "pm2_5", EnvironmentalObservation.value.isnot(None))
            .order_by(EnvironmentalObservation.observed_at.desc())
            .first()
        )
    if row is None:
        return None
    return {"value": row.value, "unit": row.unit, "observed_at": row.observed_at.isoformat() if row.observed_at else None}


def compare_geographies(session: Session, left_slug: str, right_slug: str) -> dict:
    left = session.query(GeoUnit).filter(GeoUnit.slug == left_slug).one_or_none()
    right = session.query(GeoUnit).filter(GeoUnit.slug == right_slug).one_or_none()
    if left is None or right is None:
        return {"availability": "unavailable", "reason": "One or both geographies are unknown."}
    metrics = []
    for label, kind in (("Latest grid temperature", "temperature"), ("Latest CAMS PM2.5", "pm2_5")):
        left_metric = _latest_grid(session, left.slug, kind)
        right_metric = _latest_grid(session, right.slug, kind)
        if left_metric or right_metric:
            metrics.append({"label": label, "left": left_metric, "right": right_metric})
    return {
        "availability": "partial",
        "left": serialize_geo(left),
        "right": serialize_geo(right),
        "metrics": metrics,
        "area_km2": {"left": _round(left.area_km2, 2), "right": _round(right.area_km2, 2), "dataset": "boundary geometry"},
        "note": "Temperature and PM2.5 are the latest stored Open-Meteo grid hours. They are not citywide averages. Domain figures use different official sources per city, so compare them in Explore with their method notes.",
    }


def evidence_numbers(payload) -> set[str]:
    found: set[str] = set()

    def walk(value) -> None:
        if value is None or isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            found.add(str(value))
            if isinstance(value, float):
                found.add(f"{value:.1f}".rstrip("0").rstrip("."))
                found.add(f"{value:.2f}".rstrip("0").rstrip("."))
                if value.is_integer():
                    found.add(str(int(value)))
            return
        if isinstance(value, str):
            found.update(NUMBER_RE.findall(value))
            return
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
            return
        if isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(payload)
    return {item for item in found if item}


def unsupported_numbers(text: str, evidence) -> list[str]:
    allowed = evidence_numbers(evidence)
    bad = []
    for number in NUMBER_RE.findall(text or ""):
        variants = {number}
        if _is_number(number):
            value = float(number)
            variants.add(str(value))
            if value.is_integer():
                variants.add(str(int(value)))
        if allowed.isdisjoint(variants):
            bad.append(number)
    return bad


def _is_number(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def index_documents(session: Session, root) -> int:
    from pathlib import Path

    root = Path(root)
    count = 0
    for path in root.glob("docs/**/*.md"):
        body = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(root))
        current = session.query(KnowledgeDocument).filter(KnowledgeDocument.source_path == relative).one_or_none()
        if current is None:
            current = KnowledgeDocument(id=str(uuid.uuid4()), source_path=relative, title=path.stem, body=body)
            session.add(current)
        else:
            current.body = body
            current.title = path.stem
        count += 1
    return count


def search_documents(session: Session, query: str, limit: int = 4) -> list[dict]:
    tokens = [token.lower() for token in re.findall(r"[a-zA-Z]{3,}", query)]
    rows = session.query(KnowledgeDocument).all()
    scored = []
    for row in rows:
        haystack = f"{row.title}\n{row.body}".lower()
        score = sum(haystack.count(token) for token in tokens)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [{"title": row.title, "source_path": row.source_path, "excerpt": row.body[:700], "score": score} for score, row in scored[:limit]]


def save_investigation(session: Session, question: str, city_slug: str | None, answer: dict, planner: str, tools: list) -> Investigation:
    investigation = Investigation(id=str(uuid.uuid4()), question=question, city_slug=city_slug, answer=answer, status="completed")
    session.add(investigation)
    session.flush()
    from urbix_db.models import AgentRun

    session.add(AgentRun(id=str(uuid.uuid4()), investigation_id=investigation.id, planner=planner, tools_called=tools, trace=answer))
    return investigation


def save_report(session: Session, title: str, city_slug: str | None, body: dict, evidence: list[dict]) -> IntelligenceReport:
    report = IntelligenceReport(id=str(uuid.uuid4()), title=title, city_slug=city_slug, period_label=body.get("period"), body=body, created_at=datetime.now(timezone.utc))
    session.add(report)
    session.flush()
    for item in evidence:
        session.add(ReportEvidence(report_id=report.id, claim_type=item["claim_type"], statement=item["statement"], dataset_code=item.get("dataset_code"), support=item.get("support") or {}))
    return report
