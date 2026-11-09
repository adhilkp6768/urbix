# AI strategy

The language model is an interface to verified tools. It is not the source of a statistic, a geography, or an event. Most of an investigation is ordinary Python over the same services the API uses.

## Division of work

| Step | Implementation | Why |
| --- | --- | --- |
| Resolve a name to a unit | Deterministic search over units and aliases, with a threshold | A model should not guess which Brooklyn geography was meant when several match |
| Parse an open question into a plan | LLM, constrained to a Pydantic schema | The wording varies. The plan does not. |
| Check coverage and grain | Deterministic | Stops unavailable domains before any prose |
| Aggregate, compare, rank, buffer, join | Deterministic SQL and GeoPandas behind typed tools | Numbers must be reproducible |
| Forecast and anomaly lookup | Deterministic read of `predictions` and `anomalies` | The model already ran |
| Method and dataset explanation | Retrieval over curated documents | Citations have URLs and versions |
| Cross-domain test | Deterministic statistical routine | Correlation, lag, and sample size are computed |
| Narrative | LLM, restricted to the tool payload | Language, not measurement |
| Numeric audit | Deterministic checker | Rejects figures that are not in the payload |
| Refusal | Deterministic policy | Individual criminality, unsupported grain, missing data |

If a step has a stable rule, it is Python. The model is used where language is the input or the output.

## Orchestrator

One LangGraph workflow is enough at the start. Separate agent personas are not separate processes.

Nodes:

1. `plan` — produce `InvestigationPlan`: domain list, place text, time range, operation, and whether a prediction was requested.
2. `resolve_place` — bind zero, one, or many units. Ambiguity returns a clarification instead of a silent choice.
3. `check_coverage` — drop domains that are unavailable and record the drop.
4. `analyse` — call the tool list on the plan.
5. `retrieve` — optional knowledge search for definitions and limitations.
6. `compose` — write sections: observations, comparisons, predictions, associations, hypotheses, limits.
7. `audit` — verify numbers and required sections.

Specialised nodes for traffic, environment, or reports are added when a single prompt starts mixing policies. The tools are already separated, which is the part that matters.

The graph uses a read-only database role. It has no tool that accepts SQL, a shell command, or a URL from the model.

## Tools

Each tool has a schema, a service function, and a test.

| Tool | Returns |
| --- | --- |
| `resolve_geography` | Matching units, types, and ambiguity |
| `get_coverage` | Status, grain, time span, dataset version, limitations |
| `query_series` | Aggregates for an allow-listed variable, unit, and time bucket |
| `compare_periods` | Two windows, the same variable, the difference, and the sample size |
| `compare_units` | The same variable across named units |
| `spatial_summary` | Area, count, density, or nearest-facility result computed by PostGIS |
| `accessibility` | Share of an area within a stated walk time of a transit stop |
| `get_predictions` | Promoted predictions, horizon, interval, model version, metric summary |
| `get_anomalies` | Detector, time, residual, and the series id |
| `search_knowledge` | Passages with document id and citation |

`query_series` allow-lists variable codes such as `refuse_tons`, `subway_ridership`, `pm25_monitor_daily`, `pm25_neighbourhood_annual`, and `collision_count`. It rejects a request that asks for a finer grain than the dataset version records.

There is no `execute_sql` tool and no tool that returns raw complaint rows.

## How a congestion question is answered

“Why has traffic congestion increased in this district?”

1. Bind “this district” to the selected unit. If the user said a neighbourhood name, resolve the NTA and state that it is a statistical area.
2. Read traffic coverage. For an NTA, ATR coverage will usually be partial. The answer says which segments were counted and which hours exist. It does not average a handful of segments into “the district’s congestion” without showing the sample.
3. If only a speed snapshot exists, say that historical speed is unavailable. Do not infer a trend from one snapshot.
4. Where a repeated ATR series exists, `compare_periods` returns the two windows.
5. Weather for those windows is retrieved as a covariate, with the grid centre.
6. Predictions are included only if a promoted model covers that segment and horizon.
7. The composer may say that the count changed, that weather differed, and that the data cannot establish a cause. A road closure or an event is mentioned only when a verified dataset contains it. None does today, so the hypothesis section says the platform has no event dataset.

## Natural-language querying

Examples from the product brief map to tools as follows.

| Question | Plan |
| --- | --- |
| Which NYC districts have the highest population density? | Coverage check. If only historical or projected population is loaded, the answer names that vintage and refuses a “current” ranking. |
| Compare air quality in Brooklyn and Manhattan. | `compare_units` on a declared indicator, such as DOHMH annual PM2.5 for a stated year. Borough is the matching grain. |
| Where is transit coverage poor? | `accessibility` with the threshold shown in the answer. |
| Unusual traffic in the last month | `get_anomalies` on eligible ATR series. Segments without a baseline are listed as not assessed. |
| Largest increase in PM2.5 | `compare_periods` at the grain that exists. A neighbourhood annual change is not described as an hourly spike. |
| Weekday versus weekend traffic | `compare_periods` or a calendar split on ATR segments that have both day types. |

The planner emits the tool call. It does not emit a filter expression that the database executes directly. Time zones are normalised before the query.

Unsupported questions return a reason: unknown place, unavailable dataset, prohibited target, or grain the data does not have. The composer is not allowed to fill the gap with a general statement about cities.

## Cross-domain analysis

Allowed early tests, each with a minimum sample size:

- Hourly monitor PM2.5 against the same hours of weather at that monitor’s grid cell.
- Hourly subway ridership against weather.
- Annual neighbourhood NO2 or PM2.5 against a static measure available for the same geography, such as building density or a transit-access share, for one stated year.

The implementation computes a rank correlation or a simple regression with the sample size, the period, and the grain. The result is an association. The report template contains the sentence that the test does not identify a cause. If the sample is below the minimum, the tool returns “not computed” and the reason.

Traffic-versus-pollution is deferred until both series share a real overlapping time and place. A 15-minute ATR sample and an annual neighbourhood mean do not overlap usefully. The agent must not join them into a single chart that implies they do.

## RAG

The corpus is written by the project, not scraped from the open web at question time.

- Dataset cards generated from `datasets` and `dataset_versions`.
- Methodology notes for accessibility, aggregation, and each promoted model.
- Model cards pointing at evaluation ids.
- Short limitation pages, including the public-safety policy.

pgvector stores chunks. Retrieval returns the passage and the document id. The composer cites those ids. RAG is not used to answer “what was ridership last Tuesday”. That question goes to `query_series`. If retrieval and a tool disagree, the tool wins and the conflict is logged.

## Reports

A report is a stored object:

- Title, city, unit, period.
- Dataset versions and model versions.
- Observations and comparisons, copied from tools.
- Anomalies and predictions, copied from tools.
- Associations, with sample size.
- Hypotheses, explicitly separate.
- Methodology and limitations.
- Evidence ids.

The language model writes the connecting prose after the object exists. The audit step checks numbers. A report can be rendered without the prose. The prose cannot be rendered without the object.

## Provider configuration

`LLM_PROVIDER`, `LLM_MODEL`, and the provider key are environment variables. The graph depends on a small client interface: structured plan, prose, and embeddings. Tests use a fake client that returns a fixed plan so tool behaviour is tested without a network call. A live provider test is optional and is not required for a build to pass.

## Evaluation of the agent

- Tool tests assert SQL parameters and coverage failures.
- A set of questions with known database fixtures asserts the plan and the cited numbers.
- A hallucination check feeds a payload and a draft that adds a number, and expects audit failure.
- A prohibited-question set covers individual offending, exact complaint lookup, and a demand to treat a correlation as a cause.
- Retrieval tests check that a dataset-card question cites the right document and that a numeric question does not call retrieval first.
