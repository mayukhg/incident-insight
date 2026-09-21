from __future__ import annotations

import threading
from pathlib import Path

import duckdb

from seed_data import SCHEMA_SQL, seed_if_empty

_LOCK = threading.RLock()
_CONNECTION: duckdb.DuckDBPyConnection | None = None

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "synthetic_ledger.duckdb"


def get_connection() -> duckdb.DuckDBPyConnection:
    global _CONNECTION
    with _LOCK:
        if _CONNECTION is None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            _CONNECTION = duckdb.connect(str(DB_PATH))
            _CONNECTION.execute("PRAGMA threads=4")
            for statement in SCHEMA_SQL:
                _CONNECTION.execute(statement)
            seed_if_empty(_CONNECTION)
        return _CONNECTION


def db_lock() -> threading.RLock:
    return _LOCK


def init_db() -> None:
    get_connection()
