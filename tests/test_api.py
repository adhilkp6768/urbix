from fastapi.testclient import TestClient

from app.main import app
from urbix_ml.trainers import train_domain


def test_empty_traffic_is_unavailable_rather_than_zero():
    client = TestClient(app)
    response = client.get("/api/v1/traffic/trends?city=nyc")
    assert response.status_code == 200
    body = response.json()
    assert body["availability"] == "unavailable"
    assert all(item["value"] is None for item in body["kpis"])


def test_unknown_city_is_not_found():
    client = TestClient(app)
    response = client.get("/api/v1/cities/not-a-city/overview")
    assert response.status_code == 404


def test_freshness_reports_refresh_state():
    client = TestClient(app)
    body = client.get("/api/v1/system/freshness").json()
    assert body["refresh"]["running"] is False
    assert isinstance(body["datasets"], list)


def test_world_does_not_average_missing_cities():
    client = TestClient(app)
    body = client.get("/api/v1/geography/world").json()
    assert "cities_with_data" in body
    assert "global_pm25" not in body


def test_training_without_rows_is_withheld(monkeypatch):
    from urbix_db.session import make_session_factory

    session = make_session_factory().session() if False else None
    from app.main import SessionLocal

    session = SessionLocal()
    try:
        result = train_domain(session, "traffic")
        assert result["status"] == "withheld"
        session.commit()
    finally:
        session.close()
    catalog = TestClient(app).get("/api/v1/models").json()["results"]
    assert catalog[0]["metrics"][0]["value"] is None
