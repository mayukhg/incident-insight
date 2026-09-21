from __future__ import annotations

from dataclasses import dataclass

from engine.dag import HypothesisNode
from engine.taxonomy import DIMENSION_EXPR, FILTER_COLUMNS


class CompilerError(ValueError):
    pass


@dataclass(frozen=True)
class CompiledQuery:
    sql: str
    scan_sql: str
    filter_column: str | None
    filter_value: str | None
    dimension: str

    def params(self, start: str, end: str) -> list[object]:
        values: list[object] = []
        if self.filter_column and self.filter_value is not None:
            values.append(self.filter_value)
        values.extend([start, end])
        return values


def compile_node(node: HypothesisNode) -> CompiledQuery:
    expr = DIMENSION_EXPR.get(node.dimension)
    if expr is None:
        raise CompilerError("dimension has no SQL template")
    where = "timestamp >= ? AND timestamp < ?"
    scan_where = where
    filter_column = node.filter_column
    filter_value = node.filter_value
    if filter_column:
        if filter_column not in FILTER_COLUMNS:
            raise CompilerError("filter_column is not allowlisted")
        where = f"{filter_column} = ? AND {where}"
        scan_where = where
    sql = (
        f"SELECT {expr} AS slice, "
        "COUNT(*) AS volume, "
        "COUNT(*) FILTER (WHERE status = 'authorized') AS authorized "
        "FROM transactions "
        f"WHERE {where} "
        "GROUP BY 1"
    )
    scan_sql = f"SELECT COUNT(*) FROM transactions WHERE {scan_where}"
    return CompiledQuery(
        sql=sql,
        scan_sql=scan_sql,
        filter_column=filter_column,
        filter_value=filter_value,
        dimension=node.dimension,
    )
