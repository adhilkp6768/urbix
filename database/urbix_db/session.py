from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from urbix_db.models import Base

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = REPO_ROOT / "database" / "migrations"


def normalize_database_url(url: str | None = None) -> str:
    raw = url or os.environ.get("DATABASE_URL", "sqlite:///./urbix.db")
    if raw.startswith("postgres://"):
        raw = "postgresql+psycopg://" + raw.removeprefix("postgres://")
    elif raw.startswith("postgresql://") and "+psycopg" not in raw.split("://", 1)[0]:
        raw = "postgresql+psycopg://" + raw.removeprefix("postgresql://")
    if raw.startswith("sqlite:///./"):
        path = (REPO_ROOT / raw.removeprefix("sqlite:///./")).resolve()
        return f"sqlite:///{path}"
    return raw


def make_engine(url: str | None = None):
    database_url = normalize_database_url(url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, future=True)


def make_session_factory(engine=None):
    engine = engine or make_engine()
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db(engine=None) -> None:
    engine = engine or make_engine()
    Base.metadata.create_all(engine)
    if engine.dialect.name == "postgresql":
        _apply_postgis(engine)


def _apply_postgis(engine) -> None:
    sql_path = MIGRATIONS / "001_postgis.sql"
    if not sql_path.exists():
        return
    script = sql_path.read_text()
    statements = [part.strip() for part in script.split(";") if part.strip() and not part.strip().startswith("--")]
    with engine.connect() as connection:
        postgis = True
        for statement in statements:
            try:
                with connection.begin():
                    connection.execute(text(statement))
            except Exception as exc:
                lowered = f"{statement} {exc}".lower()
                if "vector" in lowered or "postgis" in lowered or "geometry" in lowered or "gist" in lowered:
                    postgis = False
                    continue
                if not postgis and "geom" in statement.lower():
                    continue
                raise


def session_scope(factory=None):
    factory = factory or make_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
