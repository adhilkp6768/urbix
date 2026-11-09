from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from shapely.geometry import LineString, mapping, shape
from shapely import wkt
from sqlalchemy.orm import Session

from urbix_data.http_client import HttpError, SodaClient, request_bytes, request_json
from urbix_data.reference import COUNTY_TO_BOROUGH, REFERENCE_GEOGRAPHY, canonical_borough, reference_city_slugs
from urbix_data.repository import (
    CRIME_AGG,
    CRIME_POINT,
    ENVIRONMENT,
    INFRA,
    POPULATION,
    RIDERS,
    STOPS,
    TRAFFIC,
    WASTE,
    WEATHER,
    add_quality,
    finish_job,
    get_geo,
    insert_new,
    save_geo,
    start_job,
    upsert_catalog,
)
from urbix_db.models import GeoUnit
from urbix_db.spatial import centroid_latlon, geometry_area_km2, h3_cell

NYC = ZoneInfo("America/New_York")
NYC_SODA = SodaClient("data.cityofnewyork.us")
NY_SODA = SodaClient("data.ny.gov")


def _num(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_dt(value: str | None, tz=timezone.utc) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y / %m", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                parsed = None
        if parsed is None:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed


def _geojson_text(value) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        try:
            geom = wkt.loads(value)
            return json.dumps(mapping(geom))
        except Exception:
            return None
    try:
        shape(value)
    except Exception:
        return None
    return json.dumps(value)


def _apply_geometry(session: Session, geo: GeoUnit, geojson_text: str | None) -> None:
    if not geojson_text:
        return
    geom = shape(json.loads(geojson_text))
    geo.boundary_geojson = geojson_text
    area = geometry_area_km2(geom)
    if area:
        geo.area_km2 = area
    center = centroid_latlon(geom)
    if center:
        geo.latitude, geo.longitude = center
        properties = dict(geo.properties or {})
        properties["centroid_method"] = "boundary_centroid"
        geo.properties = properties
    session.flush()


def seed_reference_geography(session: Session) -> int:
    by_slug = {}
    count = 0
    for item in REFERENCE_GEOGRAPHY:
        parent = by_slug.get(item["parent_slug"]) if item.get("parent_slug") else None
        existing = get_geo(session, item["slug"])
        status = "reference"
        properties = item.get("properties") or {"centroid_method": "reference_point"}
        if existing is not None:
            if existing.integration_status in {"partial", "integrated"}:
                status = existing.integration_status
            if existing.properties:
                properties = existing.properties
        geo = save_geo(
            session,
            {
                "slug": item["slug"],
                "name": item["name"],
                "level_code": item["level_code"],
                "parent_id": parent.id if parent else None,
                "country_code": item.get("country_code"),
                "timezone": item.get("timezone"),
                "latitude": item.get("latitude"),
                "longitude": item.get("longitude"),
                "properties": properties,
                "integration_status": status,
            },
        )
        by_slug[item["slug"]] = geo
        count += 1
    return count


def _mark_city(session: Session, slug: str, status: str) -> None:
    city = get_geo(session, slug)
    if city is not None and city.integration_status != "integrated":
        city.integration_status = status


def run_connector(session: Session, code: str, options: dict | None = None) -> dict:
    upsert_catalog(session)
    options = options or {}
    if code == "reference-geography":
        rows = seed_reference_geography(session)
        return {"dataset_code": code, "status": "succeeded", "rows_written": rows, "message": "Reference geography seeded."}
    connector = CONNECTORS.get(code)
    if connector is None:
        return {"dataset_code": code, "status": "failed", "rows_written": 0, "message": "Unknown connector."}
    job = start_job(session, code, options)
    try:
        rows, message, quality = connector(session, options)
        for item in quality:
            add_quality(session, code, job.id, item["name"], item["status"], item["detail"], item.get("metrics"))
        finish_job(session, job, rows=rows, status="succeeded", message=message)
        if code.startswith(("nyc-", "nypd-", "mta-")) or code == "osm-major-roads":
            _mark_city(session, "nyc", "partial")
        return {"dataset_code": code, "status": "succeeded", "rows_written": rows, "message": message}
    except Exception as exc:
        session.rollback()
        job = start_job(session, code, options)
        finish_job(session, job, rows=0, status="failed", message=str(exc))
        add_quality(session, code, job.id, "extract", "fail", str(exc))
        return {"dataset_code": code, "status": "failed", "rows_written": 0, "message": str(exc)}


def _load_boundaries(session: Session, dataset_id: str, kind: str) -> tuple[list, list[dict]]:
    rows = NYC_SODA.fetch(dataset_id, max_rows=5000, page_size=1000)
    city = get_geo(session, "nyc")
    boroughs = {
        geo.name: geo
        for geo in session.query(GeoUnit).filter(GeoUnit.level_code == "district", GeoUnit.parent_id == (city.id if city else None)).all()
        if (geo.properties or {}).get("kind") == "borough"
    }
    cdtas = {
        geo.official_code: geo
        for geo in session.query(GeoUnit).all()
        if (geo.properties or {}).get("kind") == "cdta" and geo.official_code
    }
    written_rows = []
    invalid = 0
    for row in rows:
        geometry = _geojson_text(row.get("the_geom"))
        if geometry is None:
            invalid += 1
            continue
        if kind == "borough":
            name = canonical_borough(row.get("boroname")) or row.get("boroname")
            code = str(row.get("borocode") or "")
            slug = f"borough-{name.lower().replace(' ', '-')}"
            parent_id = city.id if city else None
            level = "district"
            properties = {"kind": "borough", "boro_code": code}
        elif kind == "community_district":
            code = str(row.get("boro_cd") or "")
            boro_digit = code[:1]
            name = f"Community District {code}"
            slug = f"cd-{code}"
            parent = boroughs.get(canonical_borough(boro_digit) or "")
            parent_id = parent.id if parent else (city.id if city else None)
            level = "district"
            joint = len(code) >= 3 and code.endswith("64") or (code.isdigit() and int(code) % 100 >= 64)
            properties = {"kind": "joint_interest_area" if joint else "community_district", "boro_cd": code}
        elif kind == "cdta":
            code = str(row.get("cdta2020") or "")
            name = row.get("cdtaname") or code
            slug = f"cdta-{code.lower()}"
            parent = boroughs.get(canonical_borough(row.get("boroname")) or "")
            parent_id = parent.id if parent else (city.id if city else None)
            level = "district"
            properties = {"kind": "cdta", "cdta_type": row.get("cdtatype")}
        else:
            code = str(row.get("nta2020") or "")
            name = row.get("ntaname") or code
            slug = f"nta-{code.lower()}"
            parent = cdtas.get(str(row.get("cdta2020") or ""))
            parent_id = parent.id if parent else (city.id if city else None)
            level = "neighbourhood"
            properties = {"kind": "nta", "nta_type": row.get("ntatype"), "cdta": row.get("cdta2020")}
        geo = save_geo(
            session,
            {
                "slug": slug,
                "name": name,
                "level_code": level,
                "parent_id": parent_id,
                "official_code": code,
                "country_code": "US",
                "timezone": "America/New_York",
                "properties": properties,
                "integration_status": "integrated",
            },
        )
        _apply_geometry(session, geo, geometry)
        if kind == "borough" and name:
            boroughs[name] = geo
        if kind == "cdta":
            cdtas[code] = geo
        written_rows.append(geo.id)
    quality = [
        {
            "name": "geometry_present",
            "status": "pass" if invalid == 0 else "warn",
            "detail": f"{invalid} rows had no readable geometry." if invalid else "Every returned boundary had geometry.",
            "metrics": {"rows": len(rows), "invalid_geometry": invalid},
        }
    ]
    return written_rows, quality


def connect_boroughs(session: Session, options: dict) -> tuple[int, str, list]:
    rows, quality = _load_boundaries(session, "gthc-hcne", "borough")
    _mark_city(session, "nyc", "partial")
    return len(rows), f"Loaded {len(rows)} borough boundaries.", quality


def connect_community_districts(session: Session, options: dict) -> tuple[int, str, list]:
    rows, quality = _load_boundaries(session, "5crt-au7u", "community_district")
    return len(rows), f"Loaded {len(rows)} community district polygons.", quality


def connect_cdta(session: Session, options: dict) -> tuple[int, str, list]:
    rows, quality = _load_boundaries(session, "xn3r-zk6y", "cdta")
    return len(rows), f"Loaded {len(rows)} CDTA polygons.", quality


def connect_nta(session: Session, options: dict) -> tuple[int, str, list]:
    rows, quality = _load_boundaries(session, "9nt8-h7nd", "nta")
    return len(rows), f"Loaded {len(rows)} NTA polygons.", quality


def connect_atr(session: Session, options: dict) -> tuple[int, str, list]:
    year = int(options.get("year") or datetime.now(NYC).year)
    max_rows = int(options.get("max_rows") or 20000)
    # Sorting this table by month and day times out. An unordered year filter with a row cap stays responsive.
    raw: list[dict] = []
    failed_years: list[str] = []
    for candidate in (year, year - 1):
        try:
            raw = NYC_SODA.fetch(
                "7ym2-wayt",
                {"$where": f"yr='{candidate}'"},
                max_rows=max_rows,
                page_size=1000,
                timeout=45,
            )
        except HttpError:
            failed_years.append(str(candidate))
            raw = []
            continue
        if raw:
            year = candidate
            break
    if not raw:
        raise HttpError("7ym2-wayt", None, f"ATR year queries failed or were empty: {', '.join(failed_years) or year}")
    output = []
    missing_volume = 0
    for row in raw:
        volume = _num(row.get("vol"))
        if volume is None:
            missing_volume += 1
        year_n = int(float(row["yr"]))
        month = int(float(row["m"]))
        day = int(float(row["d"]))
        hour = int(float(row.get("hh") or 0))
        minute = int(float(row.get("mm") or 0))
        observed = datetime(year_n, month, day, hour, minute, tzinfo=NYC)
        geometry = _geojson_text(row.get("wktgeom"))
        latitude = longitude = None
        if geometry:
            center = centroid_latlon(shape(json.loads(geometry)))
            if center:
                latitude, longitude = center
        borough = canonical_borough(row.get("boro"))
        token = f"{row.get('requestid') or ''}|{row.get('segmentid') or ''}|{observed.strftime('%Y%m%d%H%M')}|{row.get('direction') or ''}"
        if len(token) > 120:
            import hashlib

            token = hashlib.sha1(token.encode()).hexdigest()
        output.append(
            {
                "dataset_code": "nyc-atr-counts",
                "city_slug": "nyc",
                "observed_at": observed,
                "borough": borough,
                "segment_id": str(row.get("segmentid") or ""),
                "street": row.get("street"),
                "direction": row.get("direction"),
                "volume": volume,
                "h3_index": h3_cell(latitude, longitude),
                "latitude": latitude,
                "longitude": longitude,
                "geometry_geojson": geometry,
                "source_row_id": token,
                "attributes": {"from": row.get("fromst"), "to": row.get("tost"), "sample_year_filter": year},
            }
        )
    written = insert_new(session, TRAFFIC, output)
    quality = [
        {
            "name": "missing_volume",
            "status": "pass" if missing_volume == 0 else "warn",
            "detail": "Volume is null where the source left it blank. Nulls are not stored as zero.",
            "metrics": {"missing_volume": missing_volume, "fetched": len(raw), "truncated": len(raw) >= max_rows, "failed_years": failed_years},
        }
    ]
    return written, f"Stored {written} new ATR samples for {year}. Extract is partial when the cap is reached.", quality


def _decode_polyline(encoded: str) -> list[list[float]]:
    index = lat = lng = 0
    coordinates = []
    while index < len(encoded):
        shift = result = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lat = ~(result >> 1) if result & 1 else result >> 1
        lat += delta_lat
        shift = result = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lng = ~(result >> 1) if result & 1 else result >> 1
        lng += delta_lng
        coordinates.append([lng / 1e5, lat / 1e5])
    return coordinates


def connect_speeds(session: Session, options: dict) -> tuple[int, str, list]:
    raw = NYC_SODA.fetch("i4gi-tjb9", max_rows=int(options.get("max_rows") or 5000))
    output = []
    for row in raw:
        geometry = None
        latitude = longitude = None
        encoded = row.get("encoded_poly_line")
        if encoded:
            try:
                coordinates = [point for point in _decode_polyline(encoded) if -74.35 <= point[0] <= -73.65 and 40.45 <= point[1] <= 41.05]
                if len(coordinates) >= 2:
                    geometry = json.dumps(mapping(LineString(coordinates)))
                    latitude = coordinates[0][1]
                    longitude = coordinates[0][0]
            except Exception:
                geometry = None
        output.append(
            {
                "dataset_code": "nyc-traffic-speeds",
                "city_slug": "nyc",
                "observed_at": _parse_dt(row.get("data_as_of"), NYC),
                "borough": canonical_borough(row.get("borough")),
                "segment_id": str(row.get("link_id") or row.get("id") or ""),
                "street": row.get("link_name"),
                "speed_mph": _num(row.get("speed")),
                "travel_time_sec": _num(row.get("travel_time")),
                "latitude": latitude,
                "longitude": longitude,
                "geometry_geojson": geometry,
                "h3_index": h3_cell(latitude, longitude),
                "source_row_id": f"{row.get('id')}-{row.get('data_as_of')}",
                "attributes": {"status_raw": row.get("status"), "owner": row.get("owner"), "product": "current_snapshot"},
            }
        )
    written = insert_new(session, TRAFFIC, output)
    observed = [row["observed_at"].isoformat() for row in output if row["observed_at"]]
    stamp = max(observed) if observed else "unknown"
    return written, f"Stored {written} link-speed rows from the snapshot at {stamp}. This is not a historical archive.", [
        {"name": "snapshot_only", "status": "warn", "detail": "DOT publishes the current link snapshot. Earlier speeds are absent unless URBIX archived them.", "metrics": {"rows": len(raw)}}
    ]


def connect_crashes(session: Session, options: dict) -> tuple[int, str, list]:
    start = options.get("start") or (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00")
    raw = NYC_SODA.fetch(
        "h9gi-nx95",
        {
            "$select": "borough, count(1) as crash_count, sum(number_of_persons_injured) as injured, sum(number_of_persons_killed) as killed",
            "$where": f"crash_date >= '{start}'",
            "$group": "borough",
            "$limit": 20,
        },
        max_rows=20,
    )
    output = []
    for row in raw:
        borough = canonical_borough(row.get("borough")) or "Unspecified"
        output.append(
            {
                "dataset_code": "nypd-crashes",
                "city_slug": "nyc",
                "observed_at": _parse_dt(start[:10], NYC),
                "borough": borough,
                "source_row_id": f"{start[:10]}:{borough}",
                "attributes": {
                    "metric": "crash_aggregate",
                    "crash_count": _num(row.get("crash_count")),
                    "persons_injured": _num(row.get("injured")),
                    "persons_killed": _num(row.get("killed")),
                    "window_start": start,
                },
            }
        )
    written = insert_new(session, TRAFFIC, output)
    return written, f"Stored borough crash aggregates since {start[:10]}.", [
        {"name": "aggregate_scope", "status": "pass", "detail": "Server-side borough aggregate of police-reported crashes. Not a traffic volume.", "metrics": {"groups": len(raw)}}
    ]


def normalize_complaint(raw: dict, dataset_code: str = "nypd-complaints-ytd") -> dict:
    """Keep a whitelist. Demographic fields in the source are discarded."""
    latitude = _num(raw.get("latitude"))
    longitude = _num(raw.get("longitude"))
    occurred = _parse_dt(raw.get("cmplnt_fr_dt"), NYC)
    if occurred and raw.get("cmplnt_fr_tm"):
        clock = str(raw["cmplnt_fr_tm"])[:8]
        try:
            hour, minute, second = [int(part) for part in clock.split(":")]
            occurred = occurred.replace(hour=hour, minute=minute, second=second)
        except ValueError:
            pass
    return {
        "dataset_code": dataset_code,
        "city_slug": "nyc",
        "occurred_at": occurred,
        "borough": canonical_borough(raw.get("boro_nm")),
        "precinct": str(raw.get("addr_pct_cd") or "") or None,
        "law_category": raw.get("law_cat_cd"),
        "offense": raw.get("ofns_desc"),
        "latitude": latitude,
        "longitude": longitude,
        "h3_index": h3_cell(latitude, longitude),
        "completeness": "partial_sample",
        "source_row_id": str(raw.get("cmplnt_num")),
    }


def connect_complaints(session: Session, options: dict) -> tuple[int, str, list]:
    grouped = NYC_SODA.fetch(
        "5uac-w243",
        {"$select": "boro_nm, law_cat_cd, count(1) as n", "$group": "boro_nm, law_cat_cd", "$limit": 100},
        max_rows=100,
    )
    aggregates = []
    for row in grouped:
        borough = canonical_borough(row.get("boro_nm")) or "Unspecified"
        category = row.get("law_cat_cd") or "Unspecified"
        aggregates.append(
            {
                "dataset_code": "nypd-complaints-ytd",
                "city_slug": "nyc",
                "period_label": "published year-to-date quarters",
                "borough": borough,
                "category": category,
                "offense": None,
                "incident_count": int(float(row["n"])) if row.get("n") is not None else None,
                "completeness": "complete_aggregate",
                "methodology": "SODA count grouped by borough and law category on the current YTD complaint dataset. This is the complete group for that published extract, not a citywide rate.",
                "source_row_id": f"ytd:{borough}:{category}",
            }
        )
    sample = NYC_SODA.fetch(
        "5uac-w243",
        {
            "$select": "cmplnt_num,cmplnt_fr_dt,cmplnt_fr_tm,law_cat_cd,ofns_desc,boro_nm,addr_pct_cd,latitude,longitude",
            "$where": "latitude IS NOT NULL",
            "$order": "cmplnt_fr_dt DESC",
            "$limit": int(options.get("sample_rows") or 1500),
        },
        max_rows=int(options.get("sample_rows") or 1500),
    )
    points = [normalize_complaint(row) for row in sample if row.get("cmplnt_num")]
    written = insert_new(session, CRIME_AGG, aggregates) + insert_new(session, CRIME_POINT, points)
    return written, "Stored YTD borough/category totals and a partial recent point sample. Hotspot models stay disabled for the partial sample.", [
        {"name": "demographics_excluded", "status": "pass", "detail": "Suspect and victim demographic columns are not requested or stored.", "metrics": {"aggregate_groups": len(aggregates), "point_sample": len(points)}},
        {"name": "point_sample_bias", "status": "warn", "detail": "The point sample is the latest geocoded rows, capped. It is not a spatial census.", "metrics": {"cap": len(points)}},
    ]


def connect_complaint_history(session: Session, options: dict) -> tuple[int, str, list]:
    try:
        grouped = NYC_SODA.fetch(
            "qgea-i56i",
            {
                "$select": "date_trunc_ym(cmplnt_fr_dt) as month, boro_nm, law_cat_cd, count(1) as n",
                "$where": "cmplnt_fr_dt >= '2023-01-01T00:00:00'",
                "$group": "month, boro_nm, law_cat_cd",
                "$limit": 5000,
            },
            max_rows=5000,
        )
    except HttpError as exc:
        return 0, f"Historic monthly aggregation was not stored: {exc}", [
            {"name": "historic_aggregate", "status": "fail", "detail": str(exc), "metrics": {}}
        ]
    output = []
    for row in grouped:
        borough = canonical_borough(row.get("boro_nm")) or "Unspecified"
        category = row.get("law_cat_cd") or "Unspecified"
        month = str(row.get("month") or "")
        output.append(
            {
                "dataset_code": "nypd-complaints-historic",
                "city_slug": "nyc",
                "period_label": month,
                "borough": borough,
                "category": category,
                "incident_count": int(float(row["n"])) if row.get("n") is not None else None,
                "completeness": "complete_aggregate",
                "methodology": "Server-side monthly counts from the historic complaint dataset for 2023 onward. Reporting and enforcement bias remain.",
                "source_row_id": f"{month}:{borough}:{category}",
            }
        )
    written = insert_new(session, CRIME_AGG, output)
    return written, f"Stored {written} historic monthly complaint aggregates.", [
        {"name": "historic_aggregate", "status": "pass", "detail": "Counts only. No person-level fields.", "metrics": {"groups": len(output)}}
    ]


def connect_air_quality(session: Session, options: dict) -> tuple[int, str, list]:
    raw = NYC_SODA.fetch("c3uy-2p5r", {"$order": "start_date DESC"}, max_rows=int(options.get("max_rows") or 8000))
    output = []
    blank = 0
    for row in raw:
        value = _num(row.get("data_value"))
        if value is None:
            blank += 1
        output.append(
            {
                "dataset_code": "nyc-air-quality",
                "city_slug": "nyc",
                "observed_at": _parse_dt(row.get("start_date"), NYC),
                "parameter": row.get("name") or "unspecified",
                "value": value,
                "unit": row.get("measure_info"),
                "aggregation": row.get("measure"),
                "methodology": "DOHMH air-quality surveillance indicator. Neighbourhood values are modelled estimates for the named geography and period, not a monitor hour.",
                "place_name": row.get("geo_place_name"),
                "source_row_id": str(row.get("unique_id") or f"{row.get('indicator_id')}-{row.get('geo_join_id')}-{row.get('time_period')}"),
                "attributes": {
                    "geo_type": row.get("geo_type_name"),
                    "geo_join_id": row.get("geo_join_id"),
                    "time_period": row.get("time_period"),
                    "message": row.get("message"),
                },
            }
        )
    written = insert_new(session, ENVIRONMENT, output)
    return written, f"Stored {written} DOHMH air-quality indicator rows. Blank measurements stayed null.", [
        {"name": "null_measurements", "status": "pass" if blank == 0 else "warn", "detail": "Null data_value was preserved.", "metrics": {"nulls": blank, "fetched": len(raw)}}
    ]


def _open_meteo_rows(session: Session, dataset_code: str, base_url: str, variables: list[str], options: dict) -> tuple[int, str, list]:
    days = int(options.get("days") or 7)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    cities = options.get("cities") or reference_city_slugs()
    targets = []
    for slug in cities:
        city = get_geo(session, slug)
        if city and city.latitude is not None:
            targets.append(city)
        if slug == "nyc":
            boroughs = session.query(GeoUnit).filter(GeoUnit.slug.like("borough-%")).all()
            targets.extend(boroughs)
    if not targets:
        raise RuntimeError("No city coordinates are available. Seed geography first.")
    output_model = WEATHER if dataset_code == "open-meteo-weather" else ENVIRONMENT
    rows = []
    touched: set[str] = set()
    errors: list[str] = []
    for geo in targets:
        try:
            payload = request_json(
                base_url,
                params={
                    "latitude": geo.latitude,
                    "longitude": geo.longitude,
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "hourly": ",".join(variables),
                    "timezone": geo.timezone or "UTC",
                },
                timeout=60,
            )
        except Exception as exc:
            errors.append(f"{geo.slug}: {exc}")
            continue
        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        if not times:
            errors.append(f"{geo.slug}: the archive returned no hours")
            continue
        cell_lat = payload.get("latitude")
        cell_lon = payload.get("longitude")
        for variable in variables:
            values = hourly.get(variable) or []
            unit = (payload.get("hourly_units") or {}).get(variable)
            for index, moment in enumerate(times):
                value = values[index] if index < len(values) else None
                observed = _parse_dt(moment, ZoneInfo(geo.timezone or "UTC"))
                row = {
                    "dataset_code": dataset_code,
                    "city_slug": geo.slug if geo.level_code == "city" else "nyc",
                    "geo_unit_id": geo.id,
                    "observed_at": observed,
                    "parameter": variable,
                    "value": _num(value),
                    "unit": unit,
                    "latitude": cell_lat,
                    "longitude": cell_lon,
                    "source_row_id": f"{geo.slug}:{variable}:{moment}",
                }
                if dataset_code == "open-meteo-weather":
                    row["methodology"] = (
                        "Open-Meteo archive grid cell selected for this geography's coordinate. "
                        "Not a mean across the polygon."
                    )
                else:
                    row["methodology"] = (
                        "Open-Meteo / CAMS air-quality model grid. Not a regulatory monitor and "
                        "not a DOHMH neighbourhood estimate."
                    )
                    row["aggregation"] = "model_hour"
                    row["place_name"] = geo.name
                    row["attributes"] = {"requested_latitude": geo.latitude, "requested_longitude": geo.longitude}
                rows.append(row)
        touched.add(geo.slug if geo.level_code == "city" else "nyc")
    if not rows and errors:
        raise RuntimeError("Open-Meteo returned no hours. " + "; ".join(errors[:4]))
    written = insert_new(session, output_model, rows)
    for slug in touched:
        _mark_city(session, slug, "partial")
    message = f"Stored {written} {dataset_code} rows for {len(touched)} places from {start} to {end}."
    if errors:
        message += " Skipped " + "; ".join(errors[:4]) + "."
    return written, message, [
        {"name": "grid_cell", "status": "pass" if not errors else "warn", "detail": "Stored the API grid coordinate separately from the requested coordinate.", "metrics": {"locations": len(touched), "days": days, "skipped": len(errors)}}
    ]


def connect_weather(session: Session, options: dict) -> tuple[int, str, list]:
    return _open_meteo_rows(
        session,
        "open-meteo-weather",
        "https://archive-api.open-meteo.com/v1/archive",
        ["temperature_2m", "relative_humidity_2m", "precipitation", "wind_speed_10m"],
        options,
    )


def connect_model_air(session: Session, options: dict) -> tuple[int, str, list]:
    return _open_meteo_rows(
        session,
        "open-meteo-air-quality",
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        ["pm2_5", "pm10", "nitrogen_dioxide", "carbon_monoxide"],
        options,
    )


def connect_openaq(session: Session, options: dict) -> tuple[int, str, list]:
    import os

    key = os.environ.get("OPENAQ_API_KEY")
    if not key:
        raise RuntimeError("OPENAQ_API_KEY is not set. Station measurements were not requested.")
    payload = request_json(
        "https://api.openaq.org/v3/locations",
        params={"bbox": "-74.26,40.49,-73.70,40.92", "limit": 100},
        headers={"X-API-Key": key},
    )
    results = payload.get("results") or []
    rows = []
    for location in results:
        coordinates = location.get("coordinates") or {}
        rows.append(
            {
                "dataset_code": "openaq-locations",
                "city_slug": "nyc",
                "observed_at": None,
                "parameter": "station",
                "value": None,
                "unit": None,
                "aggregation": "location",
                "methodology": "OpenAQ location metadata. Measurement values are loaded per sensor only when a key is present; this row is the station, not a concentration.",
                "place_name": location.get("name"),
                "latitude": coordinates.get("latitude"),
                "longitude": coordinates.get("longitude"),
                "source_row_id": f"location:{location.get('id')}",
                "attributes": {"licenses": location.get("licenses"), "provider": (location.get("provider") or {}).get("name")},
            }
        )
    written = insert_new(session, ENVIRONMENT, rows)
    return written, f"Stored {written} OpenAQ location records. Licenses stay on the row.", [
        {"name": "license_captured", "status": "pass", "detail": "Location license metadata was stored with the station.", "metrics": {"locations": len(results)}}
    ]


def _waste_month(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace(" / ", "-").replace("/", "-")
    parsed = _parse_dt(text, NYC)
    return parsed


def connect_waste(session: Session, options: dict) -> tuple[int, str, list]:
    raw = NYC_SODA.fetch("ebb7-mvp5", {"$order": "month DESC"}, max_rows=int(options.get("max_rows") or 8000))
    output = []
    for row in raw:
        organics = sum(value for value in [_num(row.get(key)) for key in ("resorganicstons", "schoolorganictons", "leavesorganictons", "otherorganicstons")] if value is not None)
        organics_value = organics if any(row.get(key) not in (None, "") for key in ("resorganicstons", "schoolorganictons", "leavesorganictons", "otherorganicstons")) else None
        month = _waste_month(row.get("month"))
        borough = canonical_borough(row.get("borough"))
        district = str(row.get("communitydistrict") or "")
        output.append(
            {
                "dataset_code": "nyc-waste-tonnage",
                "city_slug": "nyc",
                "period_start": month,
                "borough": borough,
                "district_code": district,
                "refuse_tons": _num(row.get("refusetonscollected")),
                "paper_tons": _num(row.get("papertonscollected")),
                "mgp_tons": _num(row.get("mgptonscollected")),
                "organics_tons": organics_value,
                "source_row_id": f"{row.get('month')}:{borough}:{district}",
                "attributes": {"xmastree_tons": _num(row.get("xmastreetons"))},
            }
        )
    written = insert_new(session, WASTE, output)
    repaired = 0
    for existing in session.query(WASTE).filter(WASTE.dataset_code == "nyc-waste-tonnage", WASTE.period_start.is_(None)):
        parsed = _waste_month((existing.source_row_id or "").split(":")[0])
        if parsed is None:
            continue
        existing.period_start = parsed
        repaired += 1
    return written, f"Stored {written} DSNY monthly tonnage rows. Parsed {repaired} previously undated rows.", [
        {"name": "scope", "status": "pass", "detail": "Residential and institutional DSNY tonnage. No collection schedule was inferred.", "metrics": {"rows": len(raw), "periods_repaired": repaired}}
    ]


def connect_population(session: Session, options: dict) -> tuple[int, str, list]:
    raw = NYC_SODA.fetch("xi7c-iiu2", max_rows=500)
    output = []
    for row in raw:
        borough = canonical_borough(row.get("borough"))
        code = str(row.get("cd_number") or "")
        for year, column in ((1970, "_1970_population"), (1980, "_1980_population"), (1990, "_1990_population"), (2000, "_2000_population"), (2010, "_2010_population")):
            output.append(
                {
                    "dataset_code": "nyc-population-cd-decennial",
                    "city_slug": "nyc",
                    "place_name": row.get("cd_name") or f"{borough} {code}",
                    "place_code": code,
                    "vintage_year": year,
                    "population": _num(row.get(column)),
                    "metric_kind": "decennial_count",
                    "methodology": "DCP compilation of Census decennial counts by community district. The latest year in this table is 2010. It is not mapped onto current boundaries.",
                    "source_row_id": f"{code}:{year}",
                }
            )
    written = insert_new(session, POPULATION, output)
    census_note = "ACS borough estimates were not requested in this run."
    if options.get("include_acs", True):
        try:
            acs_rows, acs_note = _census_boroughs()
            written += insert_new(session, POPULATION, acs_rows)
            census_note = acs_note
        except Exception as exc:
            census_note = f"ACS borough estimates were not stored: {exc}"
    return written, f"Stored {written} population rows. {census_note}", [
        {"name": "vintage", "status": "warn", "detail": "Decennial district counts stop at 2010. ACS is stored only when the Census API responds, and only at borough level.", "metrics": {}}
    ]


def _census_boroughs() -> tuple[list[dict], str]:
    import os

    params = {"get": "NAME,B01003_001E", "for": "county:005,047,061,081,085", "in": "state:36"}
    key = os.environ.get("CENSUS_API_KEY")
    if key:
        params["key"] = key
    payload = None
    used_year = None
    for year in ("2023", "2022", "2021"):
        try:
            payload = request_json(f"https://api.census.gov/data/{year}/acs/acs5", params=params, timeout=40)
            used_year = year
            break
        except HttpError:
            continue
    if not payload or not used_year:
        raise RuntimeError("Census ACS API did not return a borough table.")
    header = payload[0]
    name_i = header.index("NAME")
    value_i = header.index("B01003_001E")
    county_i = header.index("county")
    rows = []
    for item in payload[1:]:
        county = item[county_i]
        borough = COUNTY_TO_BOROUGH.get(county)
        rows.append(
            {
                "dataset_code": "census-acs5-borough",
                "city_slug": "nyc",
                "place_name": borough or item[name_i],
                "place_code": county,
                "vintage_year": int(used_year),
                "population": _num(item[value_i]),
                "metric_kind": "acs5_estimate",
                "methodology": f"ACS 5-year table B01003 total population for NYC counties, release {used_year}. This is a survey estimate for the five-year window, not a point-in-time count, and it is borough-level only.",
                "source_row_id": f"acs5:{used_year}:{county}",
            }
        )
    return rows, f"ACS 5-year release {used_year} returned {len(rows)} borough estimates."


def connect_gtfs(session: Session, options: dict) -> tuple[int, str, list]:
    blob = request_bytes("https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip", timeout=120)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        stops = list(csv.DictReader(io.TextIOWrapper(archive.open("stops.txt"), encoding="utf-8-sig")))
        routes = list(csv.DictReader(io.TextIOWrapper(archive.open("routes.txt"), encoding="utf-8-sig")))
        trips = list(csv.DictReader(io.TextIOWrapper(archive.open("trips.txt"), encoding="utf-8-sig")))
    trip_counts: dict[str, int] = {}
    for trip in trips:
        trip_counts[trip.get("route_id") or ""] = trip_counts.get(trip.get("route_id") or "", 0) + 1
    stop_rows = []
    for stop in stops:
        if stop.get("location_type") not in (None, "", "0", "1"):
            continue
        latitude = _num(stop.get("stop_lat"))
        longitude = _num(stop.get("stop_lon"))
        stop_rows.append(
            {
                "dataset_code": "mta-subway-gtfs",
                "city_slug": "nyc",
                "stop_id": stop.get("stop_id") or "",
                "name": stop.get("stop_name") or stop.get("stop_id") or "stop",
                "latitude": latitude,
                "longitude": longitude,
                "location_type": stop.get("location_type") or "0",
                "route_ids": None,
            }
        )
    written = insert_new(session, STOPS, stop_rows, key="stop_id")
    route_rows = []
    for route in routes:
        route_id = route.get("route_id") or ""
        route_rows.append(
            {
                "dataset_code": "mta-subway-gtfs",
                "city_slug": "nyc",
                "feature_type": "scheduled_route_trips",
                "name": route.get("route_short_name") or route_id,
                "value": float(trip_counts.get(route_id, 0)),
                "unit": "scheduled_trips_in_feed",
                "methodology": "Count of trips in the regular subway GTFS file. This is a schedule edition, not observed service.",
                "source_row_id": f"route:{route_id}",
                "attributes": {"route_id": route_id, "long_name": route.get("route_long_name")},
            }
        )
    written += insert_new(session, INFRA, route_rows)
    return written, f"Stored {len(stop_rows)} subway stops and {len(route_rows)} route trip counts from static GTFS.", [
        {"name": "schedule_not_observed", "status": "warn", "detail": "GTFS trip counts are scheduled trips in the regular feed.", "metrics": {"stops": len(stop_rows), "routes": len(route_rows)}}
    ]


def connect_ridership(session: Session, options: dict) -> tuple[int, str, list]:
    window_start = options.get("start") or "2026-10-27T00:00:00"
    window_end = options.get("end") or "2026-10-29T23:00:00"
    raw = NY_SODA.fetch(
        "5wq4-mkjj",
        {
            "$select": "transit_timestamp, borough, station_complex_id, station_complex, sum(ridership) as riders, sum(transfers) as transfers, max(latitude) as latitude, max(longitude) as longitude",
            "$where": f"transit_timestamp between '{window_start}' and '{window_end}'",
            "$group": "transit_timestamp, borough, station_complex_id, station_complex",
            "$limit": 50000,
        },
        max_rows=int(options.get("max_rows") or 20000),
    )
    output = []
    for row in raw:
        stamp = row.get("transit_timestamp")
        output.append(
            {
                "dataset_code": "mta-subway-ridership",
                "city_slug": "nyc",
                "observed_at": _parse_dt(stamp, NYC),
                "borough": canonical_borough(row.get("borough")),
                "station_complex_id": str(row.get("station_complex_id") or ""),
                "station_name": row.get("station_complex"),
                "riders": _num(row.get("riders")),
                "transfers": _num(row.get("transfers")),
                "latitude": _num(row.get("latitude")),
                "longitude": _num(row.get("longitude")),
                "aggregation": "station_hour_summed_fare_classes",
                "source_row_id": f"{stamp}:{row.get('station_complex_id')}",
            }
        )
    written = insert_new(session, RIDERS, output)
    return written, f"Stored {written} station-hour ridership sums for {window_start} to {window_end}. Full history was not downloaded.", [
        {"name": "window", "status": "warn", "detail": "The source has tens of millions of rows. This extract is a short window of summed fare classes.", "metrics": {"rows": len(raw)}}
    ]


def connect_pluto(session: Session, options: dict) -> tuple[int, str, list]:
    raw = NYC_SODA.fetch(
        "64uk-42ks",
        {
            "$select": "borough, cd, count(1) as lots, sum(unitsres) as residential_units",
            "$group": "borough, cd",
            "$limit": 200,
        },
        max_rows=200,
    )
    output = []
    for row in raw:
        borough = canonical_borough(row.get("borough"))
        district = str(row.get("cd") or "")
        output.append(
            {
                "dataset_code": "nyc-pluto-aggregates",
                "city_slug": "nyc",
                "feature_type": "pluto_lot_aggregate",
                "name": f"{borough} CD {district}",
                "borough": borough,
                "district_code": district,
                "value": _num(row.get("lots")),
                "unit": "tax_lots",
                "methodology": "SODA aggregation of the current PLUTO extract. residential_units is the summed PLUTO unitsres field, not a population count. Lot polygons were not downloaded.",
                "source_row_id": f"{borough}:{district}",
                "attributes": {"residential_units": _num(row.get("residential_units"))},
            }
        )
    written = insert_new(session, INFRA, output)
    return written, f"Stored {written} PLUTO borough/community-district aggregates.", [
        {"name": "not_population", "status": "pass", "detail": "Residential units remain in attributes and are not written to population_observations.", "metrics": {"groups": len(raw)}}
    ]


def connect_shelters(session: Session, options: dict) -> tuple[int, str, list]:
    raw = NYC_SODA.fetch("3qem-6v3v", {"$order": "report_date DESC"}, max_rows=2000)
    if not raw:
        return 0, "Shelter dataset returned no rows.", [{"name": "rows", "status": "warn", "detail": "No rows.", "metrics": {}}]
    latest = max(row.get("report_date") or "" for row in raw)
    output = []
    fields = ["adult_family_comm_hotel", "adult_family_shelter", "adult_shelter", "adult_shelter_comm_hotel", "fwc_cluster", "fwc_comm_hotel", "fwc_shelter"]
    for row in raw:
        if row.get("report_date") != latest:
            continue
        parts = {field: _num(row.get(field)) for field in fields}
        present = [value for value in parts.values() if value is not None]
        output.append(
            {
                "dataset_code": "nyc-shelter-buildings",
                "city_slug": "nyc",
                "feature_type": "shelter_buildings",
                "name": f"{row.get('borough')} CD {row.get('community_district')}",
                "borough": canonical_borough(row.get("borough")),
                "district_code": str(row.get("community_district") or ""),
                "value": sum(present) if present else None,
                "unit": "shelter_buildings",
                "methodology": f"Sum of shelter-building categories on the DSNY/DHS report dated {latest}. This is not the citywide building stock.",
                "source_row_id": f"{latest}:{row.get('borough')}:{row.get('community_district')}",
                "attributes": parts,
            }
        )
    written = insert_new(session, INFRA, output)
    return written, f"Stored {written} shelter-building district rows for {latest}.", [
        {"name": "not_building_stock", "status": "pass", "detail": "Feature type is shelter_buildings.", "metrics": {"report_date": latest}}
    ]


def connect_roads(session: Session, options: dict) -> tuple[int, str, list]:
    query = """
    [out:json][timeout:40];
    way["highway"~"^(motorway|trunk)$"](40.50,-74.26,40.92,-73.70);
    out geom 80;
    """
    payload = request_json("https://overpass-api.de/api/interpreter", data=query.encode("utf-8"), timeout=70)
    elements = payload.get("elements") or []
    output = []
    for element in elements:
        geometry = element.get("geometry") or []
        coordinates = [[node["lon"], node["lat"]] for node in geometry if "lon" in node and "lat" in node]
        geojson = json.dumps(mapping(LineString(coordinates))) if len(coordinates) >= 2 else None
        tags = element.get("tags") or {}
        output.append(
            {
                "dataset_code": "osm-major-roads",
                "city_slug": "nyc",
                "feature_type": "major_road",
                "name": tags.get("name") or tags.get("ref") or f"way {element.get('id')}",
                "value": None,
                "unit": None,
                "methodology": "OpenStreetMap motorway and trunk ways inside the NYC bounding box, via Overpass. © OpenStreetMap contributors.",
                "geometry_geojson": geojson,
                "source_row_id": str(element.get("id")),
                "attributes": {"highway": tags.get("highway"), "ref": tags.get("ref")},
            }
        )
    written = insert_new(session, INFRA, output)
    return written, f"Stored {written} OSM motorway/trunk ways. The local street network was not requested.", [
        {"name": "coverage", "status": "warn", "detail": "Motorway and trunk only, and the Overpass query caps geometry output.", "metrics": {"ways": len(elements)}}
    ]


def connect_city_boundary(session: Session, options: dict) -> tuple[int, str, list]:
    slug = options.get("city") or "singapore"
    city = get_geo(session, slug)
    if city is None or city.latitude is None or city.longitude is None:
        raise RuntimeError(f"Unknown city {slug}")
    params = {
        "q": city.name,
        "format": "jsonv2",
        "polygon_geojson": 1,
        "polygon_threshold": 0.01,
        "limit": 5,
    }
    if city.country_code:
        params["countrycodes"] = city.country_code.lower()
    payload = request_json("https://nominatim.openstreetmap.org/search", params=params, timeout=40)
    chosen = None
    for item in payload or []:
        geojson = item.get("geojson") or {}
        if geojson.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        center = centroid_latlon(shape(geojson))
        if center is None:
            continue
        if abs(center[0] - city.latitude) > 1.5 or abs(center[1] - city.longitude) > 1.5:
            continue
        chosen = item
        break
    if chosen is None:
        raise RuntimeError(f"Nominatim returned no city polygon near the reference point for {city.name}.")
    _apply_geometry(session, city, json.dumps(chosen["geojson"]))
    if city.integration_status != "integrated":
        city.integration_status = "partial"
    properties = dict(city.properties or {})
    properties["boundary_source"] = "OpenStreetMap via Nominatim"
    properties["osm_id"] = chosen.get("osm_id")
    city.properties = properties
    return 1, f"Attached an OpenStreetMap boundary for {city.name}.", [
        {"name": "osm_boundary", "status": "pass", "detail": "Boundary came from Nominatim polygon_geojson and was kept only when its centroid stayed near the reference point. © OpenStreetMap contributors.", "metrics": {"osm_id": chosen.get("osm_id")}}
    ]


CONNECTORS = {
    "nyc-borough-boundaries": connect_boroughs,
    "nyc-community-districts": connect_community_districts,
    "nyc-cdta-2020": connect_cdta,
    "nyc-nta-2020": connect_nta,
    "nyc-atr-counts": connect_atr,
    "nyc-traffic-speeds": connect_speeds,
    "nypd-crashes": connect_crashes,
    "nypd-complaints-ytd": connect_complaints,
    "nypd-complaints-historic": connect_complaint_history,
    "nyc-air-quality": connect_air_quality,
    "open-meteo-weather": connect_weather,
    "open-meteo-air-quality": connect_model_air,
    "openaq-locations": connect_openaq,
    "nyc-waste-tonnage": connect_waste,
    "nyc-population-cd-decennial": connect_population,
    "mta-subway-gtfs": connect_gtfs,
    "mta-subway-ridership": connect_ridership,
    "nyc-pluto-aggregates": connect_pluto,
    "nyc-shelter-buildings": connect_shelters,
    "osm-major-roads": connect_roads,
    "osm-city-boundary": connect_city_boundary,
}

REFERENCE_SEQUENCE = [
    "nyc-borough-boundaries",
    "nyc-community-districts",
    "nyc-cdta-2020",
    "nyc-nta-2020",
    "nyc-atr-counts",
    "nyc-traffic-speeds",
    "nypd-crashes",
    "nypd-complaints-ytd",
    "nyc-air-quality",
    "nyc-waste-tonnage",
    "nyc-population-cd-decennial",
    "open-meteo-weather",
    "open-meteo-air-quality",
    "mta-subway-gtfs",
    "mta-subway-ridership",
    "nyc-pluto-aggregates",
    "nyc-shelter-buildings",
    "osm-major-roads",
]
