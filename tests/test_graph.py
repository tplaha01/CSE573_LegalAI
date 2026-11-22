import csv
import json
from pathlib import Path
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agentic_law_data.graph import Graph, classify_reference, export_graph


def case(ident, year=2000, **kwargs):
    return dict(doc_id=ident, case_name=f"Case {ident}", year=year,
                decision_date=f"{year}-01-01", url=f"https://indiankanoon.org/doc/{ident}/",
                is_land_dispute=False, has_text=True, has_citation_metadata=True, **kwargs)


class GraphTests(unittest.TestCase):
    def test_types_do_not_assume_every_reference_is_case(self):
        for name, expected in [("Article 21", "Section"), ("Sec. 12", "Section"),
                               ("Indian Penal Code", "Statute"), ("Land Acquisition Act 1894", "Statute"),
                               ("Alpha v. Beta", "Case"), ("Alpha vs Beta", "Case"),
                               ("12", "UnknownReference")]:
            self.assertEqual(classify_reference(name)[0], expected)

    def test_export_deduplicates_and_preserves_external_sources(self):
        refs = [dict(source_id="1", target_id="2", target_title="Article 21", source_files=["a.json"],
                     reference_sources=["precedents"], occurrences=1),
                dict(source_id="1", target_id="2", target_title="Article 21", source_files=["b.json"],
                     reference_sources=["cited_by"], occurrences=1),
                dict(source_id="3", source_title="Later vs Earlier", target_id="1",
                     source_files=["a.json"], reference_sources=["cited_by"], occurrences=1)]
        with tempfile.TemporaryDirectory() as folder:
            stats = export_graph([case("1")], refs, Path(folder))
            self.assertEqual(stats["nodes"], 3)
            self.assertEqual(stats["edges"], 2)
            graph = Graph.from_directory(folder)
            self.assertEqual(graph.nodes["2"]["node_type"], "Section")
            self.assertEqual(graph.nodes["3"]["node_type"], "Case")
            self.assertFalse(graph.nodes["3"]["metadata_verified"])
            self.assertEqual([row["doc_id"] for row in graph.expand(["1"], direction="incoming")], ["3"])
            self.assertEqual(graph.expand(["1"], direction="incoming", as_of_year=2018), [])
            with (Path(folder) / "graph_edges.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]["occurrences"], "2")
            self.assertEqual(json.loads(rows[0]["reference_sources_json"]), ["cited_by", "precedents"])
            # Stable exports despite input ordering.
            first = (Path(folder) / "graph.json").read_bytes()
            export_graph([case("1")], list(reversed(refs)), Path(folder))
            self.assertEqual(first, (Path(folder) / "graph.json").read_bytes())

    def test_temporal_traversal_blocks_future_and_unknown_nodes(self):
        nodes = [dict(case("1", 2010), node_type="Case"), dict(case("2", 2000), node_type="Case"),
                 dict(case("3", 2020), node_type="Case"), dict(case("4", 2005), node_type="Case"),
                 dict(case("5", 2001), node_type="Case")]
        nodes[4].update(year=None, decision_date=None)
        edges = [dict(source_id="1", target_id="2"), dict(source_id="3", target_id="1"),
                 dict(source_id="3", target_id="4"), dict(source_id="1", target_id="5")]
        graph = Graph(nodes, edges)
        self.assertEqual([x["doc_id"] for x in graph.expand(["1"], direction="both", hops=2,
                                                         as_of_year=2018)], ["2"])
        self.assertEqual(graph.expand(["3"], as_of_year=2018), [])
        self.assertEqual(graph.expand(["1"], as_of_date="2010-01-01"), [])
        self.assertEqual([x["doc_id"] for x in graph.expand(["1"], as_of_date="2018-01-01")], ["2"])

    def test_depth_text_cycles_and_bounds(self):
        nodes = [dict(case(str(i)), node_type="Case") for i in range(1, 5)]
        nodes[2]["has_text"] = False
        edges = [dict(source_id="1", target_id="2"), dict(source_id="2", target_id="1"),
                 dict(source_id="2", target_id="3"), dict(source_id="3", target_id="4")]
        graph = Graph(nodes, edges)
        self.assertEqual([x["doc_id"] for x in graph.expand(["1"], hops=3, require_text=True)], ["2"])
        self.assertEqual([x["doc_id"] for x in graph.expand(["1"], hops=3)], ["2", "3", "4"])
        self.assertEqual(graph.expand(["1"], hops=3, exclude_ids=["2"]), [])
        self.assertEqual(graph.expand(["1"], hops=3, exclude_ids=["1"]), [])
        self.assertEqual(len(graph.expand(["1"], hops=3, max_nodes=1)), 1)
        with self.assertRaises(ValueError):
            graph.expand(["1"], hops=6)


if __name__ == "__main__":
    unittest.main()
