# URBIX

Global urban intelligence platform. Understand a city from stored evidence, and leave a field blank when the evidence is not there.

New York City is the deep reference city: traffic, air, waste, transit, safety, population, and buildings. Twenty-three other cities carry a week of weather and modelled air quality, and a city boundary when OpenStreetMap published one close to the reference point. A city with no successful extract stays in the registry and shows no indicators.

## What you can open

| Surface | Address |
| --- | --- |
| Command centre | `/cities/nyc` |
| Map | `/cities/nyc/map` |
| City menu | header selector, after at least one city has an extract |
| Compare | `/compare` |
| Phone | `/m` |

The phone surface is the same site in a full-screen layout: Pulse, Map, Explore, and Ask. Add it to the home screen from the browser. It is not an App Store binary.

## What is loaded

Checked against the live sources on 9 November 2026. Large New York tables are capped. The ingestion job records the cap. Missing measurements stay null.

**Every registered city.** Open-Meteo archive weather (`temperature_2m`, humidity, precipitation, wind) and the CAMS air-quality grid (`pm2_5`, `pm10`, nitrogen dioxide, carbon monoxide) for 2–9 November 2026. These are grid-cell hours at the stored coordinate, not a citywide average and not a regulatory monitor.

**City boundary.** OpenStreetMap via Nominatim, kept only when the polygon centroid stays near the reference point. Tokyo, Mumbai, and Cape Town did not return a polygon that passed that check, so the map marks them with a point.

**New York only.**

| Extract | What it is |
| --- | --- |
| Borough, community-district, CDTA, and NTA polygons | Official NYC boundary files |
| DOT link speeds | Latest snapshot, not a historical archive and not a free-flow index |
| ATR counts | Bounded sample, not every road-hour |
| NYPD crashes and year-to-date complaints | Reported events. Suspect and victim demographics are not stored |
| DOHMH air indicators | Annual or seasonal neighbourhood estimates through the published period |
| DSNY tonnage | District refuse for the loaded months |
| Population by community district | Decennial counts through 2010 |
| MTA subway GTFS and hourly ridership | Static feed plus a short ridership window. Not live train positions |
| PLUTO groups and shelter buildings | Tax-lot aggregates and shelter facilities, not the whole building stock |
| OSM motorways and trunks | A bounded Overpass extract |

Census ACS and OpenAQ stay unloaded unless `CENSUS_API_KEY` and `OPENAQ_API_KEY` are set. WorldPop rasters, NYCCAS raster files, and opaque population-projection columns are catalogued and not presented as current measurements.

## Cities

United States: New York City, Chicago, Los Angeles.  
Canada: Toronto. Mexico: Mexico City. Brazil: São Paulo.  
United Kingdom: London. Netherlands: Amsterdam. Germany: Berlin, Trier.  
France: Paris. Spain: Madrid. Italy: Rome. Sweden: Stockholm.  
Singapore. Japan: Tokyo. South Korea: Seoul. India: Mumbai.  
United Arab Emirates: Dubai. Egypt: Cairo. Kenya: Nairobi. Nigeria: Lagos.  
South Africa: Cape Town. Australia: Sydney.

Coordinates in the registry are reference points. A stored boundary replaces the centroid after Nominatim returns an acceptable polygon.

## Stack

- **frontend** — Next.js 14, React 18, MapLibre, ECharts, Tailwind.
- **backend** — FastAPI. The browser talks to Next, and Next proxies `/api` to the API.
- **data-engine** — connectors, the dataset catalog, and bootstrap.
- **ml-engine** — chronological train/test splits. A forecast is withheld when the extract is too short.
- **ai-engine** — an investigation graph that can only call approved tools. With no model key, a rule planner chooses the tools. Numbers in an answer have to appear in the tool evidence.
- **database** — SQLAlchemy. SQLite is the local database. PostgreSQL with PostGIS is the deployment database.

## Run it locally

Python 3.12 and Node 22 are the intended versions.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements/base.txt -r requirements/ml.txt -r requirements/ai.txt -r requirements/dev.txt
cp .env.example .env
export PYTHONPATH=backend:data-engine:ml-engine:ai-engine:database
python -m urbix_data.bootstrap
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

The first bootstrap loads the New York extracts and weather for New York. To load weather and air for every registered city, and city boundaries where Nominatim has one:

```bash
export PYTHONPATH=backend:data-engine:ml-engine:ai-engine:database
python -m urbix_data.bootstrap --only open-meteo-weather --only open-meteo-air-quality --expand-weather
python -m urbix_data.bootstrap --only osm-city-boundary --expand-weather
```

`osm-city-boundary` runs once per call for the city in its options. The bootstrap entry point seeds geography and then runs the connector with the weather-city list only for the Open-Meteo connectors. For a single boundary:

```bash
python -c "from urbix_data.pipeline import run_connector; from urbix_db.session import make_session_factory; s=make_session_factory()(); print(run_connector(s,'osm-city-boundary',{'city':'paris'})); s.commit()"
```

In another shell:

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL= API_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Leave `NEXT_PUBLIC_API_URL` empty so the browser calls the same origin. `API_URL` is the server-side proxy target. Open [http://127.0.0.1:3000/cities/nyc](http://127.0.0.1:3000/cities/nyc).

The default database file is `urbix.db` at the repository root. It is gitignored. A fresh clone has the connectors and no measurements until bootstrap runs.

## Environment

Copy `.env.example`. Empty keys are valid.

| Variable | Role |
| --- | --- |
| `DATABASE_URL` | `sqlite:///./urbix.db` locally. `postgresql+psycopg://...` for Postgres. A `postgres://` URL is rewritten for Psycopg. |
| `URBIX_API_KEY` | When set, POST routes require the `x-api-key` header. Empty allows local writes. |
| `OPENAI_API_KEY` | Optional. Empty uses the rule planner. |
| `OPENAI_BASE_URL`, `OPENAI_MODEL` | OpenAI-compatible chat settings. |
| `OPENAQ_API_KEY` | Station list. Without it, the OpenAQ connector stops and says the key is missing. |
| `CENSUS_API_KEY` | Optional. The Census API also returns a key error without one. |
| `CORS_ORIGINS` | Browser origins that call the API host directly. Same-origin Next proxy traffic does not need this. |
| `URBIX_REFRESH_HOURS` | `0` locally. On a server, hours between current-extract refreshes. |
| `URBIX_BOOTSTRAP_ON_START` | `0` locally. `1` runs the full reference load when the database has no successful job. |

## API

Base path `/api/v1`.

- `GET /health`
- `GET /geography/world`, `/geography/countries`, `/geography/countries/{code}/cities`, `/geography/search?q=`
- `GET /cities/{slug}/overview`
- `GET /maps/geojson?city={slug}&layer={admin|traffic|environment|waste|transit|roads|population|crime}`
- `GET /traffic/trends`, `/environment/trends`, `/crime/analytics`, `/population/analytics`, `/transport/analytics`, `/waste/analytics`, `/infrastructure/analytics` — each accepts `?city=`
- `GET /compare?left={slug}&right={slug}`
- `POST /ai/query` with `{ "question", "city" }`
- `POST /ai/reports` with `{ "city" }`
- `GET /connectors` and `POST /connectors/{code}/run`
- `POST /system/refresh` with `{ "scope": "current" | "full" }`
- `GET /system/freshness`, `/alerts`, `/models`, `/data-quality`, `/data-sources`

`scope=current` refreshes speeds, counts, crashes, complaints, air, waste, weather, ridership, and shelter buildings. `scope=full` also loads boundaries, GTFS, roads, and the rest of the reference sequence. A failed source stays failed.

## Tests

```bash
source .venv/bin/activate
pytest
cd frontend && npm run typecheck
```

`pytest.ini` puts `backend`, `data-engine`, `ml-engine`, `ai-engine`, and `database` on the Python path.

## Docker and cloud

```bash
docker compose up --build
```

Compose starts PostGIS, the API on port 8000, and the web app on port 3000. `database/migrations/001_postgis.sql` adds geometry columns and GIST indexes. The stock PostGIS image has no pgvector; retrieval stays lexical, and embeddings are stored as JSON only when an embedding provider is configured later.

`render.yaml` is a Render blueprint for Postgres, the API image, and the web image. It is not already deployed. On Render, keep `NEXT_PUBLIC_API_URL` empty and set the web service's `API_URL` to the API origin. Set `URBIX_BOOTSTRAP_ON_START=1` and `URBIX_REFRESH_HOURS=12` on the API.

## Docs

- [Feasibility](docs/architecture/phase-1-overview.md)
- [System architecture](docs/architecture/system-architecture.md)
- [Database design](docs/architecture/database-design.md)
- [New York dataset inventory](docs/datasets/nyc-inventory.md)
- [ML strategy](docs/architecture/ml-strategy.md)
- [AI strategy](docs/architecture/ai-strategy.md)
- [Frontend strategy](docs/architecture/frontend-strategy.md)
- [Implementation plan](docs/architecture/implementation-plan.md)

## Limits

- No individual crime prediction. Complaint points are not drawn as hotspots.
- Traffic speed is the current DOT snapshot. URBIX does not reconstruct speeds from before collection started.
- Open-Meteo’s free API is for non-commercial use. Attribution is required for OpenStreetMap and OpenFreeMap.
- The local SQLite file and `.env` are not part of the git history.

See [CONTRIBUTING.md](CONTRIBUTING.md) before adding a dataset.
