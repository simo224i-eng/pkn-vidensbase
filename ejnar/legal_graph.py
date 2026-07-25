"""Deterministisk juridisk graf for Ejnars ejerskiftekendelser.

Grafen forbinder hver kendelse med normaliserede metadata-noder. Første version
kræver ingen grafdatabase og ændrer ikke retrieval; den leverer et stabilt
fundament til relaterede kendelser, forklaringer og senere graph retrieval.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
import re
from typing import Any, Callable, Iterable

try:
    from metadata_schema import DecisionMetadata, extract_metadata
    from paragraph_retrieval import decision_identity
except ImportError:
    try:
        from ejnar.metadata_schema import DecisionMetadata, extract_metadata
        from ejnar.paragraph_retrieval import decision_identity
    except ImportError:  # isolerede tests kan injicere extractor/identity builder
        DecisionMetadata = Any  # type: ignore[misc,assignment]
        extract_metadata = None  # type: ignore[assignment]
        decision_identity = None  # type: ignore[assignment]


_FIELD_WEIGHTS = {
    "building_parts": 3.0,
    "causes": 2.5,
    "consequences": 2.0,
    "coverage_outcomes": 1.5,
    "exclusions": 2.0,
    "laws": 1.5,
    "construction_years": 1.0,
    "materials": 2.0,
    "remedies": 1.0,
    "depreciation": 1.5,
}


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    kind: str
    label: str
    attributes: dict[str, Any]


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relation: str
    weight: float


@dataclass(frozen=True)
class RelatedDecision:
    decision_id: str
    score: float
    shared_features: tuple[str, ...]
    case_number: str
    title: str
    link: str


class DecisionGraph:
    def __init__(
        self,
        nodes: dict[str, GraphNode],
        edges: Iterable[GraphEdge],
        decision_features: dict[str, dict[str, tuple[str, float]]],
        decision_payloads: dict[str, dict[str, Any]],
    ) -> None:
        self.nodes = dict(nodes)
        self.edges = tuple(edges)
        self.decision_features = {
            key: dict(value) for key, value in decision_features.items()
        }
        self.decision_payloads = {
            key: dict(value) for key, value in decision_payloads.items()
        }

    def related(
        self,
        decision_id: str,
        *,
        limit: int = 10,
        min_score: float = 0.05,
    ) -> list[RelatedDecision]:
        target = self.decision_features.get(decision_id)
        if not target or limit <= 0:
            return []
        target_total = sum(weight for _, weight in target.values())
        ranked: list[RelatedDecision] = []
        for candidate_id, candidate in self.decision_features.items():
            if candidate_id == decision_id:
                continue
            common = sorted(set(target) & set(candidate))
            if not common:
                continue
            shared_weight = sum(target[key][1] for key in common)
            candidate_total = sum(weight for _, weight in candidate.values())
            denominator = target_total + candidate_total - shared_weight
            score = shared_weight / denominator if denominator else 0.0
            if score < min_score:
                continue
            payload = self.decision_payloads.get(candidate_id, {})
            ranked.append(
                RelatedDecision(
                    decision_id=candidate_id,
                    score=round(score, 6),
                    shared_features=tuple(target[key][0] for key in common),
                    case_number=str(payload.get("case_number") or ""),
                    title=str(payload.get("title") or ""),
                    link=str(payload.get("link") or ""),
                )
            )
        ranked.sort(
            key=lambda item: (
                -item.score,
                -len(item.shared_features),
                item.case_number,
                item.decision_id,
            )
        )
        return ranked[:limit]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [
                asdict(node)
                for node in sorted(self.nodes.values(), key=lambda item: item.node_id)
            ],
            "edges": [
                asdict(edge)
                for edge in sorted(
                    self.edges,
                    key=lambda item: (item.source, item.relation, item.target),
                )
            ],
        }


def _normalise(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _feature_node_id(field_name: str, value: Any) -> str:
    normalised = _normalise(value)
    digest = hashlib.sha1(f"{field_name}:{normalised}".encode("utf-8")).hexdigest()[:14]
    return f"feature:{field_name}:{digest}"


def _fallback_identity(document: dict[str, Any]) -> str:
    for key in ("Sagsnummer", "Link", "Titel"):
        value = _normalise(document.get(key))
        if value:
            return value
    return hashlib.sha1(repr(sorted(document.items())).encode("utf-8")).hexdigest()[:16]


def _decision_node_id(
    document: dict[str, Any],
    identity_builder: Callable[[dict[str, Any]], str] | None,
) -> str:
    identity = (
        identity_builder(document)
        if identity_builder is not None
        else _fallback_identity(document)
    )
    return f"decision:{identity}"


def _row_text(document: dict[str, Any]) -> str:
    """Byg featuretekst fra originale felter, ikke tidligere afledte labels."""
    return "\n".join(
        str(document.get(key, "") or "")
        for key in ("Titel", "Excerpt", "Tekst")
    )


def _metadata_values(metadata: DecisionMetadata) -> Iterable[tuple[str, Any]]:
    for field in fields(metadata):
        for value in getattr(metadata, field.name):
            yield field.name, value


def build_decision_graph(
    documents: Iterable[dict[str, Any]],
    *,
    metadata_extractor: Callable[[str], DecisionMetadata] | None = extract_metadata,
    identity_builder: Callable[[dict[str, Any]], str] | None = decision_identity,
) -> DecisionGraph:
    if metadata_extractor is None:
        raise RuntimeError("metadata_extractor er ikke tilgængelig")

    nodes: dict[str, GraphNode] = {}
    edges: dict[tuple[str, str, str], GraphEdge] = {}
    decision_features: dict[str, dict[str, tuple[str, float]]] = {}
    decision_payloads: dict[str, dict[str, Any]] = {}

    for document in documents:
        decision_id = _decision_node_id(document, identity_builder)
        if decision_id in decision_payloads:
            continue
        case_number = str(document.get("Sagsnummer") or "").strip()
        title = str(document.get("Titel") or "").strip()
        link = str(document.get("Link") or "").strip()
        nodes[decision_id] = GraphNode(
            node_id=decision_id,
            kind="decision",
            label=case_number or title or decision_id,
            attributes={
                "case_number": case_number,
                "title": title,
                "link": link,
                "date": str(document.get("Dato") or ""),
                "outcome": str(document.get("Udfald") or ""),
                "company": str(document.get("Selskab") or ""),
            },
        )
        decision_payloads[decision_id] = {
            "case_number": case_number,
            "title": title,
            "link": link,
        }
        feature_map: dict[str, tuple[str, float]] = {}
        metadata = metadata_extractor(_row_text(document))
        for field_name, value in _metadata_values(metadata):
            label = str(value)
            feature_id = _feature_node_id(field_name, value)
            weight = float(_FIELD_WEIGHTS.get(field_name, 1.0))
            feature_key = f"{field_name}:{_normalise(value)}"
            feature_map[feature_key] = (f"{field_name}: {label}", weight)
            nodes.setdefault(
                feature_id,
                GraphNode(
                    node_id=feature_id,
                    kind=field_name,
                    label=label,
                    attributes={"field": field_name, "value": value},
                ),
            )
            relation = f"has_{field_name.removesuffix('s')}"
            edge_key = (decision_id, relation, feature_id)
            edges[edge_key] = GraphEdge(
                source=decision_id,
                target=feature_id,
                relation=relation,
                weight=weight,
            )
        decision_features[decision_id] = feature_map

    return DecisionGraph(
        nodes=nodes,
        edges=edges.values(),
        decision_features=decision_features,
        decision_payloads=decision_payloads,
    )
