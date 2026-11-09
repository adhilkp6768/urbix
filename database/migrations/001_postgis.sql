-- PostGIS geometry columns and indexes.
-- Applied only on PostgreSQL, one statement at a time.
-- The final pgvector extension is optional and may be skipped.

CREATE EXTENSION IF NOT EXISTS postgis;

ALTER TABLE geo_units ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 4326);

CREATE INDEX IF NOT EXISTS geo_units_geom_gix ON geo_units USING GIST (geom);

ALTER TABLE traffic_observations ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 4326);

CREATE INDEX IF NOT EXISTS traffic_obs_geom_gix ON traffic_observations USING GIST (geom);

CREATE INDEX IF NOT EXISTS traffic_obs_time_idx ON traffic_observations (observed_at);

ALTER TABLE environmental_observations ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326);

CREATE INDEX IF NOT EXISTS env_obs_geom_gix ON environmental_observations USING GIST (geom);

ALTER TABLE crime_incidents ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326);

CREATE INDEX IF NOT EXISTS crime_incidents_geom_gix ON crime_incidents USING GIST (geom);

ALTER TABLE transit_stops ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326);

CREATE INDEX IF NOT EXISTS transit_stops_geom_gix ON transit_stops USING GIST (geom);

ALTER TABLE infrastructure_features ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 4326);

CREATE INDEX IF NOT EXISTS infra_geom_gix ON infrastructure_features USING GIST (geom);

ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS search_vector tsvector;

CREATE INDEX IF NOT EXISTS knowledge_documents_fts ON knowledge_documents USING GIN (search_vector);

CREATE EXTENSION IF NOT EXISTS vector;
