"""Geospatial helpers used by ingestion and the API.

Shapely performs the portable operations. When the database is PostgreSQL,
sync_postgis_geometries copies GeoJSON into the PostGIS geometry columns
created by database/migrations/001_postgis.sql.
"""

from __future__ import annotations

import json
from typing import Any

from shapely.geometry import Point, mapping, shape
from shapely.ops import unary_union
from sqlalchemy import text
from sqlalchemy.engine import Engine


def as_shape(geojson_value: str | dict | None):
    if not geojson_value:
        return None
    data = json.loads(geojson_value) if isinstance(geojson_value, str) else geojson_value
    if not data:
        return None
    return shape(data)


def geometry_area_km2(geom) -> float | None:
    if geom is None or geom.is_empty:
        return None
    try:
        from pyproj import Geod

        geod = Geod(ellps="WGS84")
        area, _perimeter = geod.geometry_area_perimeter(geom)
        return abs(float(area)) / 1_000_000.0
    except Exception:
        return None


def centroid_latlon(geom) -> tuple[float, float] | None:
    if geom is None or geom.is_empty:
        return None
    point = geom.centroid
    return float(point.y), float(point.x)


def point_in_features(latitude: float, longitude: float, features: list[dict]) -> dict | None:
    point = Point(longitude, latitude)
    for feature in features:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        try:
            polygon = shape(geometry)
        except Exception:
            continue
        if polygon.contains(point) or polygon.touches(point):
            return feature
    return None


def nearest_feature(latitude: float, longitude: float, points: list[dict]) -> dict | None:
    if not points:
        return None
    origin = Point(longitude, latitude)
    best = None
    best_distance = None
    for item in points:
        lat = item.get("latitude")
        lon = item.get("longitude")
        if lat is None or lon is None:
            continue
        distance = origin.distance(Point(float(lon), float(lat)))
        if best_distance is None or distance < best_distance:
            best = item
            best_distance = distance
    return best


def h3_cell(latitude: float | None, longitude: float | None, resolution: int = 8) -> str | None:
    if latitude is None or longitude is None:
        return None
    try:
        import h3

        return h3.latlng_to_cell(float(latitude), float(longitude), resolution)
    except Exception:
        return None


def feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def dump_geometry(geom) -> str:
    return json.dumps(mapping(geom))


def union_bounds(geometries: list[Any]) -> tuple[float, float, float, float] | None:
    valid = [geom for geom in geometries if geom is not None and not geom.is_empty]
    if not valid:
        return None
    merged = unary_union(valid)
    minx, miny, maxx, maxy = merged.bounds
    return minx, miny, maxx, maxy


def sync_postgis_geometries(engine: Engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    statements = [
        """
        UPDATE geo_units
        SET geom = ST_SetSRID(ST_GeomFromGeoJSON(boundary_geojson), 4326)
        WHERE boundary_geojson IS NOT NULL AND geom IS NULL
        """,
        """
        UPDATE traffic_observations
        SET geom = ST_SetSRID(ST_GeomFromGeoJSON(geometry_geojson), 4326)
        WHERE geometry_geojson IS NOT NULL AND geom IS NULL
        """,
        """
        UPDATE environmental_observations
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND geom IS NULL
        """,
        """
        UPDATE crime_incidents
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND geom IS NULL
        """,
        """
        UPDATE transit_stops
        SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND geom IS NULL
        """,
        """
        UPDATE infrastructure_features
        SET geom = ST_SetSRID(ST_GeomFromGeoJSON(geometry_geojson), 4326)
        WHERE geometry_geojson IS NOT NULL AND geom IS NULL
        """,
        """
        UPDATE knowledge_documents
        SET search_vector = to_tsvector('english', coalesce(title, '') || ' ' || coalesce(body, ''))
        WHERE search_vector IS NULL
        """,
    ]
    with engine.begin() as connection:
        for statement in statements:
            try:
                connection.execute(text(statement))
            except Exception:
                continue
