from __future__ import annotations

import argparse

from urbix_data.pipeline import REFERENCE_SEQUENCE, WEATHER_CITIES, run_connector, seed_reference_geography
from urbix_data.reference import reference_city_slugs
from urbix_data.repository import upsert_catalog
from urbix_db.session import init_db, make_engine, make_session_factory
from urbix_db.spatial import sync_postgis_geometries


def bootstrap(sequence: list[str] | None = None, weather_cities: list[str] | None = None) -> list[dict]:
    engine = make_engine()
    init_db(engine)
    factory = make_session_factory(engine)
    session = factory()
    results = []
    try:
        upsert_catalog(session)
        seed_reference_geography(session)
        session.commit()
        for code in sequence or REFERENCE_SEQUENCE:
            options = {}
            if code in {"open-meteo-weather", "open-meteo-air-quality"}:
                options["cities"] = weather_cities or WEATHER_CITIES
                options["days"] = 21
            if code == "nyc-atr-counts":
                options["max_rows"] = 8000
            outcome = run_connector(session, code, options)
            session.commit()
            results.append(outcome)
            print(f"{outcome['status']:10} {code:32} {outcome['message']}")
        sync_postgis_geometries(engine)
        session.commit()
    finally:
        session.close()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Load verified URBIX reference data.")
    parser.add_argument("--only", action="append", default=[], help="Run one connector code. Repeatable.")
    parser.add_argument("--expand-weather", action="store_true", help="Also request weather for expansion cities.")
    args = parser.parse_args()
    cities = reference_city_slugs() if args.expand_weather else WEATHER_CITIES
    bootstrap(args.only or None, cities)


if __name__ == "__main__":
    main()
