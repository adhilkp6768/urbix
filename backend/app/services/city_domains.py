from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median

from sqlalchemy.orm import Session

from urbix_db.models import (
    CrimeAggregate,
    EnvironmentalObservation,
    GeoUnit,
    InfrastructureFeature,
    PopulationObservation,
    TrafficObservation,
    TransitStop,
    WeatherObservation,
)

AIR_DATASETS = ["sg-nea-pm25", "london-laqn-index", "uba-air-quality", "ams-luchtmeetnet", "madrid-air-quality"]
POPULATION_DATASETS = [
    "sg-singstat-population",
    "london-ons-mye",
    "ams-bbga-population",
    "eurostat-city-population",
    "chicago-population-counts",
    "chicago-acs-community",
    "toronto-neighbourhood-profiles",
]
CRIME_DATASETS = [
    "london-mps-borough-crime",
    "ams-cbs-crime",
    "sg-spf-major-offences",
    "chicago-crime-monthly",
    "la-crime-monthly",
    "toronto-reported-crime",
]
TRAFFIC_DATASETS = ["london-dft-aadf", "chicago-traffic-crashes", "la-traffic-collisions", "toronto-traffic-collisions"]
CRASH_TRAFFIC_DATASETS = {"chicago-traffic-crashes", "la-traffic-collisions", "toronto-traffic-collisions"}
HEADLINE_PARAMETERS = ["pm25", "daqi_pm25", "no2", "daqi_no2", "pm10", "daqi_pm10"]
PARAMETER_LABELS = {
    "pm25": "PM2.5",
    "pm10": "PM10",
    "no2": "NO2",
    "o3": "O3",
    "so2": "SO2",
    "co": "CO",
    "daqi_pm25": "PM2.5 index",
    "daqi_pm10": "PM10 index",
    "daqi_no2": "NO2 index",
    "daqi_o3": "O3 index",
    "daqi_so2": "SO2 index",
}
ROAD_CATEGORIES = {
    "TM": "Trunk motorway",
    "PM": "Principal motorway",
    "TA": "Trunk A road",
    "PA": "Principal A road",
    "MB": "Minor B road",
    "MCU": "Minor C or unclassified",
}
NOT_CONNECTED = {
    "traffic": {
        "singapore": "LTA DataMall speed bands and traffic counts require an account key, which is not configured. No speed or volume figure is shown.",
        "amsterdam": "NDW national traffic data is not connected yet. No speed or volume figure is shown.",
        "berlin": "The Berlin traffic detection feed (Verkehrsdetektion) is not connected yet. No speed or volume figure is shown.",
        "trier": "No open traffic count feed for Trier has been verified.",
        "paris": "No verified open Paris traffic-count feed is connected yet.",
        "madrid": "No verified open Madrid traffic-count feed is connected yet.",
        "rome": "No verified open Rome traffic-count feed is connected yet.",
        "stockholm": "No verified open Stockholm traffic-count feed is connected yet.",
    },
    "crime": {
        "berlin": "Berlin's district crime atlas (Kriminalitätsatlas) is published as a spreadsheet without a stable API, so it is not loaded.",
        "trier": "Polizeiliche Kriminalstatistik city figures for Trier are not available through a verified open API.",
        "paris": "No verified open Paris crime aggregate API is connected yet.",
        "madrid": "No verified open Madrid crime aggregate API is connected yet.",
        "rome": "No verified open Rome crime aggregate API is connected yet.",
        "stockholm": "No verified open Stockholm crime aggregate API is connected yet.",
    },
    "waste": "No verified open municipal waste tonnage feed is connected for this city. Waste is shown as unavailable, not zero.",
}


def _round(value, digits: int = 1):
    if value is None:
        return None
    return round(float(value), digits)


def _kpi(label, value, unit, dataset_code, methodology, period=None):
    return {
        "label": label,
        "value": _round(value) if isinstance(value, float) else value,
        "unit": unit,
        "dataset_code": dataset_code,
        "methodology": methodology,
        "period": period,
        "availability": "available" if value is not None else "unavailable",
    }


def _card(session: Session, code: str):
    from app.services.query import source_card

    return source_card(session, code)


def _cards(session: Session, codes) -> list[dict]:
    return [card for card in (_card(session, code) for code in dict.fromkeys(codes)) if card]


def _city(session: Session, slug: str) -> GeoUnit | None:
    return session.query(GeoUnit).filter(GeoUnit.slug == slug).one_or_none()


def _districts(session: Session, city: GeoUnit) -> list[GeoUnit]:
    return [row for row in session.query(GeoUnit).filter(GeoUnit.parent_id == city.id).all() if (row.properties or {}).get("kind") == "district"]


SERIES_BREAKS = {"eurostat-city-population": 2024}


def _area(session: Session, city: GeoUnit) -> tuple[float | None, str]:
    rows = _districts(session, city)
    official = [row for row in rows if row.area_km2 and not ((row.properties or {}).get("district_type") or "").endswith("_osm")]
    if official and len(official) == len(rows):
        source = (official[0].properties or {}).get("source") or "the official district layer"
        return sum(row.area_km2 for row in official), f"the official district polygons ({source})"
    return city.area_km2, f"the city boundary from {(city.properties or {}).get('boundary_source') or 'the registry'}"


def _unavailable(reason: str, sources: list | None = None) -> dict:
    return {"availability": "unavailable", "kpis": [], "rankings": [], "series": [], "series_label": "", "sources": sources or [], "limitations": [reason], "reason": reason}


def _drop_incomplete_tail(rows: list, value_attr: str = "volume") -> list:
    """Drop a trailing period that is clearly still filling in (common for open SODA feeds)."""
    if len(rows) < 2:
        return list(rows)
    trimmed = list(rows)
    now = datetime.now(timezone.utc)
    while len(trimmed) >= 2:
        attrs = trimmed[-1].attributes or {}
        # Annual series for the current calendar year are almost always year-to-date.
        if attrs.get("month") is None and attrs.get("year") == now.year:
            trimmed.pop()
            continue
        latest = getattr(trimmed[-1], value_attr, None)
        previous = getattr(trimmed[-2], value_attr, None)
        if latest is None or previous in (None, 0):
            break
        threshold = 0.75 if attrs.get("month") is None else 0.4
        if latest < threshold * previous:
            trimmed.pop()
            continue
        break
    return trimmed


def _line_km(geometry: dict) -> float:
    coords = geometry.get("coordinates") or []
    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:]):
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp, dl = p2 - p1, math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        total += 2 * 6371.0088 * math.asin(math.sqrt(a))
    return total


def latest_station_values(session: Session, slug: str) -> tuple[str | None, list[EnvironmentalObservation]]:
    rows = (
        session.query(EnvironmentalObservation)
        .filter(EnvironmentalObservation.city_slug == slug, EnvironmentalObservation.dataset_code.in_(AIR_DATASETS), EnvironmentalObservation.value.isnot(None))
        .all()
    )
    present = {row.parameter for row in rows}
    headline = next((parameter for parameter in HEADLINE_PARAMETERS if parameter in present), None)
    latest: dict[str, EnvironmentalObservation] = {}
    for row in rows:
        if row.parameter != headline or row.observed_at is None:
            continue
        station = (row.attributes or {}).get("station") or row.place_name
        if station not in latest or row.observed_at > latest[station].observed_at:
            latest[station] = row
    return headline, list(latest.values())


def environment(session: Session, slug: str) -> dict:
    city = _city(session, slug)
    headline, latest = latest_station_values(session, slug)
    label = PARAMETER_LABELS.get(headline or "", headline or "")
    official = (
        session.query(EnvironmentalObservation)
        .filter(EnvironmentalObservation.city_slug == slug, EnvironmentalObservation.dataset_code.in_(AIR_DATASETS), EnvironmentalObservation.parameter == headline, EnvironmentalObservation.value.isnot(None))
        .all()
        if headline
        else []
    )
    by_hour: dict = defaultdict(list)
    for row in official:
        if row.observed_at:
            by_hour[row.observed_at].append(row.value)
    newest = max((row.observed_at for row in latest), default=None)
    current = [row for row in latest if newest and (newest - row.observed_at).total_seconds() <= 3 * 3600]
    dataset_codes = sorted({row.dataset_code for row in official})
    dataset = dataset_codes[0] if dataset_codes else (AIR_DATASETS[0])
    unit = current[0].unit if current else ""
    weather_query = session.query(WeatherObservation).filter(WeatherObservation.city_slug == slug, WeatherObservation.parameter == "temperature_2m", WeatherObservation.value.isnot(None))
    if city is not None:
        weather_query = weather_query.filter(WeatherObservation.geo_unit_id == city.id)
    weather = weather_query.order_by(WeatherObservation.observed_at.desc()).limit(72).all()
    modelled = (
        session.query(EnvironmentalObservation)
        .filter(EnvironmentalObservation.city_slug == slug, EnvironmentalObservation.dataset_code == "open-meteo-air-quality", EnvironmentalObservation.parameter == "pm2_5", EnvironmentalObservation.value.isnot(None))
        .order_by(EnvironmentalObservation.observed_at.desc())
        .first()
    )
    stamp = newest.isoformat() + "Z" if newest else None
    kpis = [
        _kpi("Official stations reporting", len(current) or None, "stations", dataset, f"Monitoring sites with a {label} value within three hours of the newest stored hour. Regional readings count as one site each.", stamp),
        _kpi(f"Median station {label}", median([row.value for row in current]) if current else None, unit, dataset, f"Median of the latest {label} value at each reporting site. It is a summary of monitors, not a modelled city average.", stamp),
        _kpi(f"Highest station {label}", max((row.value for row in current), default=None), unit, dataset, "Highest latest value among reporting sites. Traffic-side sites usually read higher than background sites.", stamp),
        _kpi("Latest grid temperature", weather[0].value if weather else None, weather[0].unit if weather else "°C", "open-meteo-weather", "Most recent Open-Meteo grid value at the city point.", weather[0].observed_at.isoformat() if weather else None),
        _kpi("Latest CAMS PM2.5", modelled.value if modelled else None, modelled.unit if modelled else "µg/m³", "open-meteo-air-quality", "Copernicus CAMS model grid value. Not a monitor reading.", modelled.observed_at.isoformat() if modelled else None),
    ]
    series = [{"name": hour.strftime("%m-%d %H:00"), "value": _round(median(values), 2), "n": len(values)} for hour, values in sorted(by_hour.items())]
    series_label = f"Median station {label} by hour (UTC)"
    if not series:
        series = [{"name": row.observed_at.strftime("%m-%d %H:%M"), "value": row.value} for row in reversed(weather) if row.observed_at]
        series_label = "City grid temperature (°C)"
    limitations = [
        "Station values are hourly and provisional. Agencies validate and can revise them later.",
        "Open-Meteo values are model output and are never blended with monitor readings.",
    ]
    if headline and headline.startswith("daqi"):
        limitations.insert(0, "London figures are DAQI bands from 1 (low) to 10 (very high), not concentrations.")
    if slug == "singapore":
        limitations.insert(0, "NEA publishes PM2.5 for five planning regions, not individual stations.")
    return {
        "availability": "available" if current else ("partial" if weather else "unavailable"),
        "kpis": kpis,
        "rankings": [
            {"name": row.place_name, "value": _round(row.value, 1), "unit": row.unit, "geo_type": (row.attributes or {}).get("station_type") or (row.attributes or {}).get("site_type")}
            for row in sorted(current, key=lambda item: item.value, reverse=True)[:15]
        ],
        "series": series,
        "series_label": series_label,
        "sources": _cards(session, [*dataset_codes, "open-meteo-weather", "open-meteo-air-quality"]),
        "limitations": limitations,
    }


def traffic(session: Session, slug: str) -> dict:
    rows = session.query(TrafficObservation).filter(TrafficObservation.city_slug == slug, TrafficObservation.dataset_code.in_(TRAFFIC_DATASETS), TrafficObservation.volume.isnot(None)).all()
    if not rows:
        return _unavailable(NOT_CONNECTED["traffic"].get(slug, "No verified traffic feed is connected for this city."))
    dataset = rows[0].dataset_code
    if dataset in CRASH_TRAFFIC_DATASETS:
        ordered = sorted(rows, key=lambda row: row.observed_at or datetime.min.replace(tzinfo=timezone.utc))
        complete = _drop_incomplete_tail(ordered, value_attr="volume")
        latest = complete[-1] if complete else ordered[-1]
        previous = complete[-2] if len(complete) > 1 else None
        unit = "collisions" if "collision" in dataset else "crashes"
        label = "Collisions" if "collision" in dataset else "Crashes"
        period = (latest.attributes or {}).get("month") or str((latest.attributes or {}).get("year") or "")
        change = None
        if previous and previous.volume:
            change = _round(100 * (latest.volume - previous.volume) / previous.volume, 1)
        method = f"Open-data count of recorded {unit} for the city, aggregated by period. Not a volume or speed measure."
        return {
            "availability": "available",
            "kpis": [
                _kpi(f"{label}, latest complete period", latest.volume, unit, dataset, method, period),
                _kpi("Change vs previous period", change, "%", dataset, f"Latest complete {unit} total compared with the previous stored period.", period),
                _kpi("Periods stored", len(ordered), "periods", dataset, f"Number of {unit}-count periods loaded from the open dataset.", None),
                _kpi(f"Peak {unit} period", max(row.volume for row in ordered), unit, dataset, f"Highest {unit} count among stored periods.", None),
            ],
            "rankings": [],
            "series": [
                {
                    "name": (row.attributes or {}).get("month") or str((row.attributes or {}).get("year") or row.segment_id),
                    "value": row.volume,
                }
                for row in ordered
            ],
            "series_label": f"{label} by period",
            "sources": _cards(session, [dataset]),
            "limitations": [
                f"These are recorded {unit}, not traffic volume, speed, or congestion.",
                "The newest calendar period is omitted from headline KPIs when it looks incomplete versus the prior period.",
                "No live road-sensor feed is connected for this city.",
            ],
        }
    year = max((row.attributes or {}).get("year") or 0 for row in rows)
    rows = [row for row in rows if (row.attributes or {}).get("year") == year]
    counted = sum(1 for row in rows if (row.attributes or {}).get("estimation_method") == "Counted")
    by_borough: dict[str, list[float]] = defaultdict(list)
    by_category: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.borough:
            by_borough[row.borough].append(row.volume)
        by_category[(row.attributes or {}).get("road_category") or "Unknown"].append(row.volume)
    volumes = [row.volume for row in rows]
    method = "DfT annual average daily flow: motor vehicles per day at a count point, averaged over the year."
    return {
        "availability": "available",
        "kpis": [
            _kpi("Count points", len(rows), "points", "london-dft-aadf", "DfT count points inside Greater London for the year.", str(year)),
            _kpi("Median daily flow", median(volumes), "vehicles/day", "london-dft-aadf", method + " Median across count points; major roads are over-represented.", str(year)),
            _kpi("Busiest count point", max(volumes), "vehicles/day", "london-dft-aadf", method, str(year)),
            _kpi("Counted in that year", round(100 * counted / len(rows), 1), "% of points", "london-dft-aadf", "Share of points with a manual count that year. The rest are estimated from earlier counts.", str(year)),
        ],
        "rankings": [
            {"name": name, "value": _round(median(values), 0), "unit": "median vehicles/day", "n": len(values)}
            for name, values in sorted(by_borough.items(), key=lambda item: median(item[1]), reverse=True)
        ],
        "series": [
            {"name": ROAD_CATEGORIES.get(code, code), "value": _round(median(values), 0), "n": len(values)}
            for code, values in sorted(by_category.items(), key=lambda item: median(item[1]), reverse=True)
        ],
        "series_label": f"Median daily flow by road category ({year})",
        "sources": _cards(session, ["london-dft-aadf"]),
        "limitations": [
            "Annual averages, not live traffic and not a congestion or speed measure.",
            "Borough medians compare count points, which are concentrated on main roads.",
            "Live speeds (TfL or DfT) are not connected.",
        ],
    }


def crime(session: Session, slug: str) -> dict:
    rows = session.query(CrimeAggregate).filter(CrimeAggregate.city_slug == slug, CrimeAggregate.dataset_code.in_(CRIME_DATASETS), CrimeAggregate.incident_count.isnot(None)).all()
    if not rows:
        return _unavailable(NOT_CONNECTED["crime"].get(slug, "No verified aggregated crime source is connected for this city."))
    dataset = rows[0].dataset_code
    monthly = all(len(row.period_label or "") == 7 for row in rows)
    base_limits = [
        "Counts are offences recorded by police. They depend on reporting and recording practice and do not measure all harm.",
        "No individual-level prediction or demographic profiling is performed.",
    ]
    if monthly:
        months = sorted({row.period_label for row in rows})
        by_month: dict[str, int] = defaultdict(int)
        by_borough: dict[str, int] = defaultdict(int)
        by_category: dict[str, int] = defaultdict(int)
        for row in rows:
            by_month[row.period_label] += row.incident_count
        # Skip a trailing incomplete month in headline KPIs.
        kpi_months = list(months)
        while len(kpi_months) >= 2 and by_month[kpi_months[-1]] < 0.4 * by_month[kpi_months[-2]]:
            kpi_months.pop()
        latest = kpi_months[-1]
        last12 = set(kpi_months[-12:])
        for row in rows:
            if row.period_label in last12:
                if row.borough:
                    by_borough[row.borough] += row.incident_count
                by_category[row.category or "Unspecified"] += row.incident_count
        window = f"{kpi_months[-12]} to {latest}" if len(kpi_months) >= 12 else f"{kpi_months[0]} to {latest}"
        prior = f"{int(latest[:4]) - 1}{latest[4:]}" if len(latest) == 7 else None
        if prior and prior not in by_month:
            prior = None
        borough_note = "The City of London Police area is not in this file." if dataset == "london-mps-borough-crime" else "Citywide monthly totals; no district breakdown is loaded."
        limits = list(base_limits)
        if dataset == "london-mps-borough-crime":
            limits += [
                "Borough totals are counts, not rates. Westminster's large daytime and visitor population raises its count.",
                "The City of London has its own police force and is excluded.",
            ]
        else:
            limits.append("Citywide monthly totals only. District crime maps are not drawn from this extract.")
            limits.append("The newest calendar month is omitted from headline KPIs when it looks incomplete versus the prior month.")
        return {
            "availability": "available",
            "kpis": [
                _kpi("Recorded offences, latest month", by_month[latest], "offences", dataset, "Sum over boroughs and offence groups for the month." if by_borough else "Citywide incident count for the month.", latest),
                _kpi("Recorded offences, last 12 months", sum(by_month[m] for m in last12), "offences", dataset, "Sum of the twelve latest complete months.", window),
                _kpi("Change vs same month last year", _round(100 * (by_month[latest] - by_month[prior]) / by_month[prior], 1) if prior and by_month.get(prior) else None, "%", dataset, "Latest complete month compared with the same month a year earlier. One month is noisy.", f"{prior} to {latest}" if prior else None),
                _kpi("Boroughs covered", len({row.borough for row in rows if row.borough}) or None, "boroughs", dataset, borough_note, window),
            ],
            "rankings": [{"name": name, "value": value, "unit": "offences, 12 months"} for name, value in sorted(by_borough.items(), key=lambda item: item[1], reverse=True)],
            "categories": [{"name": name, "value": value} for name, value in sorted(by_category.items(), key=lambda item: item[1], reverse=True)],
            "series": [{"name": month, "value": by_month[month]} for month in months],
            "series_label": "Recorded offences by month",
            "hotspots_available": False,
            "point_sample_rows": 0,
            "sources": _cards(session, [dataset]),
            "limitations": limits,
        }
    years = sorted({row.period_label for row in rows if row.category == "Total"})
    totals = {row.period_label: row.incident_count for row in rows if row.category == "Total"}
    latest = years[-1] if years else None
    previous = years[-2] if len(years) > 1 else None
    categories = sorted(((row.category, row.incident_count) for row in rows if row.period_label == latest and row.category != "Total"), key=lambda item: item[1], reverse=True)
    label = "Selected major offences" if dataset == "sg-spf-major-offences" else "Registered crimes"
    limits = list(base_limits)
    if dataset == "sg-spf-major-offences":
        limits.append("SPF publishes a selected set of major offences. The total is not all recorded crime.")
        cheating = next((value for name, value in categories if name.lower().startswith("cheating")), None)
        if cheating and totals.get(latest):
            limits.append(f"Cheating-related offences, mostly scams, are {round(100 * cheating / totals[latest])}% of the {latest} total, so the total mainly follows scam trends.")
    if dataset == "ams-cbs-crime":
        limits.append("CBS figures are for the whole municipality. No stadsdeel breakdown is published in this table, so no crime map is drawn.")
    if dataset == "toronto-reported-crime":
        limits.append("Toronto Police Service annual reported-crime totals by category. Neighbourhood breakdowns are not loaded.")
    if dataset in {"chicago-crime-monthly", "la-crime-monthly"}:
        limits.append("Citywide monthly totals only. District or community-area crime maps are not drawn from this extract.")
    return {
        "availability": "available" if latest else "partial",
        "kpis": [
            _kpi(f"{label}, latest year", totals.get(latest), "cases", dataset, rows[0].methodology, latest),
            _kpi("Change vs previous year", _round(100 * (totals[latest] - totals[previous]) / totals[previous], 1) if previous and totals.get(previous) else None, "%", dataset, "Year-on-year change in the total.", f"{previous} to {latest}" if previous else None),
            _kpi("Years of history", len(years) or None, "years", dataset, "Years with a published total.", f"{years[0]} to {latest}" if years else None),
        ],
        "rankings": [{"name": name, "value": value, "unit": "cases"} for name, value in categories[:15]],
        "categories": [{"name": name, "value": value} for name, value in categories],
        "series": [{"name": year, "value": totals[year]} for year in years],
        "series_label": f"{label} per year",
        "hotspots_available": False,
        "point_sample_rows": 0,
        "sources": _cards(session, [dataset]),
        "limitations": limits,
    }


def population(session: Session, slug: str) -> dict:
    city = _city(session, slug)
    rows = session.query(PopulationObservation).filter(PopulationObservation.city_slug == slug, PopulationObservation.dataset_code.in_(POPULATION_DATASETS), PopulationObservation.population.isnot(None)).all()
    if not rows or city is None:
        return _unavailable("No verified population source is connected for this city.")
    city_rows = [row for row in rows if row.geo_unit_id == city.id and row.metric_kind != "resident_population"]
    series = {row.vintage_year: row.population for row in city_rows}
    years = sorted(series)
    latest = years[-1] if years else None
    district_rows = [row for row in rows if row.geo_unit_id and row.geo_unit_id != city.id]
    district_year = max((row.vintage_year for row in district_rows), default=None)
    current_districts = [row for row in district_rows if row.vintage_year == district_year]
    dataset = (city_rows or rows)[0].dataset_code
    method = (city_rows or rows)[0].methodology
    base = latest - 5 if latest else None
    change_note = "Change between two vintages of the same series."
    if dataset in SERIES_BREAKS and base is not None and base < SERIES_BREAKS[dataset]:
        base = SERIES_BREAKS[dataset] if SERIES_BREAKS[dataset] < latest else None
        change_note = "Measured from the first census-based year only. Earlier years use a different census base and are not comparable."
    kpis = [
        _kpi("Population", series.get(latest), "people", dataset, method, str(latest) if latest else None),
        _kpi(f"Change since {base}" if base else "Change over five years", _round(100 * (series[latest] - series[base]) / series[base], 1) if base in series else None, "%", dataset, change_note, f"{base} to {latest}" if base in series else None),
    ]
    residents = [row for row in rows if row.metric_kind == "resident_population" and row.vintage_year == latest]
    if residents:
        kpis.append(_kpi("Resident population", residents[0].population, "people", dataset, "Citizens and permanent residents. Excludes non-residents.", str(latest)))
    area, basis = _area(session, city)
    if area and series.get(latest):
        kpis.append(_kpi("Density", series[latest] / area, "people/km²", dataset, f"Population divided by {area:.0f} km², the area of {basis}.", str(latest)))
    kpis.append(_kpi("Districts with figures", len(current_districts) or None, "districts", current_districts[0].dataset_code if current_districts else dataset, "Districts with a population value for the latest district vintage.", str(district_year) if district_year else None))
    limitations = ["Different cities use different official measures (estimate, register, or census-based). Compare cities with care."]
    if dataset == "eurostat-city-population":
        limitations.append("From 2024 the German figures are based on the 2022 census, so the drop between 2023 and 2024 is a statistical revision, not people leaving. District figures are not loaded.")
    if slug == "singapore":
        limitations.append("Planning-area population comes from survey tables and is not loaded, so no district map is drawn.")
    return {
        "availability": "available",
        "map_choropleth": "available" if current_districts else "withheld",
        "kpis": kpis,
        "rankings": [{"name": row.place_name, "value": row.population, "unit": "people", "vintage": row.vintage_year, "kind": row.metric_kind} for row in sorted(current_districts, key=lambda item: item.population, reverse=True)],
        "series": [{"name": str(year), "value": series[year]} for year in years],
        "series_label": "City population by year",
        "sources": _cards(session, [row.dataset_code for row in rows]),
        "limitations": limitations,
    }


def waste(session: Session, slug: str) -> dict:
    return _unavailable(NOT_CONNECTED["waste"])


def transport(session: Session, slug: str) -> dict:
    stops = session.query(TransitStop).filter(TransitStop.city_slug == slug).all()
    taxis = (
        session.query(InfrastructureFeature)
        .filter(InfrastructureFeature.city_slug == slug, InfrastructureFeature.feature_type == "available_taxis")
        .all()
    )
    taxis.sort(key=lambda row: (row.attributes or {}).get("timestamp") or "")
    if not stops and not taxis:
        return _unavailable("No verified transit source is connected for this city.")
    kinds: dict[str, int] = defaultdict(int)
    for stop in stops:
        kinds[stop.location_type or "station"] += 1
    labels = {"station": "Rail stations", "halt": "Rail halts", "tram_stop": "Tram stops", "subway": "Metro stations", "light_rail": "Light rail stations", "monorail": "Monorail stations"}
    kpis = [_kpi("Rail, metro and tram stops", len(stops) or None, "stops", "osm-rail-stations", "OpenStreetMap station and tram-stop nodes inside the city boundary. A station can appear as more than one node.", None)]
    if taxis:
        latest = taxis[-1]
        kpis.append(_kpi("Taxis available now", latest.value, "taxis", "sg-taxi-availability", latest.methodology, (latest.attributes or {}).get("timestamp")))
    return {
        "availability": "partial",
        "kpis": kpis,
        "rankings": [{"name": labels.get(kind, kind.replace("_", " ").title()), "value": count, "unit": "stops"} for kind, count in sorted(kinds.items(), key=lambda item: item[1], reverse=True)],
        "series": [{"name": (row.attributes or {}).get("timestamp", "")[5:16].replace("T", " "), "value": row.value} for row in taxis[-48:]],
        "series_label": "Available taxis per refresh" if taxis else "",
        "sources": _cards(session, ["osm-rail-stations", *(["sg-taxi-availability"] if taxis else [])]),
        "limitations": [
            "Stops come from OpenStreetMap and are community-mapped. Bus stops are excluded.",
            "No timetable, ridership, or live vehicle positions are connected for this city.",
        ],
    }


def infrastructure(session: Session, slug: str) -> dict:
    roads = session.query(InfrastructureFeature).filter(InfrastructureFeature.city_slug == slug, InfrastructureFeature.feature_type == "major_road", InfrastructureFeature.geometry_geojson.isnot(None)).all()
    if not roads:
        return _unavailable("No infrastructure layer is stored for this city.")
    by_type: dict[str, float] = defaultdict(float)
    by_name: dict[str, float] = defaultdict(float)
    for row in roads:
        km = _line_km(json.loads(row.geometry_geojson))
        by_type[(row.attributes or {}).get("highway") or "other"] += km
        if not (row.name or "").startswith("way "):
            by_name[row.name] += km
    dataset = roads[0].dataset_code
    return {
        "availability": "partial",
        "kpis": [
            _kpi("Motorway and trunk ways", len(roads), "ways", dataset, "OpenStreetMap ways tagged motorway or trunk that touch the city boundary.", None),
            _kpi("Motorway length", by_type.get("motorway"), "km", dataset, "Sum of way lengths. Dual carriageways count each direction, and ways crossing the boundary are counted in full.", None),
            _kpi("Trunk road length", by_type.get("trunk"), "km", dataset, "Sum of way lengths, measured the same way.", None),
        ],
        "rankings": [{"name": name, "value": _round(km, 1), "unit": "km"} for name, km in sorted(by_name.items(), key=lambda item: item[1], reverse=True)[:12]],
        "series": [],
        "series_label": "",
        "sources": _cards(session, [dataset]),
        "limitations": ["Building footprints and the full street network are not loaded.", "Lengths are approximate."],
    }


def map_layer(session: Session, city: GeoUnit, layer: str, feature) -> tuple[list[dict], str] | None:
    slug = city.slug
    if layer == "admin":
        rows = _districts(session, city)
        if not rows:
            return None
        source = (rows[0].properties or {}).get("source") or "the official district layer"
        return [item for item in (feature(row) for row in rows) if item], f"{len(rows)} {(rows[0].properties or {}).get('district_type') or 'district'} polygons from {source}."
    if layer == "traffic":
        mapped = session.query(TrafficObservation).filter(TrafficObservation.city_slug == slug, TrafficObservation.dataset_code.in_(TRAFFIC_DATASETS), TrafficObservation.latitude.isnot(None)).all()
        if mapped:
            year = max((row.attributes or {}).get("year") or 0 for row in mapped)
            features = [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [row.longitude, row.latitude]},
                    "properties": {"name": row.street or row.segment_id, "value": row.volume, "unit": "vehicles/day", "borough": row.borough, "availability": "available", "dataset_code": row.dataset_code, "period": str(year)},
                }
                for row in mapped
                if (row.attributes or {}).get("year") == year
            ]
            return features, f"DfT {year} annual average daily flow at {len(features)} count points. Annual averages, not live traffic."
        crash_rows = session.query(TrafficObservation).filter(TrafficObservation.city_slug == slug, TrafficObservation.dataset_code.in_(CRASH_TRAFFIC_DATASETS)).all()
        if crash_rows:
            return [], f"{city.name} traffic data is citywide crash/collision counts shown in Explore, not mapped points."
        return [], NOT_CONNECTED["traffic"].get(slug, f"No traffic feed is connected for {city.name}.")
    if layer == "environment":
        headline, latest = latest_station_values(session, slug)
        if not latest:
            return None
        label = PARAMETER_LABELS.get(headline or "", headline)
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [row.longitude, row.latitude]},
                "properties": {"name": row.place_name, "value": row.value, "unit": row.unit, "parameter": headline, "availability": "available", "dataset_code": row.dataset_code, "observed_at": row.observed_at.isoformat() + "Z"},
            }
            for row in latest
            if row.longitude is not None and row.latitude is not None
        ]
        return features, f"Latest official {label} at each monitoring site. Points are monitors, not an interpolated surface."
    if layer == "population":
        rows = session.query(PopulationObservation).filter(PopulationObservation.city_slug == slug, PopulationObservation.geo_unit_id.isnot(None), PopulationObservation.geo_unit_id != city.id, PopulationObservation.population.isnot(None)).all()
        if not rows:
            return [], f"No district population is loaded for {city.name}, so the choropleth is withheld. The city total is in Explore."
        year = max(row.vintage_year for row in rows)
        geos = {row.id: row for row in _districts(session, city)}
        features = []
        for row in rows:
            geo = geos.get(row.geo_unit_id)
            if row.vintage_year == year and geo is not None:
                item = feature(geo, row.population, {"unit": "people", "period": str(year), "dataset_code": row.dataset_code})
                if item:
                    features.append(item)
        return features, f"{year} district population from {rows[0].dataset_code}, joined on official codes to current boundaries."
    if layer == "crime":
        rows = session.query(CrimeAggregate).filter(CrimeAggregate.city_slug == slug, CrimeAggregate.dataset_code == "london-mps-borough-crime").all()
        if not rows:
            return [], "No district crime totals are published for this city in a connected source, so no crime map is drawn."
        months = sorted({row.period_label for row in rows})[-12:]
        totals: dict[str, int] = defaultdict(int)
        for row in rows:
            if row.period_label in months and row.geo_unit_id:
                totals[row.geo_unit_id] += row.incident_count or 0
        pops = {
            row.geo_unit_id: row.population
            for row in session.query(PopulationObservation).filter(PopulationObservation.city_slug == slug, PopulationObservation.dataset_code == "london-ons-mye", PopulationObservation.geo_unit_id.isnot(None)).order_by(PopulationObservation.vintage_year).all()
        }
        features = []
        for geo in _districts(session, city):
            count = totals.get(geo.id)
            rate = round(1000 * count / pops[geo.id], 1) if count and pops.get(geo.id) else None
            item = feature(geo, rate, {"unit": "offences per 1,000 residents", "count": count, "period": f"{months[0]} to {months[-1]}", "dataset_code": "london-mps-borough-crime"})
            if item:
                features.append(item)
        return features, "Recorded offences per 1,000 residents over the last 12 months (MPS counts over ONS mid-year estimates). Residents are not the only people present: central boroughs with many visitors and workers show higher rates. The City of London is policed separately and shows as unavailable."
    if layer == "transit":
        stops = session.query(TransitStop).filter(TransitStop.city_slug == slug, TransitStop.latitude.isnot(None)).limit(3000).all()
        features = [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [stop.longitude, stop.latitude]}, "properties": {"name": stop.name, "value": None, "kind": stop.location_type, "availability": "available", "dataset_code": stop.dataset_code, "stop_id": stop.stop_id}}
            for stop in stops
        ]
        return features, (f"{len(features)} rail, metro and tram stops from OpenStreetMap. Not live vehicle positions. © OpenStreetMap contributors." if features else f"No transit stops are stored for {city.name}.")
    if layer == "roads":
        roads = session.query(InfrastructureFeature).filter(InfrastructureFeature.city_slug == slug, InfrastructureFeature.feature_type == "major_road", InfrastructureFeature.geometry_geojson.isnot(None)).limit(2000).all()
        features = [
            {"type": "Feature", "geometry": json.loads(row.geometry_geojson), "properties": {"name": row.name, "value": None, "kind": (row.attributes or {}).get("highway"), "availability": "available", "dataset_code": row.dataset_code}}
            for row in roads
        ]
        return features, (f"{len(features)} OpenStreetMap motorway and trunk ways. © OpenStreetMap contributors." if features else f"No major-road lines are stored for {city.name}.")
    if layer == "waste":
        return [], NOT_CONNECTED["waste"]
    return None
