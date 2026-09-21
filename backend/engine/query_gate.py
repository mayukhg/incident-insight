from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Sequence

from db import db_lock, get_connection


@dataclass
class QueryResult:
    sql: str
    rows: list[tuple[Any, ...]]
    columns: list[str]
    execution_time_ms: int
    rows_scanned: int
    cache_state: str = "cold"


def execute(sql: str, params: Sequence[Any] | None = None, *, rows_scanned_sql: str | None = None, scan_params: Sequence[Any] | None = None) -> QueryResult:
    con = get_connection()
    with db_lock():
        started = perf_counter()
        cursor = con.execute(sql, list(params or []))
        description = cursor.description or []
        columns = [col[0] for col in description]
        rows = cursor.fetchall()
        elapsed_ms = max(1, int((perf_counter() - started) * 1000))
        scanned = len(rows)
        if rows_scanned_sql:
            scan_args = list(params or []) if scan_params is None else list(scan_params)
            scanned_row = con.execute(rows_scanned_sql, scan_args).fetchone()
            scanned = int(scanned_row[0]) if scanned_row else scanned
    return QueryResult(
        sql=_render_sql(sql, params),
        rows=rows,
        columns=columns,
        execution_time_ms=elapsed_ms,
        rows_scanned=scanned,
    )


def _render_sql(sql: str, params: Sequence[Any] | None) -> str:
    rendered = " ".join(sql.split())
    if not params:
        return rendered
    for value in params:
        if value is None:
            token = "NULL"
        elif isinstance(value, (int, float)):
            token = str(value)
        else:
            token = "'" + str(value).replace("'", "''") + "'"
        rendered = rendered.replace("?", token, 1)
    return rendered
