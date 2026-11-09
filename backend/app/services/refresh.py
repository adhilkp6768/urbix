from __future__ import annotations

import threading
from datetime import datetime, timezone

from urbix_data.pipeline import REFERENCE_SEQUENCE, run_connector

CURRENT_SEQUENCE = [
    "nyc-traffic-speeds",
    "nyc-atr-counts",
    "nypd-crashes",
    "nypd-complaints-ytd",
    "nyc-air-quality",
    "nyc-waste-tonnage",
    "open-meteo-weather",
    "open-meteo-air-quality",
    "mta-subway-ridership",
    "nyc-shelter-buildings",
]

_LOCK = threading.Lock()
_STATE: dict = {
    "running": False,
    "scope": None,
    "started_at": None,
    "finished_at": None,
    "steps": [],
}


def snapshot() -> dict:
    with _LOCK:
        return {
            "running": _STATE["running"],
            "scope": _STATE["scope"],
            "started_at": _STATE["started_at"],
            "finished_at": _STATE["finished_at"],
            "steps": list(_STATE["steps"]),
        }


def start(session_factory, scope: str) -> bool:
    sequence = REFERENCE_SEQUENCE if scope == "full" else CURRENT_SEQUENCE
    with _LOCK:
        if _STATE["running"]:
            return False
        _STATE["running"] = True
        _STATE["scope"] = scope
        _STATE["started_at"] = _now()
        _STATE["finished_at"] = None
        _STATE["steps"] = [{"dataset_code": code, "status": "queued", "message": "Waiting for the previous extract in this refresh."} for code in sequence]
    threading.Thread(target=_run, args=(session_factory, sequence, scope), name="urbix-refresh", daemon=True).start()
    return True


def start_if_stale(session_factory, hours: float) -> None:
    session = session_factory()
    try:
        from urbix_db.models import IngestionJob

        latest = (
            session.query(IngestionJob)
            .filter(IngestionJob.status == "succeeded")
            .order_by(IngestionJob.finished_at.desc())
            .first()
        )
    finally:
        session.close()
    if latest is None or latest.finished_at is None:
        start(session_factory, "full")
        return
    if hours <= 0:
        return
    finished = latest.finished_at
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=timezone.utc)
    if (datetime.now(timezone.utc) - finished).total_seconds() >= hours * 3600:
        start(session_factory, "current")


def serve(session_factory, hours: float) -> None:
    interval = max(hours, 1) * 3600
    while True:
        threading.Event().wait(interval)
        start(session_factory, "current")


def _run(session_factory, sequence: list[str], scope: str) -> None:
    if scope == "full":
        _prepare_registry(session_factory)
    try:
        for index, code in enumerate(sequence):
            session = session_factory()
            try:
                result = run_connector(session, code, _options(code, scope))
                session.commit()
            except Exception as exc:
                session.rollback()
                result = {"dataset_code": code, "status": "failed", "rows_written": 0, "message": str(exc)}
            finally:
                session.close()
            with _LOCK:
                steps = list(_STATE["steps"])
                steps[index] = {
                    "dataset_code": result.get("dataset_code", code),
                    "status": result.get("status"),
                    "rows_written": result.get("rows_written"),
                    "message": result.get("message"),
                }
                _STATE["steps"] = steps
        _sync_postgis(session_factory)
    finally:
        with _LOCK:
            _STATE["running"] = False
            _STATE["finished_at"] = _now()


def _prepare_registry(session_factory) -> None:
    from urbix_data.pipeline import seed_reference_geography
    from urbix_data.repository import upsert_catalog

    session = session_factory()
    try:
        upsert_catalog(session)
        seed_reference_geography(session)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def _sync_postgis(session_factory) -> None:
    engine = getattr(session_factory, "kw", {}).get("bind")
    if engine is None or getattr(engine.dialect, "name", "") != "postgresql":
        return
    try:
        from urbix_db.spatial import sync_postgis_geometries

        sync_postgis_geometries(engine)
    except Exception:
        return


def _options(code: str, scope: str) -> dict:
    if code in {"open-meteo-weather", "open-meteo-air-quality"}:
        return {"cities": ["nyc"], "days": 21 if scope == "full" else 7}
    if code == "nyc-atr-counts":
        return {"max_rows": 8000}
    return {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
