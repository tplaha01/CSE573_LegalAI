#!/usr/bin/env python3
"""Validate snapshot hashes, graph integrity, coverage, and raw citation direction."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from agentic_law_data.normalize import document_id


def jsonl(path):
    with path.open(encoding="utf-8") as stream:
        yield from (json.loads(line) for line in stream if line.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    root = args.processed_dir
    manifest = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
    for filename, expected in manifest["artifacts"].items():
        digest = hashlib.sha256()
        with (root / filename).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != expected:
            raise ValueError(f"Snapshot hash differs: {filename}")
    cases = list(jsonl(root / "cases.jsonl"))
    ids = {c["doc_id"] for c in cases}
    if len(cases) != len(ids):
        raise ValueError("Duplicate case identity")
    raw = {p.name: json.loads(p.read_text(encoding="utf-8")) for p in args.raw_dir.glob("citations*.json")}
    edges, observed = set(), 0
    for edge in jsonl(root / "references.jsonl"):
        key = (edge["source_id"], edge["target_id"])
        if key in edges:
            raise ValueError(f"Duplicate directed reference {key}")
        edges.add(key)
        if edge["occurrences"] != len(edge["source_records"]):
            raise ValueError(f"Incorrect observation count {key}")
        for provenance in edge["source_records"]:
            record = raw[provenance["file"]][provenance["json_index"]]
            original_source = document_id(record.get("source_doc_id"), record.get("source_url") or record.get("url"))
            ref = record[provenance["field"]][provenance["reference_index"]]
            original_target = document_id(ref.get("doc_id"), ref.get("url"))
            expected = ((original_target, original_source) if provenance["field"] == "cited_by"
                        else (original_source, original_target))
            if key != expected:
                raise ValueError(f"Raw citation orientation mismatch {key}")
            observed += 1
    graph = json.loads((root / "graph/graph.json").read_text(encoding="utf-8"))
    graph_ids = {n["doc_id"] for n in graph["nodes"]}
    graph_edges = {(e["source_id"], e["target_id"]) for e in graph["edges"]}
    if graph_edges != edges or not ids.issubset(graph_ids):
        raise ValueError("Graph export does not cover normalized data")
    if any(a not in graph_ids or b not in graph_ids for a, b in edges):
        raise ValueError("Dangling citation endpoint")
    print(json.dumps({"status": "passed", "artifact_hashes_checked": len(manifest["artifacts"]),
        "cases": len(cases), "nodes": len(graph_ids), "edges": len(edges),
        "raw_observations_direction_checked": observed}, indent=2))


if __name__ == "__main__":
    main()
