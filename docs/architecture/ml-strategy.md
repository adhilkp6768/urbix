# Machine learning strategy

No model has been trained. This document defines the problems the verified data can support, the baselines they must beat, and the problems that wait. Metrics will be produced by the evaluation job and stored in `model_evaluations`. They are not estimated here.

## Rules for every pipeline

- The target, horizon, and grain are declared before training.
- The split is chronological. Random row splits are not used on these series.
- Features at time *t* may use observations at or before *t* and known calendar fields. They may not use the target, a future weather observation, or a future ridership hour.
- A baseline is trained or computed on the same split.
- A model is promoted only when the evaluation record exists. Beating the baseline is the promotion rule for the first three pipelines. The margin can be zero at first, meaning “strictly better MAE on the test period”, and should be revisited after the first real scores.
- The API exposes a horizon only when that horizon was evaluated.
- SHAP is computed for tree models on a sample of the test period and stored with the version. It is an explanation of the model, not a causal claim.
- MLflow records the dataset version, feature spec, parameters, and metrics. The model file stays in MLflow’s artifact store. PostgreSQL stores the registry pointer.

## Pipeline 1 — subway complex hourly ridership

This is the first forecasting model.

| | |
| --- | --- |
| Target | Sum of ridership for a declared set of fare classes at a station complex |
| Horizon | 1 hour, 6 hours, and 24 hours |
| Dataset | `5wq4-mkjj`, `wujg-7c2s`, and `t69i-h2me`, after a seam check |
| Grain | Station complex and hour |
| Features | Hour, day of week, month, US federal and NYC holiday calendar, lags at 1, 2, 24, 168 hours, rolling means that end at the origin, and concurrent or lagged Open-Meteo weather at the complex’s grid cell |
| Candidates | Seasonal naive (same hour last week), LightGBM, and an LSTM only if the tree model is already beating the naive forecast |
| Baseline | Seasonal naive |
| Validation | Rolling origin, with at least a final untouched recent block |
| Metrics | MAE, RMSE, and MAPE. MAPE is omitted for hours whose actual value is zero and the skipped share is reported. |
| Limits | Fare-payment estimates, pandemic level shifts between the yearly files, and complexes with long outages. The model does not forecast a station that was closed for the whole test period. Weather is a covariate, not a cause. |

XGBoost can replace or join LightGBM in a comparison run. One tree library is enough for the first promotion.

## Pipeline 2 — monthly refuse tonnage

| | |
| --- | --- |
| Target | Refuse tons collected |
| Horizon | 1 month. No weekly or hourly waste forecast. |
| Dataset | `ebb7-mvp5` |
| Grain | Community district, using borough and district together |
| Features | Month of year, lag 1 and lag 12, 12-month rolling mean ending at the origin, borough |
| Candidates | Seasonal naive (same month last year) and LightGBM or XGBoost |
| Baseline | Seasonal naive |
| Validation | Last 24 months held out, plus one earlier rolling cut |
| Metrics | MAE and RMSE, in tons. MAPE is secondary because some historic district values are very small. |
| Limits | Series composition changes, including organics programmes. Refuse is the target because it is the most continuous field. Paper, MGP, and organics are separate targets with their own null policies, not columns imputed to zero. The forecast is collection mass, not generation by households and not a missed pickup. |

## Pipeline 3 — monitor-level PM2.5

| | |
| --- | --- |
| Target | Daily mean PM2.5, then hourly PM2.5 if the daily model is sound |
| Horizon | Next day for the daily model. Next hour only for the hourly file, and only at monitors with enough history. |
| Dataset | EPA `daily_88101_2024.zip` and `hourly_88101_2024.zip`, plus earlier yearly files after each file is fetched |
| Grain | EPA monitor |
| Features | Lags, hour or day of week, and Open-Meteo variables at the monitor grid cell |
| Candidates | Persistence baseline, LightGBM, Random Forest as a second tree comparison |
| Baseline | Persistence (previous day or previous hour) |
| Validation | Last 60 days of each monitor, monitors kept intact rather than shuffled |
| Metrics | MAE and RMSE in µg/m³ |
| Limits | 2024 alone is a short year for a seasonal model. Earlier EPA years should be added before promotion if their files download. The prediction is for the monitor. A map that fills districts is a separate interpolation product and is labeled `interpolated_by_urbix` with a cross-validation error, or it is not drawn. |

DOHMH neighbourhood indicators (`c3uy-2p5r`) stay in the analytical layer for comparison and change over years. Their annual grain is a poor LSTM target. They are not mixed into the monitor model as if they were the same measurement.

## Pipeline 4 — sampled traffic volume

| | |
| --- | --- |
| Target | Fifteen-minute vehicle count |
| Dataset | `7ym2-wayt` |
| Eligibility | A segment enters training only when it has a minimum repeated history. The minimum is set after a data profile, not before. A segment counted for two days cannot support a 24-hour operational forecast. |
| Features | Time of day, day type, direction, and recent bins from the same count session |
| Candidates | Hour-of-week median and LightGBM |
| Baseline | Hour-of-week median |
| Metrics | MAE and RMSE. MAPE where volumes are large enough that a small denominator does not dominate. |
| Limits | This pipeline does not claim citywide traffic, a next-hour forecast for uncounted roads, or a graph forecast. Many segments are short samples. |

## Pipeline 5 — link speed, after an archive exists

| | |
| --- | --- |
| Target | Link speed at a 1-hour horizon |
| Dataset | URBIX `traffic_speed_snapshots`, not the publisher’s history |
| Start condition | At least 30 complete days of archived snapshots, with missing status codes already nulled |
| Baseline | Persistence and hour-of-week median |
| Candidates | LightGBM. A graph model is a later experiment on the link network if, and only if, the archive is dense enough that neighbours have contemporaneous non-missing speeds. |
| Limits | Until the archive exists, the API returns no speed prediction. The map may show the latest snapshot, labeled with `data_as_of`. |

A graph neural network is a research extension of this pipeline. It is not a Phase 5 deliverable. Building one on ATR samples would invent a road graph of observations the city did not collect.

## Pipeline 6 — public-safety aggregates

| | |
| --- | --- |
| Targets | Weekly or monthly complaint counts by offence class and precinct or NTA. Separately, weekly collision counts by the same geography. |
| Models | Seasonal naive and LightGBM for counts. HDBSCAN or DBSCAN on H3 counts to describe historical concentrations. Isolation Forest, or a robust residual rule, for unusual changes in a series. |
| Baseline | Seasonal naive for counts. A hotspot method has no accuracy score; it has cluster parameters, a noise share, and a written bias statement. |
| Validation | Chronological, for counts only |
| Prohibited | Predicting an individual. Using suspect or victim demographics. A “risk score” for a person, address, or future offender. Treating a cluster as a cause or as an instruction for enforcement. |
| Limits | Reporting bias, enforcement changes, dirty dates, and quarterly lag on complaints. Collisions and complaints are different series and stay separate. |

## Pipeline 7 — population and infrastructure

No population forecast is specified. The first release computes:

- Density only where a count and a land area share a documented vintage.
- Residential unit density from PLUTO `unitsres`, labeled as units, not people.
- Optional WorldPop people-per-pixel, labeled as a 100 m model estimate and, for the 2020 USA file, as a pre-census product.
- K-means or a simple spatial grouping of lots by land use and building size. That is a descriptive segmentation, evaluated by stability and interpretability, not by a fake accuracy.

Transit accessibility is a deterministic graph calculation: walk time on an OSM or LION network from each study area to the nearest GTFS stop, with a stated speed and a stated threshold. Areas beyond the threshold are “underserved by that rule”, not by an undefined model.

## Anomaly detection

An anomaly is a residual against the promoted baseline or model for that series.

- Isolation Forest is appropriate for multivariate residuals once features are stable.
- A robust z-score against the seasonal baseline is preferred when the series is short or seasonal, because the threshold is inspectable.
- Each anomaly stores the detector version, the expected range, and the observations that produced it.
- The agent may describe an anomaly. It may not invent the event that caused it.

## Explainability

For each promoted tree model the workspace shows:

- The metric table against the baseline.
- A time plot of actual and predicted values on the test period.
- The highest-magnitude SHAP features for a selected prediction.
- The training period, test period, dataset version, and a limitation paragraph written by the developer from the evaluation, not generated as a new number.

Prediction intervals are shown only for models that produce them. A tree point prediction without an interval is labeled a point estimate.

## Evaluation integrity

- Training code and API code use different entry points.
- Tests will fail a pipeline that allows a future row into a feature, that writes a metric without a dataset version, or that promotes a model with no baseline row.
- Re-running a job on the same dataset version and seed should match recorded metrics within a stated tolerance. Where a library is nondeterministic, the seed and the tolerance are part of the version.
