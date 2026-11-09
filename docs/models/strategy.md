# Models

Training code: `ml-engine/urbix_ml/trainers.py`.

| Model | Target | Horizon | Baseline | Withheld when |
| --- | --- | --- | --- | --- |
| ATR sampled volume | Vehicles in a count bin | `sampled_hour` | Training mean | Fewer than 40 dated samples |
| Open-Meteo temperature | Grid temperature | 24 hours | Persistence of the current hour | Fewer than 40 aligned hours |
| CAMS PM2.5 | Grid PM2.5 | 24 hours | Persistence | Same |
| DSNY refuse | District-month tons | Next month | Previous month | Not enough lagged months |

Features never include a value from the target timestamp except where the target is the sampled bin itself, and that model is not described as a forecast. Validation chooses the algorithm. Test metrics are stored and are not used to switch the winner.

Isolation Forest on waste uses `contamination=0.02` as a parameter. The resulting rows are unusual relative to that fit, not confirmed operational events.

SHAP mean absolute value is stored when `shap.TreeExplainer` succeeds. Otherwise permutation importance is stored. If both fail, the evaluation simply has no importance block.

MLflow logging is attempted against `MLFLOW_TRACKING_URI` and ignored if MLflow is absent or errors. The database registry remains the record the API reads.

Graph neural networks and LSTM training are not shipped. The ATR extract is a sparse sample, and the speed feed is a snapshot, so a road-graph forecast would not have a defensible test. PyTorch is documented as a later dependency in `requirements` only when a continuous series exists. It is intentionally not imported by the current trainers.
