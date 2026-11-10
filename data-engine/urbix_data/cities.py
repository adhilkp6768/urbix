"""Connectors for reference cities outside New York.

Every endpoint here was requested live on 2026-11-10 before it was wired in.
Each connector writes rows only for the city its publisher covers.
"""

from __future__ import annotations

import csv
import io
import json
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from shapely.geometry import LineString, Point, mapping, shape
from shapely.ops import unary_union
from sqlalchemy.orm import Session

from urbix_data.http_client import request_bytes, request_json
from urbix_data.repository import CRIME_AGG, ENVIRONMENT, INFRA, POPULATION, STOPS, TRAFFIC, get_geo, insert_new, save_geo
from urbix_db.models import GeoUnit

UBA = "https://luftdaten.umweltbundesamt.de/api/air-data/v4"
OVERPASS = "https://overpass-api.de/api/interpreter"
CET = timezone(timedelta(hours=1))
OTHER_CITIES = [
    "singapore",
    "amsterdam",
    "london",
    "berlin",
    "trier",
    "paris",
    "madrid",
    "rome",
    "stockholm",
    "tokyo",
    "seoul",
    "mumbai",
    "dubai",
    "cairo",
    "nairobi",
    "lagos",
    "cape-town",
    "sydney",
    "toronto",
    "chicago",
    "los-angeles",
    "mexico-city",
    "sao-paulo",
]
BOUNDARY_QUERY = {
    "london": "Greater London",
    "singapore": "Singapore",
    "amsterdam": "Amsterdam",
    "berlin": "Berlin",
    "trier": "Trier",
    "paris": "Paris",
    "madrid": "Madrid",
    "rome": "Roma",
    "stockholm": "Stockholm",
    "tokyo": "Tokyo",
    "seoul": "Seoul",
    "mumbai": "Mumbai",
    "dubai": "Dubai",
    "cairo": "Cairo",
    "nairobi": "Nairobi",
    "lagos": "Lagos",
    "cape-town": "Cape Town",
    "sydney": "Sydney",
    "toronto": "Toronto",
    "chicago": "Chicago",
    "los-angeles": "Los Angeles",
    "mexico-city": "Ciudad de México",
    "sao-paulo": "São Paulo",
}
EUROSTAT_CITY_CODES = {
    "DE001C": "berlin",
    "DE024C": "trier",
    "FR001C": "paris",
    "ES001C": "madrid",
    "IT001C": "rome",
    "SE001C": "stockholm",
    "NL001C": "amsterdam",
}


def _num(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")


def _mark(session: Session, slug: str) -> None:
    city = get_geo(session, slug)
    if city is not None and city.integration_status not in {"partial", "integrated"}:
        city.integration_status = "partial"


def _city(session: Session, slug: str) -> GeoUnit:
    city = get_geo(session, slug)
    if city is None:
        raise RuntimeError(f"{slug} is not in the geography registry. Seed reference geography first.")
    return city


def _apply_geometry(geo: GeoUnit, geometry: dict) -> None:
    from urbix_db.spatial import centroid_latlon, geometry_area_km2

    geom = shape(geometry)
    if geom.is_empty:
        return
    geo.boundary_geojson = json.dumps(geometry)
    area = geometry_area_km2(geom)
    if area:
        geo.area_km2 = area
    center = centroid_latlon(geom)
    if center:
        geo.latitude, geo.longitude = center
        properties = dict(geo.properties or {})
        properties["centroid_method"] = "boundary_centroid"
        geo.properties = properties


def _districts(session: Session, slug: str) -> list[GeoUnit]:
    city = _city(session, slug)
    return [
        row
        for row in session.query(GeoUnit).filter(GeoUnit.parent_id == city.id).all()
        if (row.properties or {}).get("kind") == "district"
    ]


def _save_districts(session: Session, slug: str, items: list[tuple[str, str, dict]], district_type: str, source: str) -> int:
    city = _city(session, slug)
    written = 0
    for code, name, geometry in items:
        geo = save_geo(
            session,
            {
                "slug": f"{slug}-{_slug(code or name)}",
                "name": name,
                "level_code": "district",
                "parent_id": city.id,
                "official_code": code,
                "country_code": city.country_code,
                "timezone": city.timezone,
                "properties": {"kind": "district", "district_type": district_type, "source": source},
                "integration_status": "integrated",
            },
        )
        _apply_geometry(geo, geometry)
        written += 1
    session.flush()
    _mark(session, slug)
    return written


def _city_shape(session: Session, slug: str):
    city = _city(session, slug)
    if city.boundary_geojson:
        return shape(json.loads(city.boundary_geojson))
    parts = [shape(json.loads(row.boundary_geojson)) for row in _districts(session, slug) if row.boundary_geojson]
    if parts:
        return unary_union(parts)
    return None


def _bbox(session: Session, slug: str) -> tuple[float, float, float, float]:
    geom = _city_shape(session, slug)
    if geom is not None:
        minx, miny, maxx, maxy = geom.bounds
        return miny, minx, maxy, maxx
    city = _city(session, slug)
    return city.latitude - 0.15, city.longitude - 0.25, city.latitude + 0.15, city.longitude + 0.25


def _district_for_point(districts: list[tuple[GeoUnit, object]], lon: float | None, lat: float | None) -> GeoUnit | None:
    if lon is None or lat is None:
        return None
    point = Point(lon, lat)
    for geo, geom in districts:
        if geom.contains(point):
            return geo
    return None


def _district_shapes(session: Session, slug: str) -> list[tuple[GeoUnit, object]]:
    return [(row, shape(json.loads(row.boundary_geojson))) for row in _districts(session, slug) if row.boundary_geojson]


OVERPASS_MIRRORS = [OVERPASS, "https://overpass.private.coffee/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]


def _overpass(query: str, timeout: int = 120) -> list[dict]:
    error: Exception | None = None
    for endpoint in OVERPASS_MIRRORS:
        try:
            payload = request_json(endpoint, data=query.encode("utf-8"), timeout=timeout)
            return (payload or {}).get("elements") or []
        except Exception as exc:  # noqa: BLE001
            error = exc
    raise error or RuntimeError("Overpass unavailable")


def _uba_time(value: str) -> datetime:
    day, clock = value.split(" ")
    if clock.startswith("24:"):
        return datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=CET) + timedelta(days=1)
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CET)


def connect_city_boundaries(session: Session, options: dict) -> tuple[int, str, list]:
    cities = options.get("cities") or OTHER_CITIES
    attached, skipped = [], []
    for slug in cities:
        city = get_geo(session, slug)
        if city is None or city.latitude is None:
            skipped.append(f"{slug}: not in registry")
            continue
        params = {"q": BOUNDARY_QUERY.get(slug, city.name), "format": "jsonv2", "polygon_geojson": 1, "polygon_threshold": 0.0005, "limit": 5}
        if city.country_code:
            params["countrycodes"] = city.country_code.lower()
        try:
            results = request_json("https://nominatim.openstreetmap.org/search", params=params, timeout=60) or []
        except Exception as exc:
            skipped.append(f"{slug}: {exc}")
            continue
        chosen = None
        for item in results:
            geometry = item.get("geojson") or {}
            if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
                continue
            centroid = shape(geometry).centroid
            if abs(centroid.y - city.latitude) > 1.0 or abs(centroid.x - city.longitude) > 1.0:
                continue
            chosen = item
            break
        time.sleep(1.1)
        if chosen is None:
            skipped.append(f"{slug}: no polygon near the reference point")
            continue
        _apply_geometry(city, chosen["geojson"])
        properties = dict(city.properties or {})
        properties.update({"boundary_source": "OpenStreetMap via Nominatim", "osm_id": chosen.get("osm_id"), "osm_type": chosen.get("osm_type"), "boundary_label": chosen.get("display_name")})
        city.properties = properties
        _mark(session, slug)
        attached.append(slug)
    if not attached:
        raise RuntimeError("Nominatim returned no usable city polygon. " + "; ".join(skipped))
    message = f"Attached OpenStreetMap boundaries for {', '.join(attached)}."
    if skipped:
        message += " Skipped " + "; ".join(skipped) + "."
    return len(attached), message, [
        {"name": "osm_boundary", "status": "pass" if not skipped else "warn", "detail": "Nominatim polygon kept only when its centroid is near the registry point. © OpenStreetMap contributors.", "metrics": {"attached": attached, "skipped": skipped}}
    ]


def connect_sg_planning_areas(session: Session, options: dict) -> tuple[int, str, list]:
    meta = request_json("https://api-open.data.gov.sg/v1/public/api/datasets/d_4765db0e87b9c86336792efe8a1f7a66/poll-download", timeout=60)
    url = ((meta or {}).get("data") or {}).get("url")
    if not url:
        raise RuntimeError("data.gov.sg did not return a download URL for the planning-area boundaries.")
    collection = json.loads(request_bytes(url, timeout=120).decode("utf-8"))
    items = []
    for feature in collection.get("features") or []:
        props = feature.get("properties") or {}
        name = (props.get("PLN_AREA_N") or "").title()
        if name and feature.get("geometry"):
            items.append((props.get("PLN_AREA_C") or name, name, feature["geometry"]))
    written = _save_districts(session, "singapore", items, "planning_area", "URA Master Plan 2019 planning areas (no sea), data.gov.sg")
    return written, f"Loaded {written} URA Master Plan 2019 planning areas.", [
        {"name": "boundary_vintage", "status": "pass", "detail": "Master Plan 2019 planning areas. Sea areas are excluded.", "metrics": {"features": len(items)}}
    ]


def connect_ams_stadsdelen(session: Session, options: dict) -> tuple[int, str, list]:
    collection = request_json("https://api.data.amsterdam.nl/v1/gebieden/stadsdelen/", params={"_format": "geojson", "_pageSize": 50}, timeout=90, headers={"Accept": "application/geo+json, */*"})
    items = []
    for feature in (collection or {}).get("features") or []:
        props = feature.get("properties") or {}
        if props.get("eindGeldigheid"):
            continue
        if feature.get("geometry"):
            items.append((props.get("code") or props.get("naam"), props.get("naam") or props.get("code"), feature["geometry"]))
    written = _save_districts(session, "amsterdam", items, "stadsdeel", "Gemeente Amsterdam gebieden/stadsdelen API")
    return written, f"Loaded {written} current Amsterdam stadsdelen.", [
        {"name": "current_only", "status": "pass", "detail": "Stadsdelen with an end-of-validity date were skipped.", "metrics": {"features": len(items)}}
    ]


def connect_london_boroughs(session: Session, options: dict) -> tuple[int, str, list]:
    collection = request_json(
        "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/Local_Authority_Districts_December_2024_Boundaries_UK_BGC/FeatureServer/0/query",
        params={"where": "LAD24CD LIKE 'E09%'", "outFields": "LAD24CD,LAD24NM", "outSR": 4326, "f": "geojson"},
        timeout=90,
    )
    items = []
    for feature in (collection or {}).get("features") or []:
        props = feature.get("properties") or {}
        if feature.get("geometry"):
            items.append((props.get("LAD24CD"), props.get("LAD24NM"), feature["geometry"]))
    written = _save_districts(session, "london", items, "london_borough", "ONS Local Authority Districts December 2024, generalised clipped")
    return written, f"Loaded {written} London borough boundaries (32 boroughs and the City of London).", [
        {"name": "boundary_vintage", "status": "pass" if written == 33 else "warn", "detail": "ONS LAD December 2024 BGC. Generalised to 20 m and clipped to the coastline.", "metrics": {"features": written}}
    ]


def connect_berlin_bezirke(session: Session, options: dict) -> tuple[int, str, list]:
    collection = request_json(
        "https://gdi.berlin.de/services/wfs/alkis_bezirke",
        params={"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": "alkis_bezirke:bezirksgrenzen", "outputFormat": "application/json", "srsName": "EPSG:4326"},
        timeout=120,
    )
    items = []
    for feature in (collection or {}).get("features") or []:
        props = feature.get("properties") or {}
        if feature.get("geometry"):
            items.append((props.get("name") or props.get("gem"), props.get("namgem"), feature["geometry"]))
    written = _save_districts(session, "berlin", items, "bezirk", "Geoportal Berlin ALKIS Bezirksgrenzen WFS")
    return written, f"Loaded {written} Berlin Bezirke from the ALKIS WFS.", [
        {"name": "boundary_source", "status": "pass" if written == 12 else "warn", "detail": "Official cadastral district boundaries requested in EPSG:4326.", "metrics": {"features": written}}
    ]


def connect_trier_ortsbezirke(session: Session, options: dict) -> tuple[int, str, list]:
    query = """
    [out:json][timeout:120];
    area["name"="Trier"]["admin_level"="6"]->.t;
    rel(area.t)["boundary"="administrative"]["admin_level"="10"];
    out geom;
    """
    elements = _overpass(query, timeout=180)
    items = []
    for element in elements:
        geometry = _relation_polygon(element)
        name = (element.get("tags") or {}).get("name")
        if geometry and name:
            items.append((f"osm-{element.get('id')}", name, geometry))
    if not items:
        raise RuntimeError("Overpass returned no Trier admin_level 10 polygons.")
    written = _save_districts(session, "trier", items, "stadtteil_osm", "OpenStreetMap admin_level 10 relations inside Trier")
    return written, f"Loaded {written} Trier admin_level 10 areas from OpenStreetMap.", [
        {"name": "not_official", "status": "warn", "detail": "OSM community-mapped boundaries. The city's official Ortsbezirk layer was not available as an open API.", "metrics": {"relations": len(elements)}}
    ]


def _relation_polygon(element: dict) -> dict | None:
    from shapely.ops import linemerge, polygonize

    lines = []
    for member in element.get("members") or []:
        if member.get("type") != "way" or member.get("role") not in {"outer", ""}:
            continue
        coords = [(node["lon"], node["lat"]) for node in member.get("geometry") or [] if "lon" in node]
        if len(coords) >= 2:
            lines.append(LineString(coords))
    if not lines:
        return None
    polygons = list(polygonize(linemerge(lines)))
    if not polygons:
        return None
    merged = unary_union(polygons)
    return mapping(merged)


def _official_air_row(dataset: str, slug: str, station: str, name: str, parameter: str, value, unit: str, observed: datetime | None, lat, lon, methodology: str, attributes: dict | None = None) -> dict:
    if observed is not None and observed.tzinfo is not None:
        observed = observed.astimezone(timezone.utc)
    return {
        "dataset_code": dataset,
        "city_slug": slug,
        "observed_at": observed,
        "parameter": parameter,
        "value": _num(value),
        "unit": unit,
        "aggregation": "station_hour",
        "methodology": methodology,
        "place_name": name,
        "latitude": _num(lat),
        "longitude": _num(lon),
        "source_row_id": f"{station}:{parameter}:{observed.isoformat() if observed else 'none'}"[:160],
        "attributes": {"station": station, **(attributes or {})},
    }


def connect_sg_nea_air(session: Session, options: dict) -> tuple[int, str, list]:
    payload = request_json("https://api-open.data.gov.sg/v2/real-time/api/pm25", timeout=60)
    data = (payload or {}).get("data") or {}
    regions = {item["name"]: item.get("labelLocation") or {} for item in data.get("regionMetadata") or []}
    rows = []
    for item in data.get("items") or []:
        observed = datetime.fromisoformat(item["timestamp"])
        for region, value in ((item.get("readings") or {}).get("pm25_one_hourly") or {}).items():
            location = regions.get(region, {})
            rows.append(
                _official_air_row(
                    "sg-nea-pm25", "singapore", f"region-{region}", f"{region.title()} region", "pm25", value, "µg/m³", observed,
                    location.get("latitude"), location.get("longitude"),
                    "NEA one-hour PM2.5 reading for a planning region. The label point is the region's display location, not a single monitor.",
                    {"region": region},
                )
            )
    if not rows:
        raise RuntimeError("NEA returned no PM2.5 readings.")
    written = insert_new(session, ENVIRONMENT, rows)
    _mark(session, "singapore")
    return written, f"Stored {written} new NEA regional PM2.5 readings.", [
        {"name": "regional_reading", "status": "pass", "detail": "Five regional one-hour readings per timestamp. Not interpolated to planning areas.", "metrics": {"readings": len(rows)}}
    ]


def connect_london_laqn(session: Session, options: dict) -> tuple[int, str, list]:
    payload = request_json("https://api.erg.ic.ac.uk/AirQuality/Hourly/MonitoringIndex/GroupName=London/Json", timeout=90)
    authorities = ((payload or {}).get("HourlyAirQualityIndex") or {}).get("LocalAuthority") or []
    if isinstance(authorities, dict):
        authorities = [authorities]
    london = _city(session, "london")
    rows, no_data = [], 0
    for authority in authorities:
        sites = authority.get("Site") or []
        sites = sites if isinstance(sites, list) else [sites]
        for site in sites:
            observed = None
            if site.get("@BulletinDate"):
                observed = datetime.strptime(site["@BulletinDate"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo(london.timezone or "Europe/London"))
            species = site.get("Species") or []
            species = species if isinstance(species, list) else [species]
            for item in species:
                band = item.get("@AirQualityBand")
                index = _num(item.get("@AirQualityIndex"))
                if band == "No data":
                    no_data += 1
                    index = None
                rows.append(
                    _official_air_row(
                        "london-laqn-index", "london", site.get("@SiteCode") or "", site.get("@SiteName") or "", f"daqi_{(item.get('@SpeciesCode') or '').lower()}",
                        index, "DAQI band 1-10", observed, site.get("@Latitude"), site.get("@Longitude"),
                        "London Air Quality Network hourly Daily Air Quality Index for one pollutant at one site. The index is a 1-10 band, not a concentration.",
                        {"band": band, "index_source": item.get("@IndexSource"), "site_type": site.get("@SiteType"), "local_authority": authority.get("@LocalAuthorityName")},
                    )
                )
    if not rows:
        raise RuntimeError("LAQN returned no site indices.")
    written = insert_new(session, ENVIRONMENT, rows)
    _mark(session, "london")
    return written, f"Stored {written} new LAQN site-pollutant index rows. {no_data} 'No data' indices were stored as missing, not zero.", [
        {"name": "no_data_not_zero", "status": "pass", "detail": "LAQN publishes 0 with band 'No data' when a site has no reading. Those rows are null.", "metrics": {"rows": len(rows), "no_data": no_data}}
    ]


def connect_uba_air(session: Session, options: dict) -> tuple[int, str, list]:
    cities = {"berlin": "Berlin", "trier": "Trier"}
    stations = request_json(f"{UBA}/stations/json", params={"lang": "en", "index": "id"}, timeout=120)
    meta = {}
    for station_id, values in ((stations or {}).get("data") or {}).items():
        if len(values) > 8 and values[3] in cities.values():
            meta[station_id] = {"code": values[1], "name": values[2], "city": values[3], "lon": values[7], "lat": values[8], "setting": values[14] if len(values) > 14 else None, "type": values[16] if len(values) > 16 else None}
    hours = int(options.get("hours") or 48)
    end = datetime.now(CET)
    start = end - timedelta(hours=hours)
    components = {"9": ("pm25", "µg/m³"), "1": ("pm10", "µg/m³"), "5": ("no2", "µg/m³")}
    rows = []
    for component, (parameter, unit) in components.items():
        payload = request_json(
            f"{UBA}/measures/json",
            params={"date_from": start.date().isoformat(), "time_from": max(start.hour, 1), "date_to": end.date().isoformat(), "time_to": max(end.hour, 1), "component": component, "scope": 2, "lang": "en", "index": "id"},
            timeout=120,
        )
        for station_id, series in ((payload or {}).get("data") or {}).items():
            info = meta.get(station_id)
            if not info:
                continue
            slug = next(key for key, label in cities.items() if label == info["city"])
            for start_label, values in (series or {}).items():
                if not isinstance(values, list) or len(values) < 4:
                    continue
                observed = _uba_time(values[3])
                rows.append(
                    _official_air_row(
                        "uba-air-quality", slug, info["code"], info["name"], parameter, values[2], unit, observed, info["lat"], info["lon"],
                        "Umweltbundesamt one-hour mean from a federal-state monitoring station. UBA publishes end-of-hour CET times, stored here in UTC. Station values are not a city average.",
                        {"station_setting": info["setting"], "station_type": info["type"], "uba_station_id": station_id},
                    )
                )
    if not rows:
        raise RuntimeError("UBA returned no hourly values for Berlin or Trier stations.")
    written = insert_new(session, ENVIRONMENT, rows)
    for slug in cities:
        _mark(session, slug)
    return written, f"Stored {written} new UBA hourly station values for Berlin and Trier over the last {hours} hours.", [
        {"name": "station_values", "status": "pass", "detail": "PM2.5, PM10, and NO2 one-hour means. API v4 because v3 is in its sunset brownout.", "metrics": {"rows": len(rows), "stations": len({row['attributes']['station'] for row in rows})}}
    ]


def connect_ams_luchtmeetnet(session: Session, options: dict) -> tuple[int, str, list]:
    base = "https://api.luchtmeetnet.nl/open_api"
    candidates = []
    page = 1
    while page <= 10:
        listing = request_json(f"{base}/stations", params={"page": page, "order_by": "number"}, timeout=60) or {}
        for item in listing.get("data") or []:
            if (item.get("location") or "").lower().startswith("amsterdam"):
                candidates.append(item["number"])
        last = (listing.get("pagination") or {}).get("last_page") or page
        if page >= last:
            break
        page += 1
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=int(options.get("hours") or 48))
    rows, stations = [], 0
    for number in candidates:
        detail = (request_json(f"{base}/stations/{number}", timeout=60) or {}).get("data") or {}
        if detail.get("municipality") != "Amsterdam":
            continue
        stations += 1
        lon, lat = ((detail.get("geometry") or {}).get("coordinates") or [None, None])[:2]
        for formula, parameter in (("PM25", "pm25"), ("NO2", "no2"), ("PM10", "pm10")):
            if formula not in (detail.get("components") or []):
                continue
            payload = request_json(
                f"{base}/measurements",
                params={"station_number": number, "formula": formula, "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"), "order_by": "timestamp_measured", "order_direction": "desc"},
                timeout=60,
            ) or {}
            for item in payload.get("data") or []:
                observed = datetime.fromisoformat(item["timestamp_measured"])
                rows.append(
                    _official_air_row(
                        "ams-luchtmeetnet", "amsterdam", number, detail.get("location") or number, parameter, item.get("value"), "µg/m³", observed, lat, lon,
                        "Luchtmeetnet hourly value from a GGD Amsterdam or RIVM station. Values are validated later and can change.",
                        {"organisation": detail.get("organisation"), "station_type": detail.get("type")},
                    )
                )
            time.sleep(0.2)
    if not rows:
        raise RuntimeError("Luchtmeetnet returned no measurements for Amsterdam stations.")
    written = insert_new(session, ENVIRONMENT, rows)
    _mark(session, "amsterdam")
    return written, f"Stored {written} new Luchtmeetnet hourly values from {stations} Amsterdam stations.", [
        {"name": "provisional", "status": "warn", "detail": "Recent Luchtmeetnet hours are not yet validated.", "metrics": {"stations": stations, "rows": len(rows)}}
    ]


def _population_row(dataset: str, slug: str, geo: GeoUnit | None, name: str, code: str, year: int, value, kind: str, methodology: str) -> dict:
    return {
        "dataset_code": dataset,
        "city_slug": slug,
        "geo_unit_id": geo.id if geo else None,
        "place_name": name,
        "place_code": code,
        "vintage_year": year,
        "population": _num(value),
        "metric_kind": kind,
        "methodology": methodology,
        "source_row_id": f"{code}:{year}:{kind}",
    }


def connect_sg_population(session: Session, options: dict) -> tuple[int, str, list]:
    payload = request_json("https://tablebuilder.singstat.gov.sg/api/table/tabledata/M810001", params={"limit": 2000}, timeout=60)
    data = (payload or {}).get("Data") or {}
    city = _city(session, "singapore")
    rows = []
    for row in data.get("row") or []:
        if row.get("rowText") not in {"Total Population", "Resident Population"}:
            continue
        kind = "total_population" if row["rowText"] == "Total Population" else "resident_population"
        for column in row.get("columns") or []:
            year = int(column["key"])
            if year < 2000:
                continue
            rows.append(
                _population_row(
                    "sg-singstat-population", "singapore", city, "Singapore", f"SG-{kind}", year, column.get("value"), kind,
                    "SingStat M810001 mid-year population. Total population includes non-residents. Resident population is citizens plus permanent residents.",
                )
            )
    if not rows:
        raise RuntimeError("SingStat M810001 returned no population rows.")
    written = insert_new(session, POPULATION, rows)
    _mark(session, "singapore")
    return written, f"Stored {written} SingStat mid-year population rows (data last updated {data.get('dataLastUpdated')}).", [
        {"name": "national_equals_city", "status": "pass", "detail": "Singapore is a city-state, so the national series is the city series.", "metrics": {"rows": len(rows)}}
    ]


def connect_london_population(session: Session, options: dict) -> tuple[int, str, list]:
    boroughs = {row.official_code: row for row in _districts(session, "london")}
    codes = sorted(boroughs) or [f"E09{index:06d}" for index in range(1, 34)]
    text = request_bytes(
        "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv?"
        f"geography={','.join(codes)}&date=latest&gender=0&c_age=200&measures=20100&select=date_name,geography_name,geography_code,obs_value",
        timeout=90,
    ).decode("utf-8-sig")
    regional = request_bytes(
        "https://www.nomisweb.co.uk/api/v01/dataset/NM_2002_1.data.csv?"
        "geography=E12000007&date=" + ",".join(["latest"] + [f"latestMINUS{n}" for n in range(1, 10)]) + "&gender=0&c_age=200&measures=20100&select=date_name,geography_name,geography_code,obs_value",
        timeout=90,
    ).decode("utf-8-sig")
    city = _city(session, "london")
    rows = []
    method = "ONS mid-year population estimate (Nomis NM_2002_1), all ages, persons. Reference date is 30 June of the year."
    for line in csv.DictReader(io.StringIO(text)):
        code = line["GEOGRAPHY_CODE"]
        rows.append(_population_row("london-ons-mye", "london", boroughs.get(code), line["GEOGRAPHY_NAME"], code, int(line["DATE_NAME"]), line["OBS_VALUE"], "official_estimate", method))
    for line in csv.DictReader(io.StringIO(regional)):
        rows.append(_population_row("london-ons-mye", "london", city, "London region", "E12000007", int(line["DATE_NAME"]), line["OBS_VALUE"], "official_estimate", method))
    if not rows:
        raise RuntimeError("Nomis returned no London population rows.")
    written = insert_new(session, POPULATION, rows)
    _mark(session, "london")
    return written, f"Stored {written} ONS mid-year estimate rows for London boroughs and the London region.", [
        {"name": "borough_join", "status": "pass", "detail": "Joined on ONS GSS codes to the LAD 2024 boundaries.", "metrics": {"rows": len(rows), "joined": sum(1 for row in rows if row["geo_unit_id"])}}
    ]


def connect_ams_population(session: Session, options: dict) -> tuple[int, str, list]:
    districts = {row.official_code: row for row in _districts(session, "amsterdam")}
    city = _city(session, "amsterdam")
    codes = sorted(districts) + ["STAD"]
    payload = request_json(
        "https://api.data.amsterdam.nl/v1/bbga/kerncijfers/",
        params={"indicatorDefinitie.variabele": "BEVTOTAAL", "gebiedcode15[in]": ",".join(codes), "jaar[gte]": 2016, "_format": "json", "_pageSize": 500},
        timeout=90,
        headers={"Accept": "application/hal+json, */*"},
    )
    items = ((payload or {}).get("_embedded") or {}).get("kerncijfers") or []
    rows = []
    method = "Basisbestand Gebieden Amsterdam BEVTOTAAL: people in the municipal population register (BRP) on 1 January, including correspondence addresses."
    for item in items:
        code = item.get("gebiedcode15")
        geo = city if code == "STAD" else districts.get(code)
        name = "Amsterdam" if code == "STAD" else (geo.name if geo else code)
        rows.append(_population_row("ams-bbga-population", "amsterdam", geo, name, code, int(item["jaar"]), item.get("waarde"), "register_count", method))
    if not rows:
        raise RuntimeError("BBGA returned no BEVTOTAAL rows.")
    written = insert_new(session, POPULATION, rows)
    _mark(session, "amsterdam")
    return written, f"Stored {written} Amsterdam register population rows for the city and its stadsdelen.", [
        {"name": "register_count", "status": "pass", "detail": "Population register on 1 January. Not a census.", "metrics": {"rows": len(rows)}}
    ]


def connect_eurostat_population(session: Session, options: dict) -> tuple[int, str, list]:
    targets = dict(EUROSTAT_CITY_CODES)
    query = "&".join(f"cities={code}" for code in targets)
    payload = request_json(f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/urb_cpop1?indic_ur=DE1001V&{query}&sinceTimePeriod=2010", timeout=90)
    dims = payload["id"]
    sizes = payload["size"]
    categories = {name: payload["dimension"][name]["category"] for name in dims}
    ordered = {name: sorted(categories[name]["index"], key=lambda key: categories[name]["index"][key]) for name in dims}
    rows = []
    for flat, value in (payload.get("value") or {}).items():
        position = int(flat)
        coordinate = {}
        for name, size in reversed(list(zip(dims, sizes))):
            coordinate[name] = ordered[name][position % size]
            position //= size
        slug = targets.get(coordinate["cities"])
        if not slug:
            continue
        city = _city(session, slug)
        rows.append(
            _population_row(
                "eurostat-city-population",
                slug,
                city,
                categories["cities"]["label"][coordinate["cities"]],
                coordinate["cities"],
                int(coordinate["time"]),
                value,
                "official_estimate",
                "Eurostat Urban Audit urb_cpop1 DE1001V: population on 1 January for the Urban Audit city unit (core or greater city as labelled), supplied by the national statistical office.",
            )
        )
    if not rows:
        raise RuntimeError("Eurostat returned no city population values.")
    written = insert_new(session, POPULATION, rows)
    for slug in targets.values():
        _mark(session, slug)
    labels = ", ".join(sorted(set(targets.values())))
    return written, f"Stored {written} Eurostat Urban Audit population values for {labels}.", [
        {
            "name": "census_break",
            "status": "warn",
            "detail": "German series were revised to the 2022 census, so years around 2022 are not a continuous trend. Greater-city labels are not always identical to municipal boundaries.",
            "metrics": {"rows": len(rows), "cities": sorted(set(targets.values()))},
        }
    ]


def connect_london_crime(session: Session, options: dict) -> tuple[int, str, list]:
    meta = request_json("https://data.london.gov.uk/api/v2/dataset/recorded_crime_summary", timeout=60)
    resources = (meta or {}).get("resources") or {}
    resources = resources.values() if isinstance(resources, dict) else resources
    candidates = [item for item in resources if "Borough Level Crime" in (item.get("title") or "") and "Historical" not in (item.get("url") or "")]
    if not candidates:
        raise RuntimeError("London Datastore did not list a borough-level MPS file.")
    latest = max(candidates, key=lambda item: item.get("check_timestamp") or "")
    text = request_bytes(latest["url"], timeout=120).decode("utf-8-sig")
    boroughs = {row.name: row for row in _districts(session, "london")}
    reader = csv.DictReader(io.StringIO(text))
    months = [field for field in reader.fieldnames or [] if re.fullmatch(r"\d{6}", field)]
    totals: dict[tuple[str, str, str], int] = {}
    skipped: set[str] = set()
    for line in reader:
        borough = line.get("BOCU") or ""
        if borough not in boroughs:
            skipped.add(borough)
            continue
        for month in months:
            value = _num(line.get(month))
            if value is None:
                continue
            key = (month, borough, line.get("Group") or "UNSPECIFIED")
            totals[key] = totals.get(key, 0) + int(value)
    rows = [
        {
            "dataset_code": "london-mps-borough-crime",
            "city_slug": "london",
            "geo_unit_id": boroughs[borough].id,
            "period_label": f"{month[:4]}-{month[4:]}",
            "borough": borough,
            "category": group.title(),
            "offense": None,
            "incident_count": count,
            "completeness": "complete_aggregate",
            "methodology": "Metropolitan Police Service recorded offences by borough and major group, summed over sub-groups. Counts reflect reporting and recording, not all harm.",
            "source_row_id": f"{month}:{borough}:{group}"[:180],
        }
        for (month, borough, group), count in totals.items()
    ]
    if not rows:
        raise RuntimeError("The MPS file had no borough rows that matched the stored boundaries.")
    written = insert_new(session, CRIME_AGG, rows)
    _mark(session, "london")
    return written, f"Stored {written} MPS borough-month-group counts from {months[0]} to {months[-1]}.", [
        {"name": "non_borough_units", "status": "warn" if skipped else "pass", "detail": "Rows for units that are not London boroughs were skipped, so totals exclude them.", "metrics": {"skipped_units": sorted(skipped)[:12], "months": len(months)}}
    ]


def connect_ams_crime(session: Session, options: dict) -> tuple[int, str, list]:
    base = "https://opendata.cbs.nl/ODataApi/odata/83648NED"
    labels = {item["Key"]: item["Title"] for item in (request_json(f"{base}/SoortMisdrijf", timeout=60) or {}).get("value") or []}
    codes = [code for code in labels if code == "T001161" or re.fullmatch(r"CRI\d000", code)]
    payload = request_json(f"{base}/TypedDataSet", params={"$filter": "RegioS eq 'GM0363'", "$select": "SoortMisdrijf,Perioden,TotaalGeregistreerdeMisdrijven_1,GeregistreerdeMisdrijvenPer1000Inw_3"}, timeout=90)
    rows = []
    for item in (payload or {}).get("value") or []:
        code = (item.get("SoortMisdrijf") or "").strip()
        if code not in codes or item.get("TotaalGeregistreerdeMisdrijven_1") is None:
            continue
        year = (item.get("Perioden") or "")[:4]
        label = re.sub(r"^\d\s+", "", labels.get(code, code))
        rows.append(
            {
                "dataset_code": "ams-cbs-crime",
                "city_slug": "amsterdam",
                "geo_unit_id": _city(session, "amsterdam").id,
                "period_label": year,
                "borough": None,
                "category": "Total" if code == "T001161" else label,
                "offense": code,
                "incident_count": int(item["TotaalGeregistreerdeMisdrijven_1"]),
                "completeness": "complete_aggregate",
                "methodology": f"CBS / Politie registered crimes in the municipality of Amsterdam (GM0363). Per 1,000 inhabitants: {item.get('GeregistreerdeMisdrijvenPer1000Inw_3')}.",
                "source_row_id": f"{code}:{year}",
            }
        )
    if not rows:
        raise RuntimeError("CBS returned no registered-crime rows for Amsterdam.")
    written = insert_new(session, CRIME_AGG, rows)
    _mark(session, "amsterdam")
    return written, f"Stored {written} CBS registered-crime rows for Amsterdam.", [
        {"name": "municipal_total", "status": "pass", "detail": "Municipal annual totals. Not broken down by stadsdeel.", "metrics": {"rows": len(rows)}}
    ]


def connect_sg_crime(session: Session, options: dict) -> tuple[int, str, list]:
    payload = request_json("https://tablebuilder.singstat.gov.sg/api/table/tabledata/M890891", params={"limit": 2000}, timeout=60)
    data = (payload or {}).get("Data") or {}
    city = _city(session, "singapore")
    rows = []
    for row in data.get("row") or []:
        category = "Total" if row.get("rowText") == "Total" else row.get("rowText")
        for column in row.get("columns") or []:
            year = column["key"]
            if int(year) < 2012 or column.get("value") in (None, "", "na"):
                continue
            rows.append(
                {
                    "dataset_code": "sg-spf-major-offences",
                    "city_slug": "singapore",
                    "geo_unit_id": city.id,
                    "period_label": year,
                    "borough": None,
                    "category": category,
                    "offense": row.get("seriesNo"),
                    "incident_count": int(float(column["value"])),
                    "completeness": "complete_aggregate",
                    "methodology": "Singapore Police Force cases recorded for selected major offences (SingStat M890891). Selected offences only, not all crime.",
                    "source_row_id": f"{row.get('seriesNo')}:{year}",
                }
            )
    if not rows:
        raise RuntimeError("SingStat M890891 returned no offence rows.")
    written = insert_new(session, CRIME_AGG, rows)
    _mark(session, "singapore")
    return written, f"Stored {written} SPF selected-major-offence rows (last updated {data.get('dataLastUpdated')}).", [
        {"name": "selected_offences", "status": "warn", "detail": "Selected major offences only. Some series stop in earlier years.", "metrics": {"rows": len(rows)}}
    ]


def connect_london_traffic_counts(session: Session, options: dict) -> tuple[int, str, list]:
    this_year = datetime.now(timezone.utc).year
    boroughs = _district_shapes(session, "london")
    chosen_year, records = None, []
    for year in (this_year - 1, this_year - 2, this_year - 3):
        page, records = 1, []
        while page <= 10:
            payload = request_json(
                "https://roadtraffic.dft.gov.uk/api/average-annual-daily-flow",
                params={"filter[region_id]": 6, "filter[year]": year, "page[size]": 1000, "page[number]": page},
                timeout=120,
            ) or {}
            records.extend(payload.get("data") or [])
            if not payload.get("next_page_url"):
                break
            page += 1
        if records:
            chosen_year = year
            break
    if not records:
        raise RuntimeError("DfT returned no London AADF rows for the last three years.")
    rows = []
    for item in records:
        lat, lon = _num(item.get("latitude")), _num(item.get("longitude"))
        borough = _district_for_point(boroughs, lon, lat)
        rows.append(
            {
                "dataset_code": "london-dft-aadf",
                "city_slug": "london",
                "geo_unit_id": borough.id if borough else None,
                "observed_at": datetime(chosen_year, 7, 1, tzinfo=timezone.utc),
                "borough": borough.name if borough else None,
                "segment_id": str(item.get("count_point_id")),
                "street": item.get("road_name"),
                "direction": None,
                "volume": _num(item.get("all_motor_vehicles")),
                "speed_mph": None,
                "travel_time_sec": None,
                "latitude": lat,
                "longitude": lon,
                "source_row_id": f"{chosen_year}:{item.get('count_point_id')}",
                "attributes": {
                    "year": chosen_year,
                    "road_category": item.get("road_category"),
                    "road_type": item.get("road_type"),
                    "estimation_method": item.get("estimation_method"),
                    "cars_and_taxis": item.get("cars_and_taxis"),
                    "buses_and_coaches": item.get("buses_and_coaches"),
                    "all_hgvs": item.get("all_hgvs"),
                    "pedal_cycles": item.get("pedal_cycles"),
                },
            }
        )
    written = insert_new(session, TRAFFIC, rows)
    counted = sum(1 for item in records if item.get("estimation_method") == "Counted")
    _mark(session, "london")
    return written, f"Stored {written} DfT annual average daily flow count points for London in {chosen_year}.", [
        {"name": "estimated_vs_counted", "status": "warn", "detail": "Some AADF values are estimated from earlier counts rather than counted that year.", "metrics": {"year": chosen_year, "points": len(records), "counted": counted}}
    ]


def connect_sg_taxis(session: Session, options: dict) -> tuple[int, str, list]:
    payload = request_json("https://api.data.gov.sg/v1/transport/taxi-availability", timeout=60)
    feature = ((payload or {}).get("features") or [None])[0] or {}
    props = feature.get("properties") or {}
    stamp = props.get("timestamp")
    count = props.get("taxi_count")
    if stamp is None or count is None:
        raise RuntimeError("LTA taxi availability returned no count.")
    row = {
        "dataset_code": "sg-taxi-availability",
        "city_slug": "singapore",
        "feature_type": "available_taxis",
        "name": "Available taxis",
        "value": float(count),
        "unit": "taxis",
        "methodology": "LTA taxi availability snapshot via data.gov.sg: taxis reporting as available for hire at the timestamp. Not fleet size or demand.",
        "source_row_id": stamp,
        "attributes": {"timestamp": stamp},
    }
    written = insert_new(session, INFRA, [row])
    _mark(session, "singapore")
    return written, f"Stored the taxi availability snapshot at {stamp}: {count} taxis available.", [
        {"name": "snapshot", "status": "pass", "detail": "One snapshot per refresh. The series grows only as refreshes run.", "metrics": {"taxis": count}}
    ]


def connect_osm_stations(session: Session, options: dict) -> tuple[int, str, list]:
    cities = options.get("cities") or OTHER_CITIES
    total, notes = 0, []
    for slug in cities:
        south, west, north, east = _bbox(session, slug)
        query = f"""
        [out:json][timeout:120];
        (
          node["railway"~"^(station|halt)$"]({south},{west},{north},{east});
          node["railway"="tram_stop"]({south},{west},{north},{east});
          node["station"~"^(subway|light_rail|monorail)$"]({south},{west},{north},{east});
        );
        out body 6000;
        """
        try:
            elements = _overpass(query)
        except Exception as exc:
            notes.append(f"{slug}: {exc}")
            continue
        area = _city_shape(session, slug)
        rows = []
        for element in elements:
            lat, lon = element.get("lat"), element.get("lon")
            if lat is None or lon is None or (area is not None and not area.contains(Point(lon, lat))):
                continue
            tags = element.get("tags") or {}
            kind = tags.get("station") or tags.get("railway") or "station"
            rows.append(
                {
                    "dataset_code": "osm-rail-stations",
                    "city_slug": slug,
                    "stop_id": f"{slug}:{element.get('id')}"[:64],
                    "name": (tags.get("name") or f"OSM node {element.get('id')}")[:256],
                    "latitude": lat,
                    "longitude": lon,
                    "location_type": kind[:16],
                    "route_ids": tags.get("network"),
                }
            )
        written = insert_new(session, STOPS, rows, key="stop_id")
        total += written
        notes.append(f"{slug}: {len(rows)} inside the boundary")
        _mark(session, slug)
        time.sleep(2)
    if total == 0 and all(":" in note and "inside" not in note for note in notes):
        raise RuntimeError("Overpass returned no station nodes. " + "; ".join(notes))
    return total, "Stored OpenStreetMap rail, metro, and tram stops. " + "; ".join(notes) + ".", [
        {"name": "community_mapped", "status": "warn", "detail": "OSM station and tram-stop nodes inside the city boundary. Bus stops are excluded. © OpenStreetMap contributors.", "metrics": {"written": total}}
    ]


def connect_osm_roads(session: Session, options: dict) -> tuple[int, str, list]:
    cities = options.get("cities") or OTHER_CITIES
    total, notes = 0, []
    for slug in cities:
        south, west, north, east = _bbox(session, slug)
        query = f"""
        [out:json][timeout:120];
        way["highway"~"^(motorway|trunk)$"]({south},{west},{north},{east});
        out geom 1500;
        """
        try:
            elements = _overpass(query)
        except Exception as exc:
            notes.append(f"{slug}: {exc}")
            continue
        area = _city_shape(session, slug)
        rows = []
        for element in elements:
            coords = [[node["lon"], node["lat"]] for node in element.get("geometry") or [] if "lon" in node]
            if len(coords) < 2:
                continue
            line = LineString(coords)
            if area is not None and not area.intersects(line):
                continue
            tags = element.get("tags") or {}
            rows.append(
                {
                    "dataset_code": "osm-city-roads",
                    "city_slug": slug,
                    "feature_type": "major_road",
                    "name": tags.get("name") or tags.get("ref") or f"way {element.get('id')}",
                    "value": None,
                    "unit": None,
                    "methodology": f"OpenStreetMap motorway and trunk ways intersecting the {slug} boundary, via Overpass. © OpenStreetMap contributors.",
                    "geometry_geojson": json.dumps(mapping(line)),
                    "source_row_id": f"{slug}:{element.get('id')}",
                    "attributes": {"highway": tags.get("highway"), "ref": tags.get("ref")},
                }
            )
        written = insert_new(session, INFRA, rows)
        total += written
        notes.append(f"{slug}: {len(rows)} ways")
        _mark(session, slug)
        time.sleep(2)
    return total, "Stored OSM motorway and trunk ways. " + "; ".join(notes) + ".", [
        {"name": "coverage", "status": "warn", "detail": "Motorway and trunk only. Local streets are not included.", "metrics": {"written": total}}
    ]


def connect_paris_arrondissements(session: Session, options: dict) -> tuple[int, str, list]:
    payload = request_json(
        "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/arrondissements/records",
        params={"limit": 20},
        timeout=90,
    )
    items = []
    for record in (payload or {}).get("results") or []:
        geometry = record.get("geom")
        if isinstance(geometry, dict) and geometry.get("type") == "Feature":
            geometry = geometry.get("geometry")
        name = record.get("l_aroff") or record.get("l_ar")
        code = str(record.get("c_arinsee") or record.get("c_ar") or "")
        if geometry and name:
            items.append((code, name, geometry))
    if not items:
        raise RuntimeError("opendata.paris.fr returned no arrondissement polygons.")
    written = _save_districts(session, "paris", items, "arrondissement", "Ville de Paris open data arrondissements")
    return written, f"Loaded {written} Paris arrondissements.", [
        {"name": "boundary_source", "status": "pass" if written == 20 else "warn", "detail": "Official Paris arrondissement polygons from opendata.paris.fr.", "metrics": {"features": written}}
    ]


def connect_chicago_community_areas(session: Session, options: dict) -> tuple[int, str, list]:
    features = request_json(
        "https://data.cityofchicago.org/resource/igwz-8jzy.json",
        params={"$limit": "100", "$select": "community,area_numbe,the_geom"},
        timeout=90,
    ) or []
    items = []
    for feature in features:
        geometry = feature.get("the_geom")
        name = feature.get("community")
        code = str(feature.get("area_numbe") or "")
        if geometry and name:
            items.append((code, name.title(), geometry))
    if not items:
        raise RuntimeError("Chicago community-area boundaries returned no polygons.")
    written = _save_districts(session, "chicago", items, "community_area", "City of Chicago Boundaries - Community Areas (current)")
    return written, f"Loaded {written} Chicago community areas.", [
        {"name": "boundary_source", "status": "pass" if written == 77 else "warn", "detail": "Official community-area polygons from data.cityofchicago.org.", "metrics": {"features": written}}
    ]


def connect_chicago_population(session: Session, options: dict) -> tuple[int, str, list]:
    city = _city(session, "chicago")
    districts = {row.name.upper(): row for row in _districts(session, "chicago")}
    rows = []
    citywide = request_json(
        "https://data.cityofchicago.org/resource/85cm-7uqa.json",
        params={"$where": "geography_type='Citywide'", "$limit": "50", "$order": "year"},
        timeout=60,
    ) or []
    method_city = "City of Chicago Population Counts (data.cityofchicago.org 85cm-7uqa), citywide geography. ACS-based city totals published by the city."
    for item in citywide:
        year = int(item["year"])
        rows.append(
            _population_row(
                "chicago-population-counts",
                "chicago",
                city,
                "Chicago",
                f"CHI-CITY-{year}",
                year,
                item.get("population_total"),
                "official_estimate",
                method_city,
            )
        )
    community = request_json(
        "https://data.cityofchicago.org/resource/t68z-cikk.json",
        params={"$limit": "100", "$select": "community_area,total_population,acs_year"},
        timeout=60,
    ) or []
    method_area = "City of Chicago ACS 5-year estimates aggregated to community areas (t68z-cikk). Tract-to-area allocation is approximate because tracts and community areas do not align perfectly."
    joined = 0
    for item in community:
        name = (item.get("community_area") or "").upper()
        geo = districts.get(name)
        if geo is not None:
            joined += 1
        rows.append(
            _population_row(
                "chicago-acs-community",
                "chicago",
                geo,
                (item.get("community_area") or "").title(),
                name or "UNKNOWN",
                int(item["acs_year"]),
                item.get("total_population"),
                "acs_estimate",
                method_area,
            )
        )
    if not rows:
        raise RuntimeError("Chicago population endpoints returned no rows.")
    written = insert_new(session, POPULATION, rows)
    _mark(session, "chicago")
    return written, f"Stored {written} Chicago population rows (citywide and community areas).", [
        {"name": "community_join", "status": "pass" if joined else "warn", "detail": "Community-area ACS rows joined to stored boundaries by name.", "metrics": {"rows": len(rows), "joined": joined}}
    ]


def _soda_month_counts(domain: str, dataset: str, date_field: str, since: str) -> list[dict]:
    return request_json(
        f"https://{domain}/resource/{dataset}.json",
        params={
            "$select": f"date_trunc_ym({date_field}) as month,count(*) as n",
            "$where": f"{date_field} >= '{since}'",
            "$group": "month",
            "$order": "month",
            "$limit": "120",
        },
        timeout=90,
    ) or []


def _month_label(value: str) -> str | None:
    if not value:
        return None
    return value[:7]


def connect_chicago_crashes(session: Session, options: dict) -> tuple[int, str, list]:
    since = options.get("since") or "2023-01-01T00:00:00"
    months = _soda_month_counts("data.cityofchicago.org", "85ca-t3if", "crash_date", since)
    rows = []
    method = "City of Chicago Traffic Crashes (85ca-t3if): monthly count of crash records. Not a traffic volume or speed measure."
    for item in months:
        label = _month_label(item.get("month") or "")
        if not label:
            continue
        year, month = map(int, label.split("-"))
        rows.append(
            {
                "dataset_code": "chicago-traffic-crashes",
                "city_slug": "chicago",
                "geo_unit_id": _city(session, "chicago").id,
                "observed_at": datetime(year, month, 1, tzinfo=timezone.utc),
                "borough": None,
                "segment_id": label,
                "street": None,
                "direction": None,
                "volume": _num(item.get("n")),
                "speed_mph": None,
                "travel_time_sec": None,
                "latitude": None,
                "longitude": None,
                "source_row_id": f"month:{label}",
                "attributes": {"year": year, "month": label, "metric": "crash_count"},
            }
        )
    if not rows:
        raise RuntimeError("Chicago traffic crashes returned no monthly counts.")
    written = insert_new(session, TRAFFIC, rows)
    _mark(session, "chicago")
    return written, f"Stored {written} monthly Chicago crash-count rows since {since[:10]}.", [
        {"name": "crash_counts", "status": "pass", "detail": method, "metrics": {"months": len(rows)}}
    ]


def connect_chicago_crime(session: Session, options: dict) -> tuple[int, str, list]:
    since = options.get("since") or "2023-01-01T00:00:00"
    months = _soda_month_counts("data.cityofchicago.org", "ijzp-q8t2", "date", since)
    city = _city(session, "chicago")
    rows = []
    method = "Chicago Police Department Crimes - 2001 to Present (ijzp-q8t2): monthly count of recorded crime incidents citywide. Counts reflect reporting and recording practice."
    for item in months:
        label = _month_label(item.get("month") or "")
        if not label:
            continue
        rows.append(
            {
                "dataset_code": "chicago-crime-monthly",
                "city_slug": "chicago",
                "geo_unit_id": city.id,
                "period_label": label,
                "borough": None,
                "category": "Total",
                "offense": None,
                "incident_count": int(float(item.get("n") or 0)),
                "completeness": "complete_aggregate",
                "methodology": method,
                "source_row_id": f"total:{label}",
            }
        )
    if not rows:
        raise RuntimeError("Chicago crime returned no monthly counts.")
    written = insert_new(session, CRIME_AGG, rows)
    _mark(session, "chicago")
    return written, f"Stored {written} Chicago monthly crime totals since {since[:10]}.", [
        {"name": "citywide_month", "status": "pass", "detail": "Citywide monthly totals only. No community-area crime map is drawn from this extract.", "metrics": {"months": len(rows)}}
    ]


def connect_la_crime(session: Session, options: dict) -> tuple[int, str, list]:
    since = options.get("since") or "2023-01-01T00:00:00"
    months = _soda_month_counts("data.lacity.org", "2nrs-mtv8", "date_occ", since)
    city = _city(session, "los-angeles")
    rows = []
    method = "LAPD Crime Data from 2020 to Present (2nrs-mtv8): monthly count of recorded crime incidents. Recent months can be incomplete while records are still being entered."
    for item in months:
        label = _month_label(item.get("month") or "")
        if not label:
            continue
        rows.append(
            {
                "dataset_code": "la-crime-monthly",
                "city_slug": "los-angeles",
                "geo_unit_id": city.id,
                "period_label": label,
                "borough": None,
                "category": "Total",
                "offense": None,
                "incident_count": int(float(item.get("n") or 0)),
                "completeness": "complete_aggregate",
                "methodology": method,
                "source_row_id": f"total:{label}",
            }
        )
    if not rows:
        raise RuntimeError("LAPD crime returned no monthly counts.")
    written = insert_new(session, CRIME_AGG, rows)
    _mark(session, "los-angeles")
    return written, f"Stored {written} Los Angeles monthly crime totals since {since[:10]}.", [
        {"name": "lagging_months", "status": "warn", "detail": "The newest months often under-count until late reports are entered.", "metrics": {"months": len(rows)}}
    ]


def connect_la_collisions(session: Session, options: dict) -> tuple[int, str, list]:
    since = options.get("since") or "2023-01-01T00:00:00"
    months = _soda_month_counts("data.lacity.org", "d5tf-ez2w", "date_occ", since)
    rows = []
    method = "LAPD Traffic Collision Data from 2010 to Present (d5tf-ez2w): monthly count of traffic-collision crime records. The city has marked recent publication as frozen; treat the newest months as incomplete."
    for item in months:
        label = _month_label(item.get("month") or "")
        if not label:
            continue
        year, month = map(int, label.split("-"))
        rows.append(
            {
                "dataset_code": "la-traffic-collisions",
                "city_slug": "los-angeles",
                "geo_unit_id": _city(session, "los-angeles").id,
                "observed_at": datetime(year, month, 1, tzinfo=timezone.utc),
                "borough": None,
                "segment_id": label,
                "street": None,
                "direction": None,
                "volume": _num(item.get("n")),
                "speed_mph": None,
                "travel_time_sec": None,
                "latitude": None,
                "longitude": None,
                "source_row_id": f"month:{label}",
                "attributes": {"year": year, "month": label, "metric": "collision_count", "publication": "frozen_or_lagging"},
            }
        )
    if not rows:
        raise RuntimeError("LAPD traffic collisions returned no monthly counts.")
    written = insert_new(session, TRAFFIC, rows)
    _mark(session, "los-angeles")
    return written, f"Stored {written} monthly Los Angeles collision-count rows since {since[:10]}.", [
        {"name": "frozen_feed", "status": "warn", "detail": method, "metrics": {"months": len(rows)}}
    ]


def connect_toronto_crime(session: Session, options: dict) -> tuple[int, str, list]:
    resource_id = "5d04d510-88cb-4b48-8311-94b3e155e100"
    city = _city(session, "toronto")
    totals: dict[str, int] = {}
    categories: dict[tuple[str, str], int] = {}
    offset = 0
    total = None
    while True:
        payload = request_json(
            "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search",
            params={"resource_id": resource_id, "limit": "10000", "offset": str(offset)},
            timeout=120,
        ) or {}
        result = payload.get("result") or {}
        records = result.get("records") or []
        if total is None:
            total = result.get("total") or 0
        if not records:
            break
        for record in records:
            year = str(record.get("REPORT_YEAR") or "")
            category = record.get("CATEGORY") or "Unspecified"
            try:
                count = int(float(record.get("COUNT_") or 0))
            except (TypeError, ValueError):
                count = 0
            if not year:
                continue
            totals[year] = totals.get(year, 0) + count
            categories[(year, category)] = categories.get((year, category), 0) + count
        offset += len(records)
        if offset >= total:
            break
    rows = []
    method = "Toronto Police Service Annual Statistical Report - Reported Crimes (open.toronto.ca). Annual sums of COUNT_ by report year and category."
    for year, count in sorted(totals.items()):
        rows.append(
            {
                "dataset_code": "toronto-reported-crime",
                "city_slug": "toronto",
                "geo_unit_id": city.id,
                "period_label": year,
                "borough": None,
                "category": "Total",
                "offense": None,
                "incident_count": count,
                "completeness": "complete_aggregate",
                "methodology": method,
                "source_row_id": f"total:{year}",
            }
        )
    for (year, category), count in sorted(categories.items()):
        rows.append(
            {
                "dataset_code": "toronto-reported-crime",
                "city_slug": "toronto",
                "geo_unit_id": city.id,
                "period_label": year,
                "borough": None,
                "category": category,
                "offense": None,
                "incident_count": count,
                "completeness": "complete_aggregate",
                "methodology": method,
                "source_row_id": f"{year}:{_slug(category)}"[:180],
            }
        )
    if not rows:
        raise RuntimeError("Toronto reported-crimes datastore returned no rows.")
    written = insert_new(session, CRIME_AGG, rows)
    _mark(session, "toronto")
    return written, f"Stored {written} Toronto reported-crime aggregates across {len(totals)} years.", [
        {"name": "annual_totals", "status": "pass", "detail": "Citywide annual totals and category breakdowns. No neighbourhood crime map is drawn from this extract.", "metrics": {"years": sorted(totals), "records_read": offset}}
    ]


def connect_toronto_collisions(session: Session, options: dict) -> tuple[int, str, list]:
    resource_id = "4ad77de0-a9e0-4725-95d9-dbce6776d6cf"
    years = [str(year) for year in range(2014, datetime.now(timezone.utc).year + 1)]
    rows = []
    method = "Toronto Police Service Traffic Collisions open dataset: annual collision counts from the CKAN datastore total for each OCC_YEAR. Not a traffic volume or speed measure."
    for year in years:
        payload = request_json(
            "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search",
            params={"resource_id": resource_id, "limit": "0", "filters": json.dumps({"OCC_YEAR": year})},
            timeout=60,
        ) or {}
        total = (payload.get("result") or {}).get("total")
        if not total:
            continue
        rows.append(
            {
                "dataset_code": "toronto-traffic-collisions",
                "city_slug": "toronto",
                "geo_unit_id": _city(session, "toronto").id,
                "observed_at": datetime(int(year), 7, 1, tzinfo=timezone.utc),
                "borough": None,
                "segment_id": year,
                "street": None,
                "direction": None,
                "volume": float(total),
                "speed_mph": None,
                "travel_time_sec": None,
                "latitude": None,
                "longitude": None,
                "source_row_id": f"year:{year}",
                "attributes": {"year": int(year), "metric": "collision_count"},
            }
        )
        time.sleep(0.15)
    if not rows:
        raise RuntimeError("Toronto traffic collisions returned no yearly totals.")
    written = insert_new(session, TRAFFIC, rows)
    _mark(session, "toronto")
    return written, f"Stored {written} annual Toronto collision-count rows.", [
        {"name": "annual_counts", "status": "pass", "detail": method, "metrics": {"years": [row["segment_id"] for row in rows]}}
    ]


def connect_toronto_population(session: Session, options: dict) -> tuple[int, str, list]:
    resource_id = "7f8eee5e-85fb-415c-aef3-c3bd4998445f"
    city = _city(session, "toronto")
    rows = []
    method = "City of Toronto Neighbourhood Profiles 2016 (open.toronto.ca): Census Profile population figures for the City of Toronto column."
    offset = 0
    total = None
    while True:
        payload = request_json(
            "https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/datastore_search",
            params={"resource_id": resource_id, "limit": "100", "offset": str(offset)},
            timeout=90,
        ) or {}
        result = payload.get("result") or {}
        records = result.get("records") or []
        if total is None:
            total = result.get("total") or 0
        if not records:
            break
        for record in records:
            characteristic = record.get("Characteristic") or ""
            match = re.fullmatch(r"Population,\s*(\d{4})", characteristic.strip())
            if not match:
                continue
            year = int(match.group(1))
            raw = (record.get("City of Toronto") or "").replace(",", "")
            value = _num(raw)
            if value is None:
                continue
            rows.append(
                _population_row(
                    "toronto-neighbourhood-profiles",
                    "toronto",
                    city,
                    "Toronto",
                    f"TOR-CITY-{year}",
                    year,
                    value,
                    "census_count",
                    method,
                )
            )
        offset += len(records)
        if rows or offset >= total:
            break
    if not rows:
        raise RuntimeError("Toronto neighbourhood profiles returned no city population rows.")
    written = insert_new(session, POPULATION, rows)
    _mark(session, "toronto")
    return written, f"Stored {written} Toronto city population census rows from the 2016 neighbourhood profiles.", [
        {"name": "city_column_only", "status": "warn", "detail": "Neighbourhood columns are not loaded in this extract; only the City of Toronto totals are stored.", "metrics": {"rows": len(rows)}}
    ]


def connect_madrid_air(session: Session, options: dict) -> tuple[int, str, list]:
    station_text = request_bytes(
        "https://datos.madrid.es/egob/catalogo/212629-1-estaciones-control-aire.csv",
        timeout=60,
    ).decode("latin-1")
    stations = {}
    reader = csv.DictReader(io.StringIO(station_text), delimiter=";")
    for line in reader:
        code = (line.get("CODIGO_CORTO") or line.get("CODIGO") or "").lstrip("0") or line.get("CODIGO_CORTO")
        if not code:
            continue
        stations[str(int(code))] = {
            "name": line.get("ESTACION") or code,
            "lat": _num((line.get("LATITUD") or "").replace(",", ".")),
            "lon": _num((line.get("LONGITUD") or "").replace(",", ".")),
            "type": line.get("NOM_TIPO"),
        }
    # Redirect target of the egob tiempo-real CSV catalogue entry.
    text = request_bytes(
        "https://ciudadesabiertas.madrid.es/dynamicAPI/API/query/calair_tiemporeal.csv?pageSize=5000",
        timeout=120,
    ).decode("latin-1", errors="replace")
    if "PROVINCIA" not in text and "MAGNITUD" not in text:
        # Fallback: some responses wrap CSV in JSON.
        try:
            payload = json.loads(text)
            text = payload if isinstance(payload, str) else ""
        except json.JSONDecodeError:
            text = text
    if "MAGNITUD" not in text:
        raise RuntimeError("Madrid realtime air feed did not return a CSV with MAGNITUD columns.")
    sample = text.lstrip()
    dialect_delim = ";" if sample.splitlines()[0].count(";") >= sample.splitlines()[0].count(",") else ","
    reader = csv.DictReader(io.StringIO(text), delimiter=dialect_delim)
    magnitude = {"8": ("no2", "µg/m³"), "9": ("pm25", "µg/m³"), "10": ("pm10", "µg/m³"), "1": ("so2", "µg/m³"), "14": ("o3", "µg/m³"), "6": ("co", "mg/m³")}
    rows = []
    for line in reader:
        mag = str(line.get("MAGNITUD") or "").lstrip("0") or str(line.get("MAGNITUD") or "")
        if mag not in magnitude:
            continue
        parameter, unit = magnitude[mag]
        station_code = str(int(line.get("ESTACION") or line.get("ESTACIÓN") or 0))
        info = stations.get(station_code, {"name": f"Station {station_code}", "lat": None, "lon": None, "type": None})
        year = int(line.get("ANO") or line.get("AÑO") or 0)
        month = int(line.get("MES") or 0)
        day = int(line.get("DIA") or 0)
        if not year or not month or not day:
            continue
        latest_hour = None
        latest_value = None
        for hour in range(1, 25):
            flag = (line.get(f"V{hour:02d}") or "").strip().upper()
            if flag != "V":
                continue
            value = _num(line.get(f"H{hour:02d}"))
            if value is None:
                continue
            latest_hour = hour
            latest_value = value
        if latest_hour is None:
            continue
        observed = datetime(year, month, day, min(latest_hour, 23), tzinfo=ZoneInfo("Europe/Madrid"))
        if latest_hour == 24:
            observed = datetime(year, month, day, 0, tzinfo=ZoneInfo("Europe/Madrid")) + timedelta(days=1)
        rows.append(
            _official_air_row(
                "madrid-air-quality",
                "madrid",
                station_code,
                info["name"],
                parameter,
                latest_value,
                unit,
                observed,
                info["lat"],
                info["lon"],
                "Ayuntamiento de Madrid realtime air network: latest validated hour (V) for the published day at one station. Values are provisional until reviewed.",
                {"station_type": info.get("type"), "magnitude": mag},
            )
        )
    if not rows:
        raise RuntimeError("Madrid air feed produced no validated hourly values.")
    written = insert_new(session, ENVIRONMENT, rows)
    _mark(session, "madrid")
    return written, f"Stored {written} Madrid station-pollutant readings from the realtime network.", [
        {"name": "validated_hours_only", "status": "pass", "detail": "Only hours marked V (validated for publication) are stored. Station coordinates come from the control-station catalogue.", "metrics": {"rows": len(rows), "stations": len({row['attributes']['station'] for row in rows})}}
    ]


CITY_CONNECTORS = {
    "osm-city-boundaries": connect_city_boundaries,
    "sg-planning-areas": connect_sg_planning_areas,
    "ams-stadsdelen": connect_ams_stadsdelen,
    "london-boroughs": connect_london_boroughs,
    "berlin-bezirke": connect_berlin_bezirke,
    "trier-ortsbezirke-osm": connect_trier_ortsbezirke,
    "paris-arrondissements": connect_paris_arrondissements,
    "chicago-community-areas": connect_chicago_community_areas,
    "sg-nea-pm25": connect_sg_nea_air,
    "london-laqn-index": connect_london_laqn,
    "uba-air-quality": connect_uba_air,
    "ams-luchtmeetnet": connect_ams_luchtmeetnet,
    "madrid-air-quality": connect_madrid_air,
    "sg-singstat-population": connect_sg_population,
    "london-ons-mye": connect_london_population,
    "ams-bbga-population": connect_ams_population,
    "eurostat-city-population": connect_eurostat_population,
    "chicago-population-counts": connect_chicago_population,
    "toronto-neighbourhood-profiles": connect_toronto_population,
    "london-mps-borough-crime": connect_london_crime,
    "ams-cbs-crime": connect_ams_crime,
    "sg-spf-major-offences": connect_sg_crime,
    "chicago-crime-monthly": connect_chicago_crime,
    "la-crime-monthly": connect_la_crime,
    "toronto-reported-crime": connect_toronto_crime,
    "london-dft-aadf": connect_london_traffic_counts,
    "chicago-traffic-crashes": connect_chicago_crashes,
    "la-traffic-collisions": connect_la_collisions,
    "toronto-traffic-collisions": connect_toronto_collisions,
    "sg-taxi-availability": connect_sg_taxis,
    "osm-rail-stations": connect_osm_stations,
    "osm-city-roads": connect_osm_roads,
}

CITY_SEQUENCE = list(CITY_CONNECTORS)

CITY_CURRENT_SEQUENCE = [
    "sg-nea-pm25",
    "london-laqn-index",
    "uba-air-quality",
    "ams-luchtmeetnet",
    "sg-taxi-availability",
    "london-mps-borough-crime",
    "chicago-crime-monthly",
    "la-crime-monthly",
    "chicago-traffic-crashes",
    "la-traffic-collisions",
]
