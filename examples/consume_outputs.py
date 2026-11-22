"""Read shared data and inspect historical graph neighbors; no model needed."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agentic_law_data.graph import Graph


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        yield from (json.loads(line) for line in stream if line.strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args()
    cases = {r["doc_id"]: r for r in read_jsonl(args.processed_dir / "cases.jsonl")}
    graph = Graph.from_directory(args.processed_dir / "graph")
    seeds = [ident for ident, c in cases.items() if c["year"] is not None and c["year"] < 2018][:5]
    neighbors = graph.expand(seeds, hops=1, as_of_year=2018, max_nodes=10)
    print(json.dumps({"case_count": len(cases), "seed_ids": seeds,
        "historical_neighbors_for_inspection": [{k: n.get(k) for k in
            ("doc_id", "case_name", "year", "has_text", "hop")} for n in neighbors],
        "cases_with_text": sum(c["has_text"] for c in cases.values()),
        "next_step": "Use chunks.jsonl for evidence; title-only references are not evidence passages."}, indent=2))


if __name__ == "__main__":
    main()
