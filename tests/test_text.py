import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentic_law_data.text import build_records, clean_pages, extract_pdf, redact_contacts, section_spans


class TextTests(unittest.TestCase):
    def test_boundary_cleanup_does_not_strip_headings_or_body_numbers(self):
        pages, diagnostics = clean_pages([
            "SUPREME COURT ARCHIVE\nFacts\nSection 12 applies.\n42\nFooter archive\n1",
            "SUPREME COURT ARCHIVE\nFacts\nArticle 19 applies.\n37\nFooter archive\n2",
        ])
        self.assertNotIn("SUPREME COURT ARCHIVE", pages[0])
        self.assertIn("Facts", pages[0])
        self.assertIn("Section 12", pages[0])
        self.assertIn("42", pages[0])
        self.assertNotIn("Footer archive", pages[1])
        self.assertGreater(diagnostics[0]["removed_boundary_lines"], 0)

    def test_contacts_only_and_legal_numbers_remain(self):
        text, counts = redact_contacts(
            "Email: person@example.com\nPhone: +91 98765 43210\n"
            "Section 12345678, Article 19(1), (2020) 12 SCC 345 and 1234567890 remain."
        )
        self.assertEqual(counts, {"emails": 1, "phones": 1})
        self.assertIn("Section 12345678", text)
        self.assertIn("1234567890 remain", text)
        self.assertNotIn("98765", text)
        self.assertNotIn("person@example.com", text)

    def test_no_gold_labels_and_no_judgment_front_matter_mislabel(self):
        page = "Case title\nJUDGMENT\nThe court heard this matter."
        chunks, _ = build_records([page], "123", "case.pdf")
        self.assertEqual({c["section"] for c in chunks}, {"UNKNOWN"})
        self.assertEqual({c["label_source"] for c in chunks}, {"unlabeled"})

    def test_overlap_exact_page_offsets_and_determinism(self):
        pages = ["Facts\n" + " ".join(f"word{i}" for i in range(11)) + "\nIssues\nA question?",
                 "The question continues.\nDecision\nAppeal dismissed."]
        chunks, sentences = build_records(pages, "123", "case.pdf", chunk_words=5, overlap_words=2)
        again, _ = build_records(pages, "123", "case.pdf", chunk_words=5, overlap_words=2)
        self.assertEqual(chunks, again)
        facts = [c for c in chunks if c["section"] == "FACTS"]
        self.assertEqual(facts[0]["text"].split()[-2:], facts[1]["text"].split()[:2])
        for chunk in chunks:
            self.assertEqual(chunk["page_start"], chunk["page_end"])
            self.assertEqual(chunk["text"], pages[chunk["page_start"] - 1][chunk["char_start"]:chunk["char_end"]])
        for sentence in sentences:
            self.assertEqual(sentence["text"], pages[sentence["page"] - 1][sentence["char_start"]:sentence["char_end"]])
        self.assertIn("ISSUE", {c["section"] for c in chunks if c["page_start"] == 2})

    def test_invalid_overlap(self):
        with self.assertRaises(ValueError):
            build_records(["some text"], "123", "case.pdf", 5, 5)

    def test_real_pdf_extraction_with_synthetic_fixture(self):
        try:
            from reportlab.pdfgen import canvas
            import pdfplumber  # noqa: F401
        except ImportError:
            self.skipTest("optional reportlab/pdfplumber not installed")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic_judgment.pdf"
            pdf = canvas.Canvas(str(path))
            lines = ["SUPREME COURT OF INDIA", "DATE OF JUDGMENT: 19 May 1950", "Facts",
                     "The claimant asserts possession of the property.", "Issues",
                     "Whether the claimant has proved title?", "Decision", "The appeal is dismissed."]
            for i, line in enumerate(lines):
                pdf.drawString(60, 780 - 24 * i, line)
            pdf.save()
            result = extract_pdf(path, "123")
            self.assertEqual(result["metadata"]["decision_date"], "1950-05-19")
            self.assertEqual(result["metadata"]["court"], "SUPREME COURT OF INDIA")
            self.assertEqual(result["metadata"]["ocr_required_pages"], [])
            self.assertIn("FACTS", {c["section"] for c in result["chunks"]})

    def test_blank_pdf_is_flagged_without_invented_text(self):
        try:
            from reportlab.pdfgen import canvas
        except ImportError:
            self.skipTest("optional reportlab not installed")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blank.pdf"
            pdf = canvas.Canvas(str(path))
            pdf.showPage()
            pdf.save()
            result = extract_pdf(path, "123")
            self.assertEqual(result["chunks"], [])
            self.assertEqual(result["metadata"]["ocr_required_pages"], [1])
            self.assertIn("document_has_no_extractable_text", result["warnings"])


if __name__ == "__main__":
    unittest.main()
