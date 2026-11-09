# Feasibility

Checked 9 November 2026. NYC can support a real reference implementation. It cannot honestly support every module in the original brief at the same spatial and temporal resolution.

## Strong enough to implement

| Domain | Evidence | Constraint |
| --- | --- | --- |
| Geography | DCP borough, community district, CDTA, and 2020 NTA polygons on SODA | Statistical areas are not political neighborhoods |
| Traffic speeds | DOT link snapshot `i4gi-tjb9`, observed updating on 8 November 2026 | Snapshot, not an archive |
| Traffic volume | ATR counts `7ym2-wayt`, hour and minute fields | Samples, not continuous coverage |
| Air quality, neighbourhood | DOHMH indicators `c3uy-2p5r`, including 2024 PM2.5 and NO2 | Annual or seasonal, modelled |
| Weather | Open-Meteo archive, hourly, CC BY 4.0 | Grid cell, not a district mean |
| Modelled pollutants | Open-Meteo air-quality API, hourly PM2.5, PM10, NO2, CO | CAMS grid, kept separate from DOHMH |
| Waste | DSNY monthly tonnage `ebb7-mvp5` | Not a collection schedule |
| Transit network | MTA regular subway GTFS over HTTPS | Schedule, not observed headway |
| Transit demand | MTA hourly ridership `5wq4-mkjj`, 47,409,293 rows from 2025-01-01 to 2026-10-29 | Reference load keeps a short window |
| Safety, aggregated | NYPD YTD complaints `5uac-w243` | Reports, not rates; no person-level model |
| Crashes | NYPD crash table `h9gi-nx95` | Borough aggregate in the reference load |
| Housing stock | PLUTO `64uk-42ks`, updated 24 August 2026 | Aggregated lot counts, not footprints |
| Roads | OSM motorway and trunk via Overpass | Not the full street graph |

## Historical only

- Community-district population `xi7c-iiu2` ends in the 2010 Census. It is not painted on current boundaries.
- NTA demographic table `rnsn-acs2` is a 2000–2010 extract and uses 2010 NTA codes, so it is not joined to 2020 NTAs.
- NYPD historic complaints `qgea-i56i` exist, but the full table is too large for the reference load. Monthly aggregation is attempted and recorded if the API times out.
- NYCCAS rasters `q68s-8qxv` are file attachments whose metadata last changed in 2017. They are not a current layer.
- Static historical ATR `btm5-ppia` is superseded for ingestion by the current ATR feed.

## Not used, on purpose

- `t8c6-3i7b` is a projection file with opaque fields `_1` and `_2`. Loading it would risk labeling a projection as a count.
- `3qem-6v3v` counts shelter buildings. It is ingested only under that name.
- `w7kn-7zx2` is an ACS demographic profile for 2016 and has no SODA columns.
- WorldPop is a large modelled raster and is not connected.
- OpenAQ v3 requires `OPENAQ_API_KEY`. Without it the connector stops.
- Census ACS borough totals are requested at bootstrap and stored only if the API responds. The keyless call from this environment returned an empty body, so borough ACS is conditional.

## Expansion

Singapore, Amsterdam, London, Berlin, and Trier are registry cities. The weather connector accepts any city coordinate, and Nominatim can attach an OSM boundary. No indicator is copied from New York into those cities.
