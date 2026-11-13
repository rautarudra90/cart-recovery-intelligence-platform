"""
Database connection, session management and SQLite initialization for CartRecover-AI.
Supports SQLAlchemy 2.0 ORM sessions and high-throughput SQLite execution.
"""
import os
import csv
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional, Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from schema import TABLE_ORDER, columns
from cart_recover.models.orm_models import Base

DEFAULT_STARTER_DB = Path(__file__).resolve().parent.parent.parent / "data" / "starter" / "cart_recover.db"
DEFAULT_FULL_DB = Path(__file__).resolve().parent.parent.parent / "data" / "full" / "cart_recover.db"


def get_db_path(scale: str = "starter") -> Path:
    base = Path(__file__).resolve().parent.parent.parent / "data" / scale
    return base / "cart_recover.db"


def get_engine(db_path: Optional[str | Path] = None):
    if db_path is None:
        db_path = DEFAULT_STARTER_DB
    path_str = str(db_path).replace("\\", "/")
    return create_engine(f"sqlite:///{path_str}", echo=False)


def get_session_factory(db_path: Optional[str | Path] = None):
    engine = get_engine(db_path)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_db(db_path: Optional[str | Path] = None) -> Generator[Session, None, None]:
    """Context manager yielding a SQLAlchemy ORM session."""
    session_factory = get_session_factory(db_path)
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def load_dataset_to_sqlite(data_dir: str | Path, db_path: Optional[str | Path] = None) -> Path:
    """
    Rapidly loads all generated CSV tables in data_dir into an SQLite database
    enforcing schemas, primary keys, and foreign keys.
    """
    data_path = Path(data_dir)
    if db_path is None:
        db_path = data_path / "cart_recover.db"
    else:
        db_path = Path(db_path)

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA synchronous = OFF;")
    conn.execute("PRAGMA journal_mode = MEMORY;")

    schema_file = data_path / "schema.sql"
    if not schema_file.exists():
        raise FileNotFoundError(f"Missing schema.sql at {schema_file}")

    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)

    for t in TABLE_ORDER:
        csv_file = data_path / f"{t}.csv"
        if not csv_file.exists():
            continue
        cols = columns(t)
        placeholders = ",".join(["?"] * len(cols))
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = [tuple(None if v == "" else v for v in r) for r in reader]
        conn.executemany(f"INSERT INTO {t} ({','.join(cols)}) VALUES ({placeholders})", rows)

    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.close()
    return db_path
