"""Provenance-preserving citation graph exports and dependency-free traversal.

Reference titles provide *silver* type hints only. Dataset membership, rather
than a title heuristic, determines whether a judgment is corpus verified.
"""
from __future__ import annotations

from collections import defaultdict, deque
import csv
from datetime import date
import json
from pathlib import Path
import re
from typing import Iterable


NODE_FIELDS = [
    "doc_id", "node_type", "case_name", "url", "year", "decision_date",
    "is_corpus", "metadata_verified", "type_basis", "is_land_dispute",
    "has_citation_metadata", "has_text", "aliases_json", "source_files_json",
]
EDGE_FIELDS = [
    "source_id", "target_id", "relationship", "occurrences", "is_self_reference",
    "source_files_json", "reference_sources_json",
]


def _clean(value: object) -> str:
    return " ".join(str(value or "").split())


def _doc_id(value: object) -> str:
    text = str(value)
    if not re.fullmatch(r"[1-9]\d*", text):
        raise ValueError(f"Expected normalized Indian Kanoon document ID, got {value!r}")
    return text


def classify_reference(title: str) -> tuple[str, str]:
    """Conservative title-only hints; never assert that a reference was applied."""
    title = _clean(title)
    if re.search(r"\b(?:vs\.?|versus|v\.)\s+", title, re.I):
        return "Case", "title_heuristic"
    if re.match(r"^(?:section(?:s)?\b|sec\.?\s*\d|s\.\s*\d|article(?:s)?\b|art\.?\s*\d)", title, re.I):
        return "Section", "title_heuristic"
    if re.search(r"\b(?:act|code|constitution|regulations?)\b", title, re.I):
        return "Statute", "title_heuristic"
    return "UnknownReference", "unresolved"


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for item in rows:
            writer.writerow({key: str(value).lower() if isinstance(value, bool) else value
                             for key, value in item.items()})


def export_graph(cases: list[dict], references: list[dict], output_dir: Path) -> dict:
    """Export graph_nodes.csv, graph_edges.csv, graph.json; return counts.

    IDs must already be canonical numeric strings. External citing cases are
    allowed. Duplicate edges merge provenance; source ``occurrences`` counts
    are retained even where two metadata directions report the same relation.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus: dict[str, dict] = {}
    titles: dict[str, set[str]] = defaultdict(set)
    urls: dict[str, set[str]] = defaultdict(set)
    files: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        ident = _doc_id(case["doc_id"])
        if ident in corpus:
            raise ValueError(f"Duplicate normalized case: {ident}")
        corpus[ident] = case
        if case.get("case_name"):
            titles[ident].add(_clean(case["case_name"]))
        files[ident].update(case.get("source_files", []))

    merged: dict[tuple[str, str], dict] = {}
    for reference in references:
        source, target = _doc_id(reference["source_id"]), _doc_id(reference["target_id"])
        for ident, prefix in [(source, "source"), (target, "target")]:
            titles[ident]  # Ensure empty-title external nodes also exist.
            title = _clean(reference.get(prefix + "_title"))
            if title:
                titles[ident].add(title)
            url = reference.get(prefix + "_url")
            if url:
                urls[ident].add(str(url))
            files[ident].update(reference.get("source_files", []))
        edge = merged.setdefault((source, target), {
            "source_id": source, "target_id": target, "relationship": "CITES",
            "occurrences": 0, "is_self_reference": source == target,
            "source_files": set(), "reference_sources": set(),
        })
        count = int(reference.get("occurrences", 1))
        if count < 1:
            raise ValueError("Citation occurrence counts must be positive")
        edge["occurrences"] += count
        edge["source_files"].update(reference.get("source_files", []))
        edge["reference_sources"].update(reference.get("reference_sources", []))

    nodes: list[dict] = []
    for ident in sorted(set(corpus) | set(titles), key=int):
        case = corpus.get(ident)
        aliases = sorted(titles[ident])
        if case:
            node_type, basis = "Case", "dataset_membership"
            name = case.get("case_name") or (aliases[0] if aliases else "")
        else:
            hints = {classify_reference(title)[0] for title in aliases}
            resolved = hints - {"UnknownReference"}
            node_type = next(iter(resolved)) if len(resolved) == 1 else "UnknownReference"
            basis = "title_heuristic" if node_type != "UnknownReference" else "unresolved"
            name = aliases[0] if aliases else ""
        nodes.append({
            "doc_id": ident, "node_type": node_type, "case_name": name,
            "url": (case or {}).get("url") or f"https://indiankanoon.org/doc/{ident}/",
            "year": (case or {}).get("year"),
            "decision_date": (case or {}).get("decision_date"),
            "is_corpus": bool(case), "metadata_verified": bool(case),
            "type_basis": basis,
            "is_land_dispute": bool((case or {}).get("is_land_dispute", False)),
            "has_citation_metadata": bool((case or {}).get("has_citation_metadata", False)),
            "has_text": bool((case or {}).get("has_text", False)),
            "aliases_json": json.dumps(aliases, ensure_ascii=False),
            "source_files_json": json.dumps(sorted(files[ident]), ensure_ascii=False),
        })
    edges = []
    for key in sorted(merged, key=lambda pair: (int(pair[0]), int(pair[1]))):
        edge = merged[key]
        edge["source_files_json"] = json.dumps(sorted(edge.pop("source_files")))
        edge["reference_sources_json"] = json.dumps(sorted(edge.pop("reference_sources")))
        edges.append(edge)
    _write_csv(output_dir / "graph_nodes.csv", nodes, NODE_FIELDS)
    _write_csv(output_dir / "graph_edges.csv", edges, EDGE_FIELDS)
    with (output_dir / "graph.json").open("w", encoding="utf-8") as stream:
        json.dump({"schema_version": "1.0", "directed": True,
                   "nodes": nodes, "edges": edges}, stream, ensure_ascii=False)
        stream.write("\n")
    counts: dict[str, int] = defaultdict(int)
    for node in nodes:
        counts[node["node_type"]] += 1
    return {
        "nodes": len(nodes), "edges": len(edges),
        "node_types": dict(sorted(counts.items())),
        "corpus_nodes": len(corpus), "external_nodes": len(nodes) - len(corpus),
        "self_references": sum(edge["is_self_reference"] for edge in edges),
        "corpus_to_corpus_edges": sum(edge["source_id"] in corpus and edge["target_id"] in corpus
                                       for edge in edges),
        "relationship_semantics": "source CITES target (reported reference; not proof of reliance)",
        "files": ["graph_nodes.csv", "graph_edges.csv", "graph.json"],
    }


class Graph:
    """Offline citation neighbors for Graph-RAG without a running database."""

    def __init__(self, nodes: Iterable[dict], edges: Iterable[dict]):
        self.nodes = {str(node["doc_id"]): dict(node) for node in nodes}
        self.outgoing: dict[str, set[str]] = defaultdict(set)
        self.incoming: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            source, target = str(edge["source_id"]), str(edge["target_id"])
            if source not in self.nodes or target not in self.nodes:
                raise ValueError("Graph edge has an endpoint missing from nodes")
            self.outgoing[source].add(target)
            self.incoming[target].add(source)

    @classmethod
    def from_directory(cls, path: str | Path) -> "Graph":
        with (Path(path) / "graph.json").open(encoding="utf-8") as stream:
            graph = json.load(stream)
        return cls(graph["nodes"], graph["edges"])

    def expand(self, seed_ids: Iterable[str], direction: str = "outgoing", hops: int = 1,
               as_of_year: int | None = None, as_of_date: str | None = None,
               require_text: bool = False, case_only: bool = True,
               max_nodes: int = 1000, exclude_ids: Iterable[str] | None = None) -> list[dict]:
        """Return non-seed neighbors with shortest hop and deterministic ordering.

        Cutoffs are strict: ``year < as_of_year`` / ``date < as_of_date``.
        Unknown dates/years fail the corresponding filter. All traversed nodes,
        including seeds, must pass filters. No traversal through future nodes.
        Year-only filtering intentionally excludes all same-year cases because
        their relative order is not known. ``max_nodes`` bounds returned nodes.
        Use ``exclude_ids=[query_doc_id]`` to explicitly block the query case
        even in non-temporal operational searches. Excluded nodes cannot be
        used as intermediary traversal nodes either.
        """
        if direction not in {"outgoing", "incoming", "both"}:
            raise ValueError("direction must be outgoing, incoming, or both")
        if not isinstance(hops, int) or not 0 <= hops <= 5:
            raise ValueError("hops must be an integer from 0 to 5")
        if not isinstance(max_nodes, int) or max_nodes < 1:
            raise ValueError("max_nodes must be a positive integer")
        cutoff = date.fromisoformat(as_of_date) if as_of_date else None
        excluded = {str(ident) for ident in (exclude_ids or [])}

        def eligible(ident: str) -> bool:
            node = self.nodes.get(ident)
            if ident in excluded or not node or (case_only and node["node_type"] != "Case"):
                return False
            if require_text and not node.get("has_text"):
                return False
            if as_of_year is not None:
                try:
                    if node.get("year") is None or int(node["year"]) >= int(as_of_year):
                        return False
                except (TypeError, ValueError):
                    return False
            if cutoff:
                try:
                    if not node.get("decision_date") or date.fromisoformat(node["decision_date"]) >= cutoff:
                        return False
                except (TypeError, ValueError):
                    return False
            return True

        seeds = {str(ident) for ident in seed_ids}
        queue = deque((ident, 0) for ident in sorted(seeds, key=lambda x: (len(x), x)) if eligible(ident))
        seen = set(seeds)
        result: list[dict] = []
        while queue and len(result) < max_nodes:
            current, depth = queue.popleft()
            if depth >= hops:
                continue
            neighbors: set[str] = set()
            if direction in {"outgoing", "both"}:
                neighbors.update(self.outgoing[current])
            if direction in {"incoming", "both"}:
                neighbors.update(self.incoming[current])
            for ident in sorted(neighbors, key=lambda x: (len(x), x)):
                if ident in seen or not eligible(ident):
                    continue
                seen.add(ident)
                result.append({**self.nodes[ident], "hop": depth + 1})
                queue.append((ident, depth + 1))
                if len(result) >= max_nodes:
                    break
        return result

    def prior_cases(self, seed_ids: Iterable[str], query_year: int, **kwargs) -> list[dict]:
        """Convenience wrapper for conservative year-level historical expansion."""
        return self.expand(seed_ids, as_of_year=query_year, case_only=True, **kwargs)
