# Implementation plan

Phase 1 is this document set. Later phases start only after the approval gate in the overview. Each phase ends with a written summary of files, decisions, tests, gaps, and the next step. A phase does not silently begin the next one.

## Repository

```text
urbix/
├── frontend/                 # Next.js application
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   ├── core/
│   │   ├── geography/
│   │   ├── domains/
│   │   ├── services/
│   │   ├── schemas/
│   │   └── main.py
│   └── tests/
├── data-engine/
│   ├── connectors/
│   ├── pipelines/
│   ├── validation/
│   └── schemas/
├── ml-engine/
│   ├── ridership/
│   ├── waste/
│   ├── environment/
│   ├── traffic/
│   ├── safety/
│   └── common/
├── ai-engine/
│   ├── workflows/
│   ├── tools/
│   ├── rag/
│   └── prompts/
├── database/
│   ├── migrations/
│   └── seeds/
├── infrastructure/docker/
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
```

`ml-engine/traffic` stays empty of a speed model until the archive exists. `ai-engine` does not gain one folder per persona.

## Dependencies, introduced when first used

| Phase | Add |
| --- | --- |
| 2 | Next.js, React, TypeScript, Tailwind, shadcn/ui, MapLibre, FastAPI, Pydantic, SQLAlchemy, Alembic, GeoAlchemy2, psycopg, Redis, Celery, Docker images for PostGIS 16 and Redis |
| 3 | GeoPandas, Shapely, pyarrow, polars, duckdb, httpx, H3 |
| 4 | ECharts, vector-tile generation |
| 5 | scikit-learn, LightGBM, MLflow. XGBoost when a comparison needs it. PyTorch only if an LSTM is actually trained. SHAP with the first tree model. |
| 6 | LangGraph, the chosen LLM client, pgvector, an embedding client |
| 3, as needed | OSMnx for a bounded walk-network extract |

Libraries are not installed “for the architecture”. OSMnx, PyTorch, and a graph-network library wait for the milestone that uses them.

## Environment

`.env.example` will list names and not values.

| Variable | Required from |
| --- | --- |
| `DATABASE_URL` | Phase 2 |
| `REDIS_URL` | Phase 2 |
| `NYC_OPENDATA_APP_TOKEN` | Phase 3, optional but recommended |
| `CENSUS_API_KEY` | Before official small-area population |
| `OPENAQ_API_KEY` | Before any OpenAQ connector |
| `OPEN_METEO_API_KEY` | Only for commercial use of Open-Meteo |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` | Phase 6 |
| `MLFLOW_TRACKING_URI` | Phase 5 |

Open-Meteo’s free archive endpoint needs no key for non-commercial research. The dataset record will still say that a commercial deployment must switch endpoints.

## Milestones

### Phase 2 — foundation

- Monorepo, Compose, API health check, frontend shell, design tokens, and the geographical tables.
- Seed continents and countries only after the geoBoundaries connector test passes for more than the USA ADM1 call already made. Until then, seed USA, New York State, and New York City as units with an explicit source note, plus the NYC boundary layers.
- Empty versioned routes that return a typed unavailable payload.
- Test: Compose boots, migrations apply, a borough polygon round-trips through PostGIS, the shell renders loading and empty states.

No observation data and no model.

### Phase 3 — data

- Connectors in the ingestion order listed in the dataset inventory.
- GTFS is a separate test: download, parse, and count stops before the transport API is marked ready.
- Quality checks for impossible dates, null geometries, duplicate keys, and missing speed statuses.
- Coverage rows for every dataset version.
- Test: a fixture or a small live extract validates schema, and a second run does not duplicate rows.

### Phase 4 — map and city workspace

- Global, country, city, and district pages bound to real units.
- Layer registry, tooltips, time control, and coverage banners.
- Building footprints as tiles, not one GeoJSON.
- Test: selecting an NTA shows its name from PostGIS; an unavailable layer explains itself; mobile and desktop layouts both open the city page.

### Phase 5 — models

- Ridership, waste, and monitor PM2.5 pipelines, each with a baseline.
- Registry, evaluations, and prediction reads.
- Speed archive job starts, without a speed model.
- Test: leakage test, chronological split test, and a test that the API hides a model with no evaluation.

### Phase 6 — agent

- Orchestrator, tools, knowledge cards, numeric audit, investigation and report storage.
- Test: fixture questions, prohibited questions, and a forged-number audit failure.

### Phase 7 — operations

- Quality and anomaly views, report library, and alerts for failed jobs and promoted anomalies.
- Test: a failed connector creates a visible quality record and does not change coverage to available.

### Phase 8 — another city

- A second connector set, chosen after the same verification used for NYC. Singapore, Amsterdam, London, Berlin, and Trier are candidates, not commitments.
- Test: NYC tests still pass and the new city cannot see NYC dataset versions as its own.

### Phase 9 — production hardening

- Authentication, rate limits, CI, logging, backup, and performance passes on ridership and footprints.
- Test: the agent role cannot read `restricted`, and secrets are absent from the frontend bundle.

## Testing strategy

| Area | First tests |
| --- | --- |
| Geography | Relationship queries, Marble Hill and Rikers notes preserved, area is non-zero |
| API | Pagination, null behaviour, coverage short-circuit, OpenAPI schema |
| Connectors | Schema contract, watermark, duplicate key, dirty date |
| Map UI | Layer toggle, empty layer, district selection |
| ML | Baseline present, future row rejected, metric tied to a dataset version |
| Agent | Tool arguments, citation, numeric audit, prohibited targets |

Frontend interaction tests use a running API or a recorded contract. A screenshot is not the test.

## Deployment

Local Compose is the deployment for Phases 2 through 6. GitHub Actions runs unit tests and image builds once those tests exist. A hosted environment waits until authentication and backup are defined. Logs go to the worker and API stdout, with job failures also written to `system_logs`.

## Risks

| Risk | Response |
| --- | --- |
| Socrata HTTP 503 and the 1,000-row cap | Export downloads, tokens, retries, watermarks |
| Stale publisher descriptions | Trust sampled fields and store the description as publisher text, not as verified coverage |
| Boundary exceptions | Typed relationships with notes |
| NYC licence field empty | Store terms URL and “as-is” on the source |
| Census and OpenAQ authentication | Leave the domain unavailable |
| Open-Meteo non-commercial API | Record the restriction; do not hide it in the UI |
| MTA proxy prohibition | Cache feeds in URBIX |
| No speed history | Archive forward; no backfilled forecast |
| ATR sparsity | Eligibility rule before training |
| Crime misuse | Aggregates only, no demographic features, no individual target |
| PLUTO owner names and complaint coordinates | Drop or restrict before the public schema |
| Large footprints and hourly ridership | Tiles, BRIN indexes, incremental loads |
| Agent invention | Tool-only numbers and an audit node |
| Scope creep into a live digital twin | Coverage states and the promotion rules |

## Recommended next task

After approval, implement Phase 2 only: the repository skeleton, Compose, migrations for geography and data-management tables, a health check, and the application shell with an empty NYC place picker. Do not load ridership or train a model in that change.
