# NYC dataset inventory

Verified on 9 November 2026 by reading Socrata view metadata, catalogue search, sample rows, file headers, or API responses. This is an inventory of sources, not a loaded warehouse.

Socrata endpoints below accept SoQL. The unauthenticated API often returns HTTP 503 under load and defaults to 1,000 rows. Bulk ingestion should prefer the versioned CSV export, paginate, retry, and use an application token stored outside the repository. An export URL has the form:

`https://data.cityofnewyork.us/api/v3/views/{id}/export.csv?accessType=DOWNLOAD`

The resource URL used for sampled rows is:

`https://data.cityofnewyork.us/resource/{id}.json`

NYC Open Data view metadata left `license` empty. Treat these tables as public data under NYC terms of use, supplied without warranty. Do not assign an OSI licence that the publisher did not publish.

## Coverage classes used below

| Class | Meaning for URBIX |
| --- | --- |
| Available | Usable for the stated geography and time, with normal quality controls |
| Partial | Real data, but the wrong grain, incomplete space, or incomplete time for the feature people will expect |
| Historical only | Published as a static or closed series |
| Restricted | Usable only after aggregation or field suppression |
| Unavailable | No verified source for that behaviour |

---

## 1. Automated Traffic Volume Counts

| | |
| --- | --- |
| Provider | NYC Department of Transportation |
| Dataset | Automated Traffic Volume Counts |
| Identifier | `7ym2-wayt` |
| Page | https://data.cityofnewyork.us/Transportation/Automated-Traffic-Volume-Counts/7ym2-wayt |
| Format | Socrata JSON, CSV, and other SODA formats |
| Update | Metadata says every 6 months. View `rowsUpdatedAt` converts to 20 March 2026. |
| Geography | Sampled bridge and roadway segments in the five boroughs. WKT geometry, segment id, street, from-street, to-street, direction. |
| Time | Fifteen-minute bins. Fields: `yr`, `m`, `d`, `hh`, `mm`, `vol`. |
| Confirmed rows | Year filters returned rows for 2000, 2012, 2014, 2022, and 2023. Sample minutes were 15 and 45, so the grain is sub-hourly. |
| Not confirmed | Filters for 2019, 2024, and 2025 returned HTTP 503. Absence is not proven. |
| Fields | `requestid`, `boro`, `yr`, `m`, `d`, `hh`, `mm`, `vol`, `segmentid`, `wktgeom`, `street`, `fromst`, `tost`, `direction` |
| Licence | NYC Open Data terms. Licence field empty. |
| Limits | The publisher states that counts do not cover the whole year and that days counted vary by location. This is not a continuous network series and not a real-time feed. |
| Use | Segment-level volume profiles, weekday and weekend comparisons, and forecasts only where a segment has a dense repeated history. |
| Class | Partial |

## 2. Historical traffic volume counts

| | |
| --- | --- |
| Provider | NYC DOT |
| Dataset | Traffic Volume Counts (Historical) |
| Identifier | `btm5-ppia` |
| Format | Socrata. Wide table: one row per count day and 24 hourly columns. |
| Update | Metadata says historical data. `rowsUpdatedAt` converts to 26 May 2022. |
| Fields | `id`, `segmentid`, `roadway_name`, `from`, `to`, `direction`, `date`, plus `_12_00_1_00_am` through `_11_00_12_00am` |
| Limits | Static. Superseded for current ingestion by `7ym2-wayt`. A sample row was not retrieved. |
| Use | Optional backfill after the wide schema is profiled. Do not mix it blindly with the long 15-minute feed. |
| Class | Historical only |

## 3. DOT traffic speeds

| | |
| --- | --- |
| Provider | NYC DOT |
| Dataset | DOT Traffic Speeds |
| Identifier | `i4gi-tjb9` |
| Format | Socrata JSON |
| Update | Metadata: data changes several times per minute and the dataset is updated daily. `rowsUpdatedAt` converts to 9 November 2026. |
| Sample | Two rows returned with the same `data_as_of` of `2026-11-08T18:21:05`. One link reported speed `11.18` and travel time `584`. Another reported speed `0`, travel time `0`, and status `-101`. |
| Fields | `id`, `speed`, `travel_time`, `status`, `data_as_of`, `link_id`, `link_points`, `encoded_poly_line`, `encoded_poly_line_lvls`, `owner`, `transcom_id`, `borough`, `link_name` |
| Limits | This is a latest-state feed, not an archive. A speed of zero with a non-normal status must be stored as missing, not as congestion. During this check the observation timestamp lagged the metadata update by many hours, so the product must not be labeled real-time. |
| Use | A current link-speed layer, and a forecast source only after URBIX archives successive snapshots. |
| Class | Partial |

## 4. NYPD complaint data, historic

| | |
| --- | --- |
| Provider | NYPD, via NYC Open Data |
| Dataset | NYPD Complaint Data Historic |
| Identifier | `qgea-i56i` |
| Page | https://data.cityofnewyork.us/Public-Safety/NYPD-Complaint-Data-Historic/qgea-i56i |
| Update | Metadata says annually. `rowsUpdatedAt` converts to a 2026 date. The public description still says the series runs from 2006 through 2019. |
| Confirmed rows | A row with `cmplnt_fr_dt` of 1 January 2023 and a row dated 1 June 2024 were returned. The description is stale. A 2006 window returned HTTP 503. |
| Geography | `latitude`, `longitude`, `lat_lon`, borough, precinct (`addr_pct_cd`), patrol borough. Coordinates can be as fine as a block or intersection. |
| Fields of analytical interest | `cmplnt_num`, complaint from/to date and time, `rpt_dt`, `ky_cd`, `ofns_desc`, `pd_cd`, `pd_desc`, `law_cat_cd`, `boro_nm`, `prem_typ_desc`, `juris_desc`, precinct, coordinates |
| Fields URBIX will not model | Suspect age group, race, and sex. Victim demographic fields are also excluded from features and from the default API. |
| Limits | Reporting and enforcement bias. Invalid dates exist in the current-year companion file and must be assumed possible here. Overlap with the year-to-date file is likely. Deduplicate on `cmplnt_num`. |
| Use | Aggregates by time, offence class, precinct, NTA, or H3 cell. Hotspot description. Monthly or weekly count forecasts. |
| Class | Restricted |

## 5. NYPD complaint data, year to date

| | |
| --- | --- |
| Provider | NYPD |
| Dataset | NYPD Complaint Data Current (Year To Date) |
| Identifier | `5uac-w243` |
| Update | Metadata says quarterly. `rowsUpdatedAt` converts to 5 November 2026. The description text still refers to 2019 and is stale. |
| Confirmed rows | Complaints dated 1 January 2026 and 30 September 2026 were returned. Ordering by date also returned `1015-09-18`, which is not a usable timestamp. |
| Schema | Same analytical family as `qgea-i56i`, plus `geocoded_column`. |
| Limits | Quarterly lag. Dirty dates. Point locations are more precise than URBIX should display by default. |
| Use | Same restricted aggregate use as the historic file, after validation and deduplication. |
| Class | Restricted |

## 6. Motor vehicle collisions

| | |
| --- | --- |
| Provider | NYPD |
| Dataset | Motor Vehicle Collisions - Crashes |
| Identifier | `h9gi-nx95` |
| Update | Metadata says daily. `rowsUpdatedAt` converts to 6 November 2026. |
| Sample | A row dated 6 November 2026 in Queens was returned, with latitude and an injury count. |
| Fields | `crash_date`, `crash_time`, `borough`, `zip_code`, latitude, longitude, street names, injury and fatality counts by person type, contributing factors, `collision_id`, vehicle types |
| Limits | Police-reported crashes only. Some rows lack coordinates or borough. Injury counts of zero are real zeros for that crash; a missing coordinate is not a zero. This is a safety dataset, not a crime-prediction dataset. |
| Use | Collision density, street and district comparison, time-of-day patterns, and aggregate count forecasts. |
| Class | Available, with incomplete geocoding |

## 7. Air quality and health impacts

| | |
| --- | --- |
| Provider | NYC Department of Health and Mental Hygiene |
| Dataset | Air Quality and Health Impacts |
| Identifier | `c3uy-2p5r` |
| Update | As needed. `rowsUpdatedAt` converts to 18 June 2026. |
| Sample | Ozone summer-mean rows for 2024 were returned in ppb, at borough and UHF34 geography. The CSV export also contains PM2.5 and NO2 at UHF34 and community-district geography. |
| Fields | `unique_id`, `indicator_id`, `name`, `measure`, `measure_info`, `geo_type_name`, `geo_join_id`, `geo_place_name`, `time_period`, `start_date`, `data_value`, `message` |
| Geography | Neighbourhood and district indicators, including UHF34, community district, and borough. Not a monitor feed. |
| Time | Annual and seasonal means. 2024 values were present. The series is short for deep sequence models. |
| Limits | Modeled surveillance indicators. They must not be described as hourly station readings or as real-time air quality. `message` must be preserved when the publisher suppresses a value. |
| Use | District comparison, change over years, and evidence in cross-domain reports. |
| Class | Available at annual and seasonal grain |

## 8. NYCCAS air-pollution rasters

| | |
| --- | --- |
| Provider | DOHMH |
| Dataset | NYCCAS Air Pollution Rasters |
| Identifier | `q68s-8qxv` |
| Update | Metadata says annually, but `rowsUpdatedAt` converts to 11 May 2017. The view has no column list. |
| Content | Citywide predicted surfaces for NO2, PM2.5, black carbon, nitric oxide, ozone, and sulfur dioxide, as described by the publisher. |
| Limits | Stale catalogue entry and no confirmed download of a raster in this review. |
| Use | Do not build on it until a current file and year are confirmed. |
| Class | Historical only, unverified file |

## 9. EPA Air Quality System files

| | |
| --- | --- |
| Provider | US Environmental Protection Agency |
| Confirmed files | HTTP 200 and a ZIP header on 9 November 2026 |
| Daily PM2.5 | https://aqs.epa.gov/aqsweb/airdata/daily_88101_2024.zip |
| Daily PM10 | https://aqs.epa.gov/aqsweb/airdata/daily_81102_2024.zip |
| Daily NO2 | https://aqs.epa.gov/aqsweb/airdata/daily_42602_2024.zip |
| Daily CO | https://aqs.epa.gov/aqsweb/airdata/daily_42101_2024.zip |
| Daily ozone | https://aqs.epa.gov/aqsweb/airdata/daily_44201_2024.zip |
| Hourly PM2.5 | https://aqs.epa.gov/aqsweb/airdata/hourly_88101_2024.zip (about 66 MB compressed) |
| Geography | Monitoring sites. NYC must be filtered from the national file by state and county, then stored as monitoring locations. |
| Time | Parameter-specific daily values for 2024, plus hourly PM2.5 for 2024. Earlier and later years use the same file pattern and must be checked at ingestion rather than assumed. |
| Limits | Site measurements. Sparse sites cannot be painted across a borough without a documented interpolation and an error statement. Instrument methods and exceptional-event flags need validation. The files were not unpacked in this review, so column use waits for the connector’s schema test. |
| Use | The primary series for air-quality forecasting and station-level anomalies. |
| Class | Available at monitor grain |

## 10. OpenAQ

| | |
| --- | --- |
| Provider | OpenAQ |
| Locations endpoint | `https://api.openaq.org/v3/locations` |
| Measurements | `https://api.openaq.org/v3/sensors/{sensor_id}/measurements` and hourly, daily, and yearly rollups documented at https://docs.openaq.org/ |
| This review | `GET /v3/locations?limit=1&iso=US` returned HTTP 401. |
| Licence | Per-location licence objects. Attribution requirements differ by source. |
| Use | Revisit after a key is available and NYC reference-monitor coverage is counted. EPA remains the primary US source. |
| Class | Unavailable until authenticated and inventoried |

## 11. Open-Meteo historical weather

| | |
| --- | --- |
| Provider | Open-Meteo |
| Endpoint | `https://archive-api.open-meteo.com/v1/archive` |
| Documentation | https://open-meteo.com/en/docs/historical-weather-api |
| Sample | A request for 40.7128, -74.0060 on 1–2 January 2024 returned hourly temperature (°C), relative humidity (%), precipitation (mm), and wind speed (km/h) in `America/New_York`. The returned grid centre was 40.738136, -74.04254, elevation 32 m. |
| Variables | The API exposes a large hourly and daily set, including temperature, humidity, precipitation, rain, wind, cloud cover, and radiation. URBIX should request an explicit variable list. |
| History | Reanalysis, not a sidewalk sensor. Documentation describes multi-decade coverage at up to about 5 km. |
| Licence | Data under CC BY 4.0. The free API tier is for non-commercial use. A commercial deployment needs the customer endpoint and a key. Attribution is required. |
| Limits | Grid snapping must be stored with the series. Do not call a grid cell a monitoring station. The forecast API, if used later, is an external forecast and must be labeled as Open-Meteo output rather than an URBIX model. |
| Use | Weather context, model features, and weather-versus-pollution analysis. |
| Class | Available, gridded |

## 12. DSNY monthly tonnage

| | |
| --- | --- |
| Provider | NYC Department of Sanitation |
| Dataset | DSNY Monthly Tonnage Data |
| Identifier | `ebb7-mvp5` |
| Page | https://data.cityofnewyork.us/City-Government/DSNY-Monthly-Tonnage-Data/ebb7-mvp5 |
| Update | Monthly, for the previous month. `rowsUpdatedAt` converts to 2 November 2026. |
| Confirmed rows | `1990 / 01` and `2026 / 10` were returned. |
| Fields | `month`, `borough`, `communitydistrict`, `refusetonscollected`, `papertonscollected`, `mgptonscollected`, `resorganicstons`, `schoolorganictons`, `leavesorganictons`, `xmastreetons`, `otherorganicstons`, `borough_id` |
| Geography | Borough plus a community-district code that is unique only inside the borough. The key is `(borough_id, communitydistrict)`, mapped to a community-district unit. |
| Limits | Residential and institutional collection tons. Not commercial waste, not a truck route, and not a missed-pickup event. Organics fields are null in older rows. A null organics value is missing, not zero, unless the publisher’s dictionary says otherwise for that year. |
| Use | Monthly generation and recycling trends, district comparison, and one-month-ahead tonnage forecasts. |
| Class | Available at monthly community-district grain |

## 13. Administrative boundaries

All of these are Department of City Planning products on NYC Open Data. Catalogue `updatedAt` for the boundary sets below was 2 November 2026.

| Dataset | Identifier | Sample or schema | Role in the hierarchy |
| --- | --- | --- | --- |
| Borough Boundaries, water excluded | `gthc-hcne` | Sample MultiPolygon for Staten Island. Fields include `borocode`, `boroname`, `the_geom`. | City districts. Also counties. |
| Borough Boundaries, water included | `wh2p-dxnf` | Catalogue record only. | Cartographic alternative. Do not mix areas with the land-only layer. |
| Community Districts | `5crt-au7u` | A feature with `boro_cd` `226` was returned. The geometry was null in a property-only select, so the connector must request `the_geom`. | Charter districts. The analytical parent for sanitation tons. |
| 2020 CDTAs | `xn3r-zk6y` | Columns: `borocode`, `boroname`, `countyfips`, `cdta2020`, `cdtaname`, `cdtatype`, `shape_leng`, `shape_area`, `the_geom`. | Statistical version of community districts. Parent of NTAs. |
| 2020 NTAs | `9nt8-h7nd` | Columns include `nta2020`, `ntaname`, `ntatype`, `cdta2020`, `cdtaname`, `the_geom`. A sample returned Greenpoint `BK0101` inside `BK01`. | Neighbourhood statistical areas. Not official neighbourhood borders. |
| 2020 Census Tracts | `63ge-mke6` | Catalogue record. Shoreline-clipped tracts. | Small-area census geography. |
| 2020 Census Blocks | `wmsu-5muw` | Catalogue record only. | Too fine for the first release. |

NTA metadata documents real topology exceptions. Bronx Community District 8 crosses into Manhattan. Rikers Island is coded with a Queens CDTA and a Bronx borough. The hierarchy therefore cannot be a strict containment tree. Relationships need a type and a note.

Class: available.

## 14. Population tables currently reachable without a Census key

| Dataset | Identifier | What was found | Class |
| --- | --- | --- | --- |
| Population by community district | `xi7c-iiu2` | One Bronx CD row contained population columns for 1970, 1980, 1990, 2000, and 2010. No later census year was in that row. | Historical only |
| Population by NTA | `swpk-hqdp` | Catalogue description says decennial SF1. `updatedAt` is 8 February 2020, before the 2020 census publication used by later products. | Historical only, likely 2010 geography |
| Census demographics at NTA | `rnsn-acs2` | Catalogue record, last updated 8 February 2020. | Historical only |
| Population by borough, 1950–2040 | `xywu-7bv9` | Columns run from 1950 through 2040. The publisher says unadjusted census data for 1950–2000 and projected figures for 2010–2040. | Mixed. Later years are projections and must be labeled as projections. |
| US Census ACS 5-year API | `https://api.census.gov/data/2023/acs/acs5` | The New York County probe returned HTML titled “Missing Key”. | Unavailable until a free key is configured |
| WorldPop USA | `https://www.worldpop.org/rest/data/pop/wpgp?iso3=USA` | 21 GeoTIFF layers, about 100 m, people per pixel, WGS84. Years through 2020 are listed. The 2020 record (`id` 6545, DOI `10.5258/SOTON/WP00645`) has dataset date 1 November 2018, so it is an estimate produced before the 2020 census. Licence text at https://hub.worldpop.org/data/licence.txt is CC BY 4.0. | Available as a gridded estimate, not as an official count |

Official current small-area population is the weakest major domain. Phase 3 should add a Census key and load decennial PL 94-171 or ACS at tract level, then aggregate with the NTA equivalency. Until then the population module shows boundaries, clearly labeled historical counts, clearly labeled projections, and an optional WorldPop estimate layer. It does not invent a 2026 neighbourhood census.

## 15. PLUTO

| | |
| --- | --- |
| Provider | NYC Department of City Planning |
| Dataset | Primary Land Use Tax Lot Output (PLUTO) |
| Identifier | `64uk-42ks` |
| Update | Catalogue `updatedAt` 24 August 2026. |
| Schema | Read from view metadata. Includes `borough`, `block`, `lot`, `cd`, `bbl`, `address`, `landuse`, `bldgclass`, `lotarea`, `bldgarea`, `numfloors`, `unitsres`, `unitstotal`, `yearbuilt`, `latitude`, `longitude`, `geom`, zoning fields, and `ownername`. |
| Limits | A data row was not retrieved; a broad query returned HTTP 503. `ownername` is excluded from the public API. `unitsres` is a housing-unit count, not a resident count. Version and source dates are part of the row and must be kept. |
| Use | Land use, residential capacity, building age, and infrastructure context. |
| Class | Available after a bulk load |

## 16. Building footprints

| | |
| --- | --- |
| Provider | City of New York |
| Dataset | BUILDING |
| Identifier | `5zhs-2jue` |
| Documentation | https://github.com/CityOfNewYork/nyc-geo-metadata/blob/master/Metadata/Metadata_BuildingFootprints.md |
| Update | Catalogue `updatedAt` 8 November 2026. |
| Fields | `the_geom`, `name`, `bin`, `doitt_id`, `shape_area`, `base_bbl`, `construction_year`, `feature_code`, `geom_source`, `ground_elevation`, `height_roof`, `last_edited_date`, `last_status_type`, `mappluto_bbl`, `shape_length` |
| Companion sets | `u9wf-3gbt` BUILDING_P and `ipkp-snf6` BUILDING_HISTORIC were catalogue hits only. |
| Limits | Citywide polygons are large. The first map should use vector tiles or generalised zoom rules, not a single GeoJSON dump. |
| Use | Building distribution, height, footprint density, and joins to PLUTO through BBL. |
| Class | Available |

## 17. MTA subway geography and ridership

| Dataset | Identifier | Host | What was confirmed |
| --- | --- | --- | --- |
| MTA Subway Stations | `39hk-dx4f` | data.ny.gov | A station row with GTFS stop id, complex id, line, borough, daytime routes, structure, coordinates, and ADA flags. Catalogue update 8 November 2026. |
| MTA Subway Stations and Complexes | `5f5g-n3cz` | data.ny.gov | Catalogue record. Aggregate geometry for complexes. |
| MTA Subway Station Complexes | `4ta5-wz5s` | data.ny.gov | Catalogue record. |
| Hourly ridership, beginning 2025 | `5wq4-mkjj` | data.ny.gov | Rows include `transit_timestamp`, complex id, complex name, borough, payment method, fare class, `ridership`, `transfers`, and coordinates. Catalogue update 4 November 2026. An unordered sample was 23 May 2025. A query ordered by `transit_timestamp` descending returned 29 October 2026, 23:00, at 18 Av (F) in Brooklyn. |
| Hourly ridership, 2020–2024 | `wujg-7c2s` | data.ny.gov | Catalogue record, updated 10 March 2026. |
| Hourly ridership, 2017–2019 | `t69i-h2me` | data.ny.gov | Catalogue record. |
| Monthly ridership | `ak4z-sape` | data.ny.gov | Catalogue record, beginning February 2017. |

Resource pattern: `https://data.ny.gov/resource/{id}.json`.

Ridership fields observed on the 2025 feed: `transit_timestamp`, `transit_mode`, `station_complex_id`, `station_complex`, `borough`, `payment_method`, `fare_class_category`, `ridership`, `transfers`, `latitude`, `longitude`, `georeference`.

Limits: estimates by fare class, not turnstile audits. Summing fare classes without grouping will double-count a complex. Transfers are a separate measure. The three hourly datasets must be normalised and deduplicated at the seams.

Use: the strongest forecasting problem in the first release. Horizons of 1, 6, and 24 hours match the hourly grain. Also coverage, ADA flags, and complex-level demand.

Class: available.

## 18. MTA GTFS

| | |
| --- | --- |
| Provider | MTA New York City Transit |
| Regular subway GTFS | https://rrgtfsfeeds.s3.amazonaws.com/gtfs_subway.zip |
| Supplemented GTFS | https://rrgtfsfeeds.s3.amazonaws.com/gtfs_supplemented.zip |
| Developer page | https://www.mta.info/developers |
| Terms | https://www.mta.info/developers/terms-and-conditions |
| External index | Transitland records feed `f-dr5r-nyctsubway`, publisher MTA, a version fetched 29 October 2026, and service dates 1 November 2026 through 15 May 2027. |
| This review | The zip was not downloaded or parsed. |
| Terms that affect design | URBIX must host the feed on its own server. The application must not read through to MTA servers for each user. Data is as-is. A lag of more than one minute on any future real-time feed must be disclosed. |
| Bus, rail, and GTFS-RT | Listed by MTA as separate feeds. They are deferred until each URL is fetched and parsed. |
| Use | Stops, routes, shapes, and calendars for the subway accessibility graph. |
| Class | Published and indexed. Connector not yet tested. |

## 19. Bus and ferry

| Dataset | Identifier | Status |
| --- | --- | --- |
| MTA Bus Hourly Ridership, beginning 2025 | `gxb3-akrn` on data.ny.gov | Catalogue record. Route and fare class, not stop geography. |
| Bus ridership 2020–2024 and 2017–2019 | `kv7t-n8in`, `98u6-vmgs` | Catalogue records. |
| NYC Ferry Ridership | `t5n6-gx8c` | Catalogue says hourly boardings by route, direction, and landing. A data request returned HTTP 503. |
| Bus stop shelters | `t4f2-8md7` | Shelter locations, not the full stop network. |

Class: partial. GTFS is the source for stop geography. Route-level boardings can support route demand, not a stop-level map, unless joined through a documented assignment.

## 20. Global boundary and basemap services

| Source | What was confirmed | Use |
| --- | --- | --- |
| geoBoundaries | `https://www.geoboundaries.org/api/current/gbOpen/USA/ADM1/` returned JSON with `boundaryID` `USA-ADM1-66186276`. | First source for reusable country and admin-region geometry. Other ISO codes and ADM0 still need a connector test. |
| OpenFreeMap dark style | `https://tiles.openfreemap.org/styles/dark` returned a MapLibre style document, version 8. | Basemap without a proprietary token. OSM attribution is required. Licence text for the tile service still needs to be stored in `data_sources` during Phase 2. |

OpenStreetMap, through OSMnx and Overpass, remains the planned source for walk networks, roads, and points of interest. No Overpass extract was run in this review. OSM data is ODbL. Extracts must be modest, cached, and attributed.

## 21. Sources investigated and not adopted

| Source | Result |
| --- | --- |
| NYC DEP as a separate real-time air API | No verified real-time station API was found. DOHMH indicators and EPA AQS cover the environmental module more honestly. |
| NYCCAS rasters | Catalogue entry is stale and has no columns. |
| WorldPop as the NYC population authority | Useful global fallback. The listed 2020 USA layer predates the census. |
| DOT speeds as a historical training set | The publisher does not provide the history. |
| Complaint coordinates as a public map layer | Too fine, and contaminated by reporting bias. Aggregate first. |

## Ingestion order after approval

1. Boroughs, community districts, CDTAs, NTAs, and a USA admin-region boundary.
2. Subway stations and the GTFS zip, once parsed in a connector test.
3. DSNY tonnage.
4. DOHMH air indicators.
5. EPA 2024 daily files, filtered to NYC counties, then hourly PM2.5.
6. Open-Meteo hourly history at a documented set of grid points.
7. Collisions.
8. Complaint aggregates, after a restricted raw landing zone and date checks.
9. Building footprints and PLUTO.
10. ATR counts.
11. A scheduled archive of DOT speed snapshots, starting the day the worker runs. No backfill is claimed.
