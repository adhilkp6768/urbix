from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from urbix_db.models import (
    Anomaly,
    EnvironmentalObservation,
    ModelEvaluation,
    ModelVersion,
    Prediction,
    TrafficObservation,
    WasteObservation,
    WeatherObservation,
)
from urbix_ml.metrics import chronological_split, regression_scores

ARTIFACTS = Path(__file__).resolve().parents[1] / "artifacts"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _candidates():
    from sklearn.ensemble import HistGradientBoostingRegressor

    models = [("hist_gradient_boosting", HistGradientBoostingRegressor(max_depth=6, learning_rate=0.08, max_iter=200, random_state=7))]
    try:
        from xgboost import XGBRegressor

        models.append(("xgboost", XGBRegressor(n_estimators=200, max_depth=4, learning_rate=0.08, objective="reg:squarederror", random_state=7, n_jobs=1)))
    except Exception:
        pass
    try:
        from lightgbm import LGBMRegressor

        models.append(("lightgbm", LGBMRegressor(n_estimators=200, num_leaves=31, learning_rate=0.08, random_state=7, verbosity=-1)))
    except Exception:
        pass
    return models


def _fit_select(train_x, train_y, validation_x, validation_y):
    scored = []
    for name, model in _candidates():
        model.fit(train_x, train_y)
        predicted = model.predict(validation_x)
        scores = regression_scores(list(map(float, validation_y)), list(map(float, predicted)))
        scored.append((scores["mae"], name, model, scores))
    scored.sort(key=lambda item: (item[0] is None, item[0]))
    return scored


def _persist(session: Session, *, domain: str, name: str, algorithm: str, target: str, horizon: str, status: str, datasets: list[str], features: list[str], limitations: str, train_rows, test_rows, metrics: dict, baseline: dict, model=None, predictions: list[dict] | None = None) -> ModelVersion:
    version = ModelVersion(
        id=str(uuid.uuid4()),
        domain=domain,
        name=name,
        version=_stamp(),
        algorithm=algorithm,
        target=target,
        horizon=horizon,
        status=status,
        dataset_codes=datasets,
        feature_names=features,
        train_start=str(train_rows[0]["observed_at"]) if train_rows else None,
        train_end=str(train_rows[-1]["observed_at"]) if train_rows else None,
        test_start=str(test_rows[0]["observed_at"]) if test_rows else None,
        test_end=str(test_rows[-1]["observed_at"]) if test_rows else None,
        limitations=limitations,
        trained_at=datetime.now(timezone.utc),
    )
    if model is not None and status == "trained":
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        path = ARTIFACTS / f"{version.id}.joblib"
        import joblib

        joblib.dump(model, path)
        version.artifact_path = str(path)
    session.add(version)
    for metric_name in ("mae", "rmse", "mape"):
        session.add(
            ModelEvaluation(
                model_version_id=version.id,
                metric_name=metric_name,
                metric_value=metrics.get(metric_name),
                baseline_name=baseline.get("name"),
                baseline_value=(baseline.get("scores") or {}).get(metric_name),
                n_train=baseline.get("n_train"),
                n_test=metrics.get("n"),
                details={"validation": baseline.get("validation"), "all_candidates": baseline.get("candidates")},
            )
        )
    for row in predictions or []:
        session.add(Prediction(model_version_id=version.id, **row))
    session.flush()
    _mlflow(version, metrics, baseline)
    return version


def _mlflow(version: ModelVersion, metrics: dict, baseline: dict) -> None:
    try:
        import mlflow

        mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "file:./mlruns"))
        with mlflow.start_run(run_name=f"{version.domain}-{version.version}"):
            mlflow.log_params({"algorithm": version.algorithm, "horizon": version.horizon, "status": version.status})
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(key, float(value))
            if baseline.get("scores") and baseline["scores"].get("mae") is not None:
                mlflow.log_metric("baseline_mae", float(baseline["scores"]["mae"]))
    except Exception:
        return


def _withhold(session: Session, domain: str, name: str, target: str, horizon: str, datasets: list[str], reason: str) -> dict:
    version = _persist(
        session,
        domain=domain,
        name=name,
        algorithm="withheld",
        target=target,
        horizon=horizon,
        status="withheld",
        datasets=datasets,
        features=[],
        limitations=reason,
        train_rows=[],
        test_rows=[],
        metrics={"mae": None, "rmse": None, "mape": None, "n": 0},
        baseline={"name": None, "scores": {}, "n_train": 0},
    )
    return {"status": "withheld", "model_id": version.id, "reason": reason}


def train_weather_horizon(session: Session, parameter: str = "temperature_2m", horizon_hours: int = 24) -> dict:
    rows = (
        session.query(WeatherObservation)
        .filter(WeatherObservation.parameter == parameter, WeatherObservation.value.isnot(None))
        .order_by(WeatherObservation.observed_at)
        .all()
    )
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row.geo_unit_id or row.city_slug or "unknown", []).append(row)
    examples = []
    for series in grouped.values():
        index = {item.observed_at: item.value for item in series if item.observed_at}
        for item in series:
            if item.observed_at is None:
                continue
            future = item.observed_at + timedelta(hours=horizon_hours)
            if future not in index:
                continue
            examples.append(
                {
                    "observed_at": item.observed_at,
                    "target_time": future,
                    "y": float(index[future]),
                    "x": [float(item.value), item.observed_at.hour, item.observed_at.weekday()],
                    "place_name": item.geo_unit_id,
                    "geo_unit_id": item.geo_unit_id,
                }
            )
    split = chronological_split(examples)
    if split is None:
        return _withhold(session, "environment", f"{parameter} +{horizon_hours}h", parameter, f"next_{horizon_hours}_hours", ["open-meteo-weather"], "Fewer than 40 aligned hourly rows are available, so no forecast was trained.")
    train, validation, test = split
    result = _supervised(
        session,
        domain="environment",
        name=f"Open-Meteo {parameter} +{horizon_hours}h",
        target=f"{parameter} at the selected grid cell",
        horizon=f"next_{horizon_hours}_hours",
        datasets=["open-meteo-weather"],
        features=["value_now", "hour", "weekday"],
        limitations="Forecasts the Open-Meteo grid cell, not a borough mean and not a street measurement. The validation fold chooses the algorithm. Test metrics are reported once and do not change the selection.",
        train=train,
        validation=validation,
        test=test,
        baseline_index=0,
    )
    return result


def train_modelled_air(session: Session) -> dict:
    rows = (
        session.query(EnvironmentalObservation)
        .filter(EnvironmentalObservation.dataset_code == "open-meteo-air-quality", EnvironmentalObservation.parameter == "pm2_5", EnvironmentalObservation.value.isnot(None))
        .all()
    )
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row.geo_unit_id or "unknown", []).append(row)
    examples = []
    for series in grouped.values():
        index = {item.observed_at: item.value for item in series if item.observed_at}
        for item in series:
            future = item.observed_at + timedelta(hours=24) if item.observed_at else None
            if future is None or future not in index or item.value is None:
                continue
            examples.append(
                {
                    "observed_at": item.observed_at,
                    "target_time": future,
                    "y": float(index[future]),
                    "x": [float(item.value), item.observed_at.hour, item.observed_at.weekday()],
                    "place_name": item.place_name,
                    "geo_unit_id": item.geo_unit_id,
                }
            )
    split = chronological_split(examples)
    if split is None:
        return _withhold(session, "environment", "CAMS PM2.5 +24h", "pm2_5", "next_24_hours", ["open-meteo-air-quality"], "Not enough modelled hourly PM2.5 rows to validate a 24-hour forecast.")
    train, validation, test = split
    return _supervised(
        session,
        domain="environment",
        name="CAMS PM2.5 +24h",
        target="Open-Meteo PM2.5 grid value",
        horizon="next_24_hours",
        datasets=["open-meteo-air-quality"],
        features=["pm2_5_now", "hour", "weekday"],
        limitations="This predicts the CAMS/Open-Meteo grid, not DOHMH neighbourhood indicators and not a monitor.",
        train=train,
        validation=validation,
        test=test,
        baseline_index=0,
    )


def train_traffic_samples(session: Session) -> dict:
    rows = session.query(TrafficObservation).filter(TrafficObservation.dataset_code == "nyc-atr-counts", TrafficObservation.volume.isnot(None), TrafficObservation.observed_at.isnot(None)).all()
    boroughs = sorted({row.borough or "Unknown" for row in rows})
    borough_index = {name: position for position, name in enumerate(boroughs)}
    examples = [
        {
            "observed_at": row.observed_at,
            "target_time": row.observed_at,
            "y": float(row.volume),
            "x": [row.observed_at.hour, row.observed_at.weekday(), row.observed_at.month, float(borough_index.get(row.borough or "Unknown", -1))],
            "place_name": row.borough,
            "geo_unit_id": None,
        }
        for row in rows
    ]
    split = chronological_split(examples)
    if split is None:
        return _withhold(session, "traffic", "ATR sampled volume", "vehicle count during an ATR sample bin", "sampled_hour", ["nyc-atr-counts"], "The ATR extract does not contain enough dated samples to evaluate a model. Next-hour citywide forecasts are not offered from this dataset.")
    train, validation, test = split
    return _supervised(
        session,
        domain="traffic",
        name="ATR sampled volume",
        target="vehicles in a sampled ATR bin",
        horizon="sampled_hour",
        datasets=["nyc-atr-counts"],
        features=["hour", "weekday", "month", "borough_code"],
        limitations="ATR samples do not cover the full road network or every hour. This model does not provide a next-hour, 6-hour, or 24-hour operational forecast.",
        train=train,
        validation=validation,
        test=test,
        baseline_index=None,
    )


def train_waste(session: Session) -> dict:
    rows = session.query(WasteObservation).filter(WasteObservation.refuse_tons.isnot(None), WasteObservation.period_start.isnot(None)).all()
    grouped: dict[tuple, list] = {}
    for row in rows:
        grouped.setdefault((row.borough, row.district_code), []).append(row)
    examples = []
    for series in grouped.values():
        series = sorted(series, key=lambda item: item.period_start)
        values = {item.period_start: item.refuse_tons for item in series}
        for index, item in enumerate(series):
            previous = series[index - 1].refuse_tons if index else None
            if previous is None:
                continue
            examples.append(
                {
                    "observed_at": item.period_start,
                    "target_time": item.period_start,
                    "y": float(item.refuse_tons),
                    "x": [float(previous), item.period_start.month],
                    "place_name": f"{item.borough} {item.district_code}",
                    "geo_unit_id": item.geo_unit_id,
                }
            )
    split = chronological_split(examples)
    if split is None:
        return _withhold(session, "waste", "DSNY refuse tons", "monthly refuse tons", "next_month", ["nyc-waste-tonnage"], "Not enough district-months with a prior month to train a next-month refuse model.")
    train, validation, test = split
    result = _supervised(
        session,
        domain="waste",
        name="DSNY refuse tons",
        target="monthly refuse tons by community district",
        horizon="next_month",
        datasets=["nyc-waste-tonnage"],
        features=["previous_month_tons", "month"],
        limitations="Predicts DSNY-collected refuse tonnage. It does not predict missed collections or commercial waste.",
        train=train,
        validation=validation,
        test=test,
        baseline_index=0,
    )
    if len(examples) >= 40:
        from sklearn.ensemble import IsolationForest

        detector = IsolationForest(contamination=0.02, random_state=7)
        matrix = np.array([row["x"] for row in examples], dtype=float)
        detector.fit(matrix)
        scores = -detector.score_samples(matrix)
        cutoff = float(np.quantile(scores, 0.98))
        for row, score in zip(examples, scores):
            if float(score) < cutoff:
                continue
            session.add(
                Anomaly(
                    id=str(__import__("uuid").uuid4()),
                    domain="waste",
                    geo_unit_id=row.get("geo_unit_id"),
                    detected_at=row.get("observed_at"),
                    score=float(score),
                    method="isolation_forest",
                    summary=f"{row['place_name']} refuse pattern scored {float(score):.3f}, above the training 98th percentile.",
                    evidence={"contamination_parameter": 0.02, "cutoff": cutoff, "features": row["x"]},
                )
            )
    return result


def _supervised(session, *, domain, name, target, horizon, datasets, features, limitations, train, validation, test, baseline_index):
    train_x = np.array([row["x"] for row in train], dtype=float)
    train_y = np.array([row["y"] for row in train], dtype=float)
    validation_x = np.array([row["x"] for row in validation], dtype=float)
    validation_y = np.array([row["y"] for row in validation], dtype=float)
    test_x = np.array([row["x"] for row in test], dtype=float)
    test_y = np.array([row["y"] for row in test], dtype=float)
    scored = _fit_select(train_x, train_y, validation_x, validation_y)
    _mae, algorithm, model, validation_scores = scored[0]
    predicted = list(map(float, model.predict(test_x)))
    metrics = regression_scores(list(map(float, test_y)), predicted)
    if baseline_index is None:
        baseline_pred = [float(np.mean(train_y))] * len(test_y)
        baseline_name = "train_mean"
    else:
        baseline_pred = [float(row["x"][baseline_index]) for row in test]
        baseline_name = "persistence"
    baseline_scores = regression_scores(list(map(float, test_y)), baseline_pred)
    importances = _importance(model, features, test_x, test_y)
    version = _persist(
        session,
        domain=domain,
        name=name,
        algorithm=algorithm,
        target=target,
        horizon=horizon,
        status="trained",
        datasets=datasets,
        features=features,
        limitations=limitations,
        train_rows=train,
        test_rows=test,
        metrics=metrics,
        baseline={"name": baseline_name, "scores": baseline_scores, "n_train": len(train), "validation": validation_scores, "candidates": [{"algorithm": item[1], "validation_mae": item[0]} for item in scored]},
        model=model,
        predictions=[
            {
                "geo_unit_id": row.get("geo_unit_id"),
                "place_name": row.get("place_name"),
                "target_time": row.get("target_time"),
                "predicted_value": value,
                "created_at": datetime.now(timezone.utc),
            }
            for row, value in list(zip(test, predicted))[:200]
        ],
    )
    if importances:
        evaluation = session.query(ModelEvaluation).filter(ModelEvaluation.model_version_id == version.id, ModelEvaluation.metric_name == "mae").one()
        details = dict(evaluation.details or {})
        details["feature_importance"] = importances
        evaluation.details = details
    return {"status": "trained", "model_id": version.id, "algorithm": algorithm, "test": metrics, "baseline": baseline_scores}


def _importance(model, features: list[str], test_x, test_y) -> dict:
    try:
        import shap

        explainer = shap.TreeExplainer(model)
        values = explainer.shap_values(test_x[:80])
        array = np.abs(np.array(values)).mean(axis=0)
        return {"method": "shap_mean_abs", "values": {feature: float(array[index]) for index, feature in enumerate(features)}}
    except Exception:
        try:
            from sklearn.inspection import permutation_importance

            result = permutation_importance(model, test_x, test_y, n_repeats=4, random_state=7)
            return {"method": "permutation_importance", "values": {feature: float(result.importances_mean[index]) for index, feature in enumerate(features)}}
        except Exception:
            return {}


def train_domain(session: Session, domain: str) -> dict:
    if domain == "traffic":
        return train_traffic_samples(session)
    if domain == "waste":
        return train_waste(session)
    if domain == "environment":
        weather = train_weather_horizon(session)
        air = train_modelled_air(session)
        return {"status": "completed", "runs": [weather, air]}
    return _withhold(session, domain, domain, domain, "unsupported", [], "No validated trainer is registered for this domain.")
