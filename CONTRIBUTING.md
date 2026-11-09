# Contributing

Keep connectors, analytical services, model training, and the interface in their own packages. A route handler should call a service, and a service should read stored rows rather than invent a number.

Before adding a dataset:

1. Record the live endpoint, fields, geography, time coverage, licence, and the limitation that matters.
2. Put that record in `data-engine/urbix_data/catalog.py`.
3. Map source fields explicitly. Do not persist complaint demographics.
4. Preserve nulls.
5. If the extract is capped, store that fact on the ingestion job.

Model metrics belong in `model_evaluations` and must come from a chronological test fold. Do not commit fabricated scores.

Do not commit `.env`, database files, or model artifacts.
