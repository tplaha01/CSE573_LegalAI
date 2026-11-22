"""Data-contract and leakage regression tests, runnable without pytest."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentic_law_data.normalize import document_id, date_from_title, load_metadata
from agentic_law_data.benchmark import build_benchmark, strictly_earlier
from agentic_law_data.pipeline import resolve_pdfs
from agentic_law_data.pipeline import run


def case(ident, year, text=True, land=True, date=None):
    return {"doc_id": ident, "case_name": f"Party {ident} vs State", "year": year,
            "decision_date": date, "has_text": text, "is_land_dispute": land,
            "has_citation_metadata": True, "metadata_conflicts": [],
            "text_fingerprint": ident}


class NormalizationTests(unittest.TestCase):
    def test_id_normalization_rejects_foreign_urls_and_boolean(self):
        self.assertEqual(document_id(123.0), "123")
        self.assertEqual(document_id(url="http://indiankanoon.org/doc/123/"), "123")
        self.assertIsNone(document_id(url="https://example.com/doc/123/"))
        self.assertIsNone(document_id(True))
        self.assertIsNone(document_id("0"))
        self.assertEqual(date_from_title("A_vs_B_on_14_March_1950"), "1950-03-14")

    def test_duplicate_union_and_cited_by_orientation(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "land.xlsx").write_bytes(b"mocked-workbook-input")
            (root / "citations.json").write_text(json.dumps([
                {"case": "A vs B on 1 January, 2018", "year": "2018", "url": "https://indiankanoon.org/doc/1/",
                 "precedents": [{"case": "Section 12", "url": "https://indiankanoon.org/doc/2/"}]}]))
            (root / "citations_2.json").write_text(json.dumps([
                {"source_doc_id": "1", "source_name": "Indian Kanoon - Search engine for Indian Law",
                 "precedents": [{"name": "C vs D", "doc_id": "3"}],
                 "cited_by": [{"name": "E vs F", "doc_id": "4"}]}]))
            frame = pd.DataFrame([{"filename": "A_vs_B_on_1_January_2018_1.PDF", "year": 2018,
                "path": "/content/drive/2018/a.PDF", "url": "https://indiankanoon.org/doc/1/",
                "doc id": 1, "is_land_property_dispute": "yes"}])
            with patch("pandas.read_excel", return_value=frame):
                cases, refs, issues, _, counts = load_metadata(root)
            self.assertEqual(counts["duplicate_source_rows"], 1)
            self.assertEqual({(r["source_id"], r["target_id"]) for r in refs}, {("1", "2"), ("1", "3"), ("4", "1")})
            self.assertEqual(cases[0]["decision_date"], "2018-01-01")
            self.assertEqual(cases[0]["relative_pdf_path"], "2018/A_vs_B_on_1_January_2018_1.PDF")
            self.assertEqual(len(refs[0]["source_records"]), 1)
            self.assertEqual(issues, [])


class BenchmarkTests(unittest.TestCase):
    def test_strict_chronology_and_conflicts(self):
        query = case("10", 2018, date="2018-05-20")
        self.assertTrue(strictly_earlier(case("1", 2018, date="2018-04-20"), query))
        self.assertFalse(strictly_earlier(case("1", 2018), query))
        self.assertFalse(strictly_earlier(case("1", None), query))
        self.assertFalse(strictly_earlier(query, query))
        bad = case("2", 2010)
        bad["metadata_conflicts"] = [{"field": "year"}]
        self.assertFalse(strictly_earlier(bad, query))

    def test_metadata_only_does_not_fabricate_benchmark(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_benchmark([case("1", 2018, text=False)], [], [], [], Path(tmp))
            self.assertEqual(result["metadata_land_citation_candidate_ids"], ["1"])
            self.assertEqual(result["test_case_ids"], [])
            self.assertEqual(result["status"], "pending_pdf_corpus")
            self.assertFalse(result["frozen"])

    def test_silver_qrels_exclude_future_and_cited_by_only(self):
        cases = [case("1", 2010), case("2", 2020), case("3", 2019), case("4", 2011)]
        refs = [{"source_id": "3", "target_id": ident, "reference_sources": [direction]}
                for ident, direction in [("1", "precedents"), ("2", "precedents"), ("4", "cited_by")]]
        chunks = [{"doc_id": "3", "section": "FACTS", "text": "Ownership AIR 2010 SC 12."}]
        with tempfile.TemporaryDirectory() as tmp:
            result = build_benchmark(cases, refs, chunks, [], Path(tmp))
            qrels = [json.loads(line) for line in (Path(tmp) / "qrels.jsonl").read_text().splitlines()]
            self.assertEqual([r["doc_id"] for r in qrels], ["1"])
            self.assertEqual(result["silver_query_ids_needing_review"], ["3"])
            query = json.loads((Path(tmp) / "benchmark_queries.jsonl").read_text())
            self.assertEqual(query["review_status"], "needs_human_review")
            self.assertNotIn("AIR 2010 SC 12", query["query"])

    def test_frozen_benchmark_rejects_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            cases = [case("1", 2018)]
            first = build_benchmark(cases, [], [], [], out)
            self.assertTrue(first["frozen"])
            self.assertEqual(first, build_benchmark(cases, [], [], [], out))
            with self.assertRaises(ValueError):
                build_benchmark(cases, [], [], [], out, cutoff_year=2017)
            refreshed = build_benchmark(cases, [], [], [], out, cutoff_year=2017, refresh_splits=True)
            self.assertNotEqual(first["fingerprint"], refreshed["fingerprint"])

    def test_frozen_queries_cannot_change_and_overlaps_are_deduplicated(self):
        cases = [case("1", 2010), case("2", 2018)]
        refs = [{"source_id": "2", "target_id": "1", "reference_sources": ["precedents"]}]
        chunks = [{"doc_id": "2", "section": "FACTS", "page_start": 1,
                   "char_start": 0, "char_end": 16, "text": "alpha beta gamma"},
                  {"doc_id": "2", "section": "FACTS", "page_start": 1,
                   "char_start": 11, "char_end": 22, "text": "gamma delta"}]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            build_benchmark(cases, refs, chunks, [], out)
            content = (out / "benchmark_queries.jsonl").read_text()
            self.assertEqual(json.loads(content)["query"].count("gamma"), 1)
            chunks[1]["text"] = "gamma other"
            with self.assertRaises(ValueError):
                build_benchmark(cases, refs, chunks, [], out)
            self.assertEqual((out / "benchmark_queries.jsonl").read_text(), content)


class PdfPipelineIntegrationTests(unittest.TestCase):
    def test_explicit_dates_promote_and_ocr_scraps_are_not_model_inputs(self):
        try:
            from reportlab.pdfgen import canvas
        except ImportError:
            self.skipTest("Install requirements-dev.txt for synthetic PDF integration tests")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_root = root / "pdfs"
            pdf_root.mkdir()
            path = pdf_root / "actual.pdf"
            pdf = canvas.Canvas(str(path))
            for i, line in enumerate(["DATE OF JUDGMENT: 1 January 2018", "Facts",
                "The parties dispute ownership and possession of a parcel of land."]):
                pdf.drawString(50, 750 - i * 24, line)
            pdf.showPage()
            pdf.drawString(50, 750, "WATERMARK")
            pdf.save()
            manifest = root / "mapping.json"
            manifest.write_text(json.dumps({"5": "actual.pdf"}))
            c = case("5", None, text=False)
            c.update({"filename": None, "case_name": "Unknown", "date_source": None,
                      "source_files": [], "source_records": [], "url": "https://indiankanoon.org/doc/5/"})
            with patch("agentic_law_data.pipeline.load_metadata", return_value=([c], [], [], [], {})):
                report = run(root, root / "out", pdf_root, manifest)
            stored = json.loads((root / "out/cases.jsonl").read_text())
            self.assertEqual(stored["decision_date"], "2018-01-01")
            self.assertEqual(stored["date_source"], "pdf_explicit_header_silver")
            self.assertEqual(report["text"]["pages_requiring_ocr_review"], 1)
            self.assertTrue(stored["has_text"])
            chunks = [json.loads(line) for line in (root / "out/chunks.jsonl").read_text().splitlines()]
            self.assertEqual({c["page_start"] for c in chunks}, {1})

    def test_new_manifest_id_adds_text_only_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "mapping.json"
            manifest.write_text(json.dumps({"42": "missing.pdf"}))
            with patch("agentic_law_data.pipeline.load_metadata", return_value=([], [], [], [], {})):
                report = run(root, root / "out", root, manifest)
            self.assertEqual(report["metadata"]["manifest_added_cases"], 1)
            stored = json.loads((root / "out/cases.jsonl").read_text())
            self.assertFalse(stored["has_citation_metadata"])
            self.assertFalse(stored["has_text"])
            self.assertEqual(stored["doc_id"], "42")


class PdfMappingTests(unittest.TestCase):
    def test_ambiguous_filename_and_duplicate_assignment_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for folder in ("a", "b"):
                (root / folder).mkdir()
                (root / folder / "case.PDF").write_bytes(b"not-opened")
            cases = [{"doc_id": "1", "filename": "case.PDF", "relative_pdf_path": "2018/case.PDF"}]
            mapped, issues = resolve_pdfs(cases, root)
            self.assertEqual(mapped, {})
            self.assertEqual(issues[0]["reason"], "ambiguous_pdf_filename")
            cases.append({"doc_id": "2", "filename": None})
            mapped, issues = resolve_pdfs(cases, root, {"1": "a/case.PDF", "2": "a/case.PDF"})
            self.assertEqual(mapped, {})
            self.assertEqual(issues[0]["reason"], "pdf_assigned_to_multiple_ids")


if __name__ == "__main__":
    unittest.main()
