from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from engine.taxonomy import (
    CATALOG,
    DIMENSIONS,
    FILTER_COLUMNS,
    HYPOTHESIS_TYPES,
    MAX_DAG_NODES,
    TESTS,
)


class DagValidationError(ValueError):
    pass


class HypothesisNode(BaseModel):
    id: str
    hypothesis_type: str
    dimension: str
    test: str = "chi_square"
    parent_id: str | None = None
    filter_column: str | None = None
    filter_value: str | None = None
    inherit_parent_filter: bool = False

    @field_validator("id")
    @classmethod
    def _id_token(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 64 or not cleaned.replace("_", "").replace("-", "").isalnum():
            raise ValueError("invalid node id")
        return cleaned

    @field_validator("hypothesis_type")
    @classmethod
    def _type(cls, value: str) -> str:
        if value not in HYPOTHESIS_TYPES:
            raise ValueError("hypothesis_type is not in the frozen taxonomy")
        return value

    @field_validator("dimension")
    @classmethod
    def _dimension(cls, value: str) -> str:
        if value not in DIMENSIONS:
            raise ValueError("dimension is not allowlisted")
        return value

    @field_validator("test")
    @classmethod
    def _test(cls, value: str) -> str:
        if value not in TESTS:
            raise ValueError("test is not allowlisted")
        return value


class HypothesisDAG(BaseModel):
    nodes: list[HypothesisNode] = Field(default_factory=list)


def validate_dag(dag: HypothesisDAG) -> HypothesisDAG:
    if not dag.nodes:
        raise DagValidationError("DAG is empty")
    if len(dag.nodes) > MAX_DAG_NODES:
        raise DagValidationError("DAG exceeds max node count")
    ids = [node.id for node in dag.nodes]
    if len(ids) != len(set(ids)):
        raise DagValidationError("duplicate node ids")
    known = set(ids)
    for node in dag.nodes:
        if node.parent_id and node.parent_id not in known:
            raise DagValidationError(f"unknown parent_id {node.parent_id}")
        if node.parent_id == node.id:
            raise DagValidationError("node cannot parent itself")
        if (node.filter_column is None) != (node.filter_value is None):
            raise DagValidationError("filter_column and filter_value must be paired")
        if node.filter_column:
            if node.filter_column not in FILTER_COLUMNS:
                raise DagValidationError("filter_column is not allowlisted")
            allowed = CATALOG.get(node.filter_column, frozenset())
            if node.filter_value not in allowed:
                raise DagValidationError("filter_value is not in the catalog")
        if node.hypothesis_type == "global_shift" and node.dimension != "global":
            raise DagValidationError("global_shift requires dimension=global")
        if node.dimension == "global" and node.hypothesis_type != "global_shift":
            raise DagValidationError("global dimension is only valid on global_shift")
    _assert_acyclic(dag)
    return dag


def _assert_acyclic(dag: HypothesisDAG) -> None:
    children: dict[str, list[str]] = {node.id: [] for node in dag.nodes}
    for node in dag.nodes:
        if node.parent_id:
            children[node.parent_id].append(node.id)
    visiting: set[str] = set()
    seen: set[str] = set()

    def walk(node_id: str) -> None:
        if node_id in seen:
            return
        if node_id in visiting:
            raise DagValidationError("DAG contains a cycle")
        visiting.add(node_id)
        for child in children[node_id]:
            walk(child)
        visiting.remove(node_id)
        seen.add(node_id)

    for node in dag.nodes:
        walk(node.id)


def template_dag(scenario_id: str) -> HypothesisDAG:
    from engine.taxonomy import DRILL_DIMENSION

    drill = DRILL_DIMENSION.get(scenario_id, "bin_country")
    dag = HypothesisDAG(
        nodes=[
            HypothesisNode(id="n1", hypothesis_type="global_shift", dimension="global", test="chi_square"),
            HypothesisNode(
                id="n2",
                parent_id="n1",
                hypothesis_type="gateway_isolation",
                dimension="gateway_id",
                test="chi_square",
            ),
            HypothesisNode(
                id="n3",
                parent_id="n2",
                hypothesis_type="dimensional_slice",
                dimension=drill,
                test="chi_square",
                inherit_parent_filter=True,
            ),
        ]
    )
    return validate_dag(dag)


def parse_dag_payload(payload: dict) -> HypothesisDAG:
    return validate_dag(HypothesisDAG.model_validate(payload))
