from datetime import datetime, timedelta, timezone

from urbix_ml.metrics import chronological_split, regression_scores


def test_chronological_split_keeps_time_order():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rows = [{"observed_at": start + timedelta(days=index), "y": index} for index in range(50)]
    train, validation, test = chronological_split(rows)
    assert train[-1]["observed_at"] <= validation[0]["observed_at"] <= test[0]["observed_at"]
    assert len(train) + len(validation) + len(test) == 50


def test_split_withholds_short_series():
    assert chronological_split([{"observed_at": index} for index in range(10)]) is None


def test_regression_scores_do_not_invent_mape_for_tiny_actuals():
    scores = regression_scores([0.2, 0.4], [0.1, 0.2])
    assert scores["mape"] is None
    assert scores["mae"] is not None
