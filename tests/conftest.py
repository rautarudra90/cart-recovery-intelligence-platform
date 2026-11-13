"""
Pytest fixtures for CartRecover-AI testing suite.
Provides memory and file-based SQLite sessions, sample data, and paths.
"""
import sys
import pytest
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from cart_recover.models.orm_models import Base
from cart_recover.database.connection import load_dataset_to_sqlite

DATA_DIR = ROOT_DIR / "data"
STARTER_DIR = DATA_DIR / "starter"
FULL_DIR = DATA_DIR / "full"


@pytest.fixture(scope="session")
def starter_data_dir():
    return STARTER_DIR


@pytest.fixture(scope="session")
def starter_db(starter_data_dir):
    db_file = starter_data_dir / "cart_recover.db"
    if not db_file.exists():
        load_dataset_to_sqlite(starter_data_dir, db_file)
    return db_file


@pytest.fixture
def db_session(starter_db):
    engine = create_engine(f"sqlite:///{str(starter_db).replace('\\', '/')}")
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
