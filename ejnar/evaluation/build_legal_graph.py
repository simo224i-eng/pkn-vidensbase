"""Byg og eksportér Ejnars deterministiske juridiske graf som JSON."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


EJNAR_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = EJNAR_DIR.parent
if str(EJNAR_DIR) not in sys.path:
    sys.path.insert(0, str(EJNAR_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from legal_graph import DecisionGraph, build_decision_graph  # noqa: E402
from evaluation.run_retrieval import load_corpus  # noqa: E402


def graph_statistics(graph: DecisionGraph) -> dict[str, Any]:
    kind_counts: dict[str, int] = {}
    for node in graph.nodes.values():
        kind_counts[node.kind] = kind_counts.get(node.kind, 0) + 1

    connected_decisions = {edge.source for edge in graph.edges}
    decision_ids = set(graph.decision_payloads)
    return {
        "decisions": len(decision_ids),
        "feature_nodes": len(graph.nodes) - len(decision_ids),
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "isolated_decisions": len(decision_ids - connected_decisions),
        "node_kinds": dict(sorted(kind_counts.items())),
    }


def graph_payload(graph: DecisionGraph) -> dict[str, Any]:
    return {
        "schema_version": "ejnar-legal-graph-v1",
        "statistics": graph_statistics(graph),
        "graph": graph.to_dict(),
    }


def write_graph(path: str | Path, graph: DecisionGraph, *, compact: bool = False) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = graph_payload(graph)
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=None if compact else 2,
        separators=(",", ":") if compact else None,
        sort_keys=True,
    )
    target.write_text(rendered + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Byg Ejnars juridiske kendelsesgraf")
    parser.add_argument("--data-dir", default=str(EJNAR_DIR))
    parser.add_argument(
        "--output",
        default=str(EJNAR_DIR / "evaluation" / "legal_graph.json"),
    )
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    import shared

    frame = load_corpus(Path(args.data_dir), shared)
    graph = build_decision_graph(frame.to_dict("records"))
    write_graph(args.output, graph, compact=args.compact)
    print(json.dumps(graph_statistics(graph), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
