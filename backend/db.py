from __future__ import annotations

import gzip
import shutil
import threading
from pathlib import Path

import duckdb

from seed_data import SCHEMA_SQL, seed_if_empty

_LOCK = threading.RLock()
_CONNECTION: duckdb.DuckDBPyConnection | None = None

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "synthetic_ledger.duckdb"
ARCHIVE_PATH = DATA_DIR / "synthetic_ledger.duckdb.gz"


def _restore_ledger_from_archive() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists() and DB_PATH.stat().st_size > 0:
        return
    if not ARCHIVE_PATH.exists():
        return
    with gzip.open(ARCHIVE_PATH, "rb") as source, DB_PATH.open("wb") as destination:
        shutil.copyfileobj(source, destination)


def get_connection() -> duckdb.DuckDBPyConnection:
    global _CONNECTION
    with _LOCK:
        if _CONNECTION is None:
            _restore_ledger_from_archive()
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
