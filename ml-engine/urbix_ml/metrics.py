from __future__ import annotations

import math


def chronological_split(rows: list[dict], time_key: str = "observed_at", test_fraction: float = 0.2, validation_fraction: float = 0.2):
    ordered = sorted(rows, key=lambda row: row[time_key])
    count = len(ordered)
    if count < 40:
        return None
    test_count = max(8, int(count * test_fraction))
    validation_count = max(8, int(count * validation_fraction))
    train_count = count - test_count - validation_count
    if train_count < 16:
        return None
    train = ordered[:train_count]
    validation = ordered[train_count : train_count + validation_count]
    test = ordered[train_count + validation_count :]
    if train[-1][time_key] > validation[0][time_key] or validation[-1][time_key] > test[0][time_key]:
        raise RuntimeError("Chronological split leaked a later row into an earlier fold.")
    return train, validation, test


def regression_scores(actual: list[float], predicted: list[float]) -> dict[str, float | None]:
    if not actual or len(actual) != len(predicted):
        return {"mae": None, "rmse": None, "mape": None, "n": 0}
    errors = [abs(a - p) for a, p in zip(actual, predicted)]
    mae = sum(errors) / len(errors)
    rmse = math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(errors))
    eligible = [(a, p) for a, p in zip(actual, predicted) if abs(a) >= 1]
    mape = None
    if eligible:
        mape = 100.0 * sum(abs(a - p) / abs(a) for a, p in eligible) / len(eligible)
    return {"mae": mae, "rmse": rmse, "mape": mape, "n": len(actual)}


def pearson(xs: list[float], ys: list[float]) -> dict | None:
    if len(xs) != len(ys) or len(xs) < 12:
        return None
    try:
        from scipy.stats import pearsonr

        coefficient, p_value = pearsonr(xs, ys)
        return {"method": "pearson", "coefficient": float(coefficient), "p_value": float(p_value), "n": len(xs)}
    except Exception:
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
        den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
        if den_x == 0 or den_y == 0:
            return None
        return {"method": "pearson", "coefficient": num / (den_x * den_y), "p_value": None, "n": len(xs)}
