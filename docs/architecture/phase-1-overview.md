# Phase 1 — Feasibility and approval gate

Research date: 9 November 2026.  
Scope: architecture and dataset verification only. No connectors, models, or interface have been built.

## Decision

New York City is a valid first reference city. Public boundaries, buildings, land use, subway geography, hourly subway ridership, monthly sanitation tonnage, collision records, complaint records, neighbourhood air-quality indicators, EPA monitoring files, and historical weather can support a real intelligence platform.

The complete product vision cannot be implemented from public data alone. Several requested behaviours have no supporting source:

- A live reading for every road, district, and pollutant.
- A historical speed archive. NYC DOT publishes a current speed snapshot. History begins only if URBIX stores it.
- Network-wide next-hour traffic forecasts. Automated traffic counts are samples, not a continuous citywide series.
- Official current population for every neighbourhood, until a Census API key or an official small-area table is added.
- Waste collection schedules or missed-pickup events.
- The same dataset depth in every future city.
- Any individual-level public-safety prediction. That is out of scope even where point data exists.

URBIX should be built as an evidence system. Every city page must be able to say that a domain is available, partial, historical only, or unavailable. A missing value stays null. A prediction stays in the prediction store and is never written back as an observation.

## What “complete enough” means for the first release

A defensible NYC reference implementation can include:

1. A flexible world hierarchy with NYC loaded from official boundaries.
2. An interactive map whose layers come from stored geometries and aggregated observations.
3. Transport forecasting at subway-complex and hourly resolution.
4. Monthly waste forecasting at community-district resolution.
5. Station-level air-quality forecasting from EPA monitors, plus neighbourhood indicator trends from the NYC Department of Health and Mental Hygiene.
6. Weather as a gridded reanalysis covariate, labeled as model-based weather, not as a city sensor.
7. Aggregated public-safety patterns and collision analysis, with bias and data-quality limits stated on the page.
8. Infrastructure density and transit accessibility from building footprints, PLUTO, GTFS, and a walk network.
9. An agent that can only quote numbers returned by approved tools.

Graph neural networks, citywide hourly pollution surfaces, and live traffic operations are later research tracks. They are not part of the first working release.

## Domain assessment

| Module | Support | Why |
| --- | --- | --- |
| Global intelligence | Partial | Country and state boundaries are available. Only NYC will have urban datasets at first, so global indicator maps must show coverage, not imputed values. |
| City intelligence | Strong, with gaps | A command centre can be assembled from the domains below. It cannot show one complete live operating picture. |
| Geospatial platform | Strong | Boroughs, community districts, CDTAs, NTAs, tracts, building footprints, and subway stations were retrieved or their schemas were read. |
| Traffic | Partial | 15-minute ATR sample counts exist. Link speeds are a snapshot. Continuous road-level history does not. |
| Environment | Partial to strong | Neighbourhood annual and seasonal indicators, EPA daily files, hourly PM2.5 files, and hourly weather exist. Live fused surfaces do not. |
| Public safety | Partial and restricted | Complaint and collision archives are rich. Analysis must stay aggregated. The complaint feed contains impossible dates. |
| Population | Difficult for current official counts | Boundaries are current. The readily queried population tables are historical, projected, or gridded estimates. Census API calls now require a key. |
| Public transport | Strong | Station geometry, GTFS, and hourly ridership datasets exist across multiple year ranges. Bus ridership is by route, not by stop. |
| Waste | Strong for tonnage | Monthly tons by borough and community district run from January 1990 through October 2026. Operations schedules were not found. |
| Infrastructure | Strong for static form | Building footprints and PLUTO were verified. Condition, outages, and work orders were not. |

## NYC as the reference city

The selection holds for five practical reasons.

1. **Geography.** Department of City Planning boundaries for boroughs, community districts, community-district tabulation areas, neighbourhood tabulation areas, and census tracts are published on NYC Open Data and were readable on 9 November 2026.
2. **Time.** Waste tonnage, complaints, collisions, traffic counts, and subway ridership span multiple years. That is enough for chronological validation.
3. **Access.** The core city tables use the Socrata Open Data API. EPA daily files and the Open-Meteo archive responded without a key. OpenAQ and the Census API did not.
4. **Licence posture.** WorldPop and Open-Meteo data are CC BY 4.0. NYC Open Data view metadata does not carry an OSI licence identifier; use is governed by NYC terms and the data is provided as-is. MTA feed terms require URBIX to cache feeds rather than proxy the agency’s servers to end users.
5. **Known holes are modelable.** The gaps are specific enough to represent as coverage records instead of being hidden.

No separate database or application is required for a second city. A city is a geographical unit plus a set of connector configurations and coverage rows.

## Architectural commitments

These are the decisions Phase 2 should implement, unless this review changes them.

- One modular monolith: Next.js, FastAPI, a Python worker, PostgreSQL/PostGIS, Redis, and MLflow. No microservices.
- One flexible geographical graph, not ten rigid levels and not one schema per city.
- Raw files in object storage or Parquet. Analytical tables in PostGIS. Predictions in their own tables.
- Domain models stay separate. Subway ridership, waste tonnage, monitor-level pollution, and sampled traffic are different learning problems.
- The language model plans and explains. Python computes. The analyst database role is read-only, and the agent has no free-form SQL tool.
- The interface is a desktop-first intelligence workspace. MapLibre renders real geometries. Empty, loading, and unavailable states are part of the design.

## What was verified, and what was not

Verified means a metadata document, a catalogue record, a sample row, a file header, or a style document was returned successfully on 9 November 2026. Details and endpoints are in the [dataset inventory](../datasets/nyc-inventory.md).

Not verified, and therefore not approved for a connector yet:

- A successful download and parse of the MTA GTFS zip. The URL is published; the feed itself was not unpacked.
- OpenAQ measurements. The locations call returned HTTP 401 without a key.
- Census statistics. The ACS 5-year call returned an HTML page titled “Missing Key”.
- ATR rows for 2019, 2024, and 2025. Those requests returned HTTP 503, which shows service trouble, not absence of the year.
- The full row count of any large table. Count queries were too expensive and several timed out.
- Any model metric. None will exist until a pipeline is trained and evaluated.

## Approval gate

Phase 2 should not start until this package is accepted. Approval means:

1. NYC remains the first city.
2. The first analytical release may ship with explicit unavailable states for live traffic, official small-area population, waste operations, and OpenAQ.
3. Public-safety work is limited to aggregated historical patterns, collision analysis, and count forecasting.
4. The first forecasting models are subway ridership, monthly waste tonnage, and monitor-level PM2.5. Traffic-speed modelling waits until URBIX has archived the DOT snapshot.
5. Phase 2 builds the monorepo, containers, geographical model, and empty API shell. It does not load the full city or train models.

If any of those five points should change, the implementation plan changes before code is written.
