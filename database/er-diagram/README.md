# Entity relationships

```mermaid
erDiagram
  GEO_UNITS ||--o{ GEO_UNITS : parent
  DATA_SOURCES ||--o{ DATASETS : publishes
  DATASETS ||--o{ INGESTION_JOBS : loaded_by
  DATASETS ||--o{ DATA_QUALITY_CHECKS : checked_by
  GEO_UNITS ||--o{ TRAFFIC_OBSERVATIONS : locates
  GEO_UNITS ||--o{ ENVIRONMENTAL_OBSERVATIONS : locates
  GEO_UNITS ||--o{ WEATHER_OBSERVATIONS : locates
  GEO_UNITS ||--o{ POPULATION_OBSERVATIONS : locates
  GEO_UNITS ||--o{ WASTE_OBSERVATIONS : locates
  GEO_UNITS ||--o{ TRANSIT_STOPS : locates
  MODEL_VERSIONS ||--o{ MODEL_EVALUATIONS : scored_by
  MODEL_VERSIONS ||--o{ PREDICTIONS : emits
  INVESTIGATIONS ||--o{ AGENT_RUNS : traces
  INTELLIGENCE_REPORTS ||--o{ REPORT_EVIDENCE : cites
```

Primary keys are UUIDs on registry tables and integers on observation tables. Natural deduplication uses `(dataset_code, source_row_id)`. Spatial columns live in the PostGIS migration rather than the portable ORM, because SQLite has no geometry type. Time columns are indexed on traffic, environment, weather, waste, and ridership.

Crime incidents intentionally have no demographic columns. Population rows carry `metric_kind` so a 2010 count cannot be confused with an ACS estimate.
