"""Reproducible command-line metadata, text, citation-graph preparation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from .benchmark import build_benchmark
from .normalize import (load_metadata, meaningful_name, sha256, write_json, write_jsonl,
                        document_id, canonical_url, title_from_filename, date_from_title)


def resolve_pdfs(cases, pdf_root=None, manifest=None):
    """Exact manifest, portable year/filename, then unique filename; never fuzzy match."""
    manifest = manifest or {}
    index = {}
    if pdf_root:
        for path in sorted(Path(pdf_root).rglob("*")):
            if path.is_file() and path.suffix.lower() == ".pdf":
                index.setdefault(path.name.casefold(), []).append(path)
    result, issues = {}, []
    for case in cases:
        doc_id = case["doc_id"]
        if doc_id in manifest:
            path = Path(manifest[doc_id]).expanduser()
            if not path.is_absolute():
                if not pdf_root:
                    raise ValueError("Relative manifest paths require --pdf-root")
                path = Path(pdf_root) / path
            if not path.is_file() or path.suffix.lower() != ".pdf":
                issues.append({"reason": "missing_manifest_pdf", "doc_id": doc_id, "path": str(path)})
            else:
                result[doc_id] = path
            continue
        if not pdf_root:
            continue
        if not case.get("filename"):
            issues.append({"reason": "pdf_mapping_required", "doc_id": doc_id})
            continue
        path = Path(pdf_root) / case["relative_pdf_path"]
        if path.is_file():
            result[doc_id] = path
        else:
            candidates = index.get(case["filename"].casefold(), [])
            if len(candidates) == 1:
                result[doc_id] = candidates[0]
            elif len(candidates) > 1:
                issues.append({"reason": "ambiguous_pdf_filename", "doc_id": doc_id})
            else:
                issues.append({"reason": "missing_pdf", "doc_id": doc_id,
                               "expected_relative_path": case["relative_pdf_path"]})
    reverse = {}
    for doc_id, path in result.items():
        reverse.setdefault(str(path.resolve()), []).append(doc_id)
    for path, ids in reverse.items():
        if len(ids) > 1:
            for doc_id in ids:
                result.pop(doc_id)
            issues.append({"reason": "pdf_assigned_to_multiple_ids", "doc_ids": ids, "path": path})
    known = {c["doc_id"] for c in cases}
    for doc_id in sorted(set(manifest) - known):
        issues.append({"reason": "manifest_id_not_in_metadata", "doc_id": doc_id})
    return result, issues


def run(raw_dir: Path, out_dir: Path, pdf_root: Path | None = None,
        pdf_manifest: Path | None = None, cutoff_year: int = 2018,
        chunk_words: int = 350, overlap_words: int = 50,
        refresh_splits: bool = False) -> dict:
    from .graph import export_graph
    from .text import extract_pdf

    if not raw_dir.is_dir():
        raise ValueError(f"Raw data directory does not exist: {raw_dir}")
    if pdf_root and not pdf_root.is_dir():
        raise ValueError(f"PDF corpus directory does not exist: {pdf_root}")
    if chunk_words <= 0 or not 0 <= overlap_words < chunk_words:
        raise ValueError("Require 0 <= overlap_words < chunk_words")
    cases, references, issues, inputs, counters = load_metadata(raw_dir)
    manifest = json.loads(pdf_manifest.read_text(encoding="utf-8")) if pdf_manifest else {}
    if not isinstance(manifest, dict) or any(not isinstance(v, str) for v in manifest.values()):
        raise ValueError("PDF manifest must be a JSON object of doc_id -> path strings")
    known = {c["doc_id"] for c in cases}
    for ident, filename in manifest.items():
        if document_id(ident) != ident:
            raise ValueError(f"Manifest key must be a canonical positive document ID: {ident!r}")
        if ident in known:
            continue
        # Explicit manifests can introduce text-only judgments absent from the
        # supplied citation/land subsets. Identity is supplied, never guessed.
        title = title_from_filename(Path(filename).name)
        date = date_from_title(title)
        cases.append({"doc_id": ident, "case_name": title or f"Indian Kanoon document {ident}",
            "year": int(date[:4]) if date else None, "decision_date": date,
            "date_source": "manifest_filename_silver" if date else None,
            "url": canonical_url(ident), "filename": Path(filename).name,
            "original_path": filename, "relative_pdf_path": filename,
            "is_land_dispute": False, "has_citation_metadata": False, "has_text": False,
            "source_files": [pdf_manifest.name], "source_records": [{"file": pdf_manifest.name, "manifest_key": ident}],
            "metadata_conflicts": []})
    cases.sort(key=lambda c: int(c["doc_id"]))
    counters["manifest_added_cases"] = len(cases) - len(known)
    counters["metadata_cases"] = len(cases)
    if pdf_manifest:
        inputs.append({"path": pdf_manifest.name, "sha256": sha256(pdf_manifest), "rows": len(manifest)})
    pdfs, pdf_issues = resolve_pdfs(cases, pdf_root, manifest)
    issues.extend(pdf_issues)
    pages, chunks, sentences = [], [], []
    failed = 0
    for case in cases:
        path = pdfs.get(case["doc_id"])
        if path is None:
            continue
        try:
            record = extract_pdf(path, case["doc_id"], chunk_words=chunk_words, overlap_words=overlap_words)
        except Exception as error:
            # A corrupt/encrypted PDF does not silently become a complete text record.
            issues.append({"reason": "pdf_extraction_failed", "doc_id": case["doc_id"],
                           "path": str(path), "error": f"{type(error).__name__}: {error}"})
            failed += 1
            continue
        unusable_pages = set(record["metadata"].get("ocr_required_pages", []))
        for page in record["pages"]:
            page["usable_text"] = page["page"] not in unusable_pages
        record["chunks"] = [c for c in record["chunks"] if c["page_start"] not in unusable_pages]
        record["sentences"] = [s for s in record["sentences"] if s["page"] not in unusable_pages]
        case["has_text"] = bool(record["chunks"])
        case["source_pdf"] = str(path.relative_to(pdf_root)) if pdf_root and path.is_relative_to(pdf_root) else path.name
        case["source_pdf_sha256"] = sha256(path)
        case["extracted_metadata"] = record["metadata"]
        pdf_date = record["metadata"].get("decision_date")
        if pdf_date and not any(c.get("field") in {"year", "decision_date"} for c in case["metadata_conflicts"]):
            conflict = ((case["decision_date"] and case["decision_date"] != pdf_date)
                        or (case["year"] is not None and case["year"] != int(pdf_date[:4])))
            if conflict:
                case["metadata_conflicts"].append({"field": "decision_date", "metadata_date": case["decision_date"],
                    "metadata_year": case["year"], "pdf_date": pdf_date, "source": case["source_pdf"]})
                issues.append({"reason": "pdf_date_conflict", "doc_id": case["doc_id"], "pdf_date": pdf_date})
                case["decision_date"], case["year"] = None, None
            else:
                case["decision_date"], case["year"] = pdf_date, int(pdf_date[:4])
                case["date_source"] = "pdf_explicit_header_silver"
        case["text_warnings"] = record["warnings"]
        case["text_fingerprint"] = hashlib.sha256(json.dumps(record["pages"], sort_keys=True).encode()).hexdigest()
        pages.extend(record["pages"])
        chunks.extend(record["chunks"])
        sentences.extend(record["sentences"])
        for warning in record["warnings"]:
            issues.append({"reason": "pdf_warning", "doc_id": case["doc_id"], "warning": warning})
    out_dir.mkdir(parents=True, exist_ok=True)
    # Validate frozen identity before replacing any previous generated output.
    benchmark = build_benchmark(cases, references, chunks, inputs, out_dir, cutoff_year, refresh_splits)
    write_jsonl(out_dir / "cases.jsonl", cases)
    write_jsonl(out_dir / "references.jsonl", references)
    write_jsonl(out_dir / "pages.jsonl", pages)
    write_jsonl(out_dir / "chunks.jsonl", chunks)
    write_jsonl(out_dir / "sentences.jsonl", sentences)
    write_jsonl(out_dir / "metadata_issues.jsonl", issues)
    with (out_dir / "cases.csv").open("w", encoding="utf-8", newline="") as stream:
        fields = ["doc_id", "case_name", "year", "decision_date", "url", "is_land_dispute",
                  "has_citation_metadata", "has_text", "relative_pdf_path"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(cases)
    graph_stats = export_graph(cases, references, out_dir / "graph")
    report = {"schema_version": "1.0", "inputs": inputs, "metadata": counters,
        "text": {"matched_pdfs": len(pdfs), "failed_pdfs": failed,
                 "cases_with_text": sum(c["has_text"] for c in cases), "pages": len(pages),
                 "chunks": len(chunks), "sentences": len(sentences),
                 "pages_requiring_ocr_review": sum(not p["usable_text"] for p in pages)},
        "graph": graph_stats, "benchmark": {"status": benchmark["status"],
            "metadata_test_candidates": len(benchmark["metadata_land_citation_candidate_ids"]),
            "test_cases_with_text": len(benchmark["test_case_ids"]),
            "query_drafts": len(benchmark["silver_query_ids_needing_review"]),
            "qrels": benchmark["silver_qrels_count"]},
        "issues_by_reason": dict(sorted(Counter(i["reason"] for i in issues).items())),
        "cases_with_unknown_year": sum(c["year"] is None for c in cases),
        "placeholder_names_remaining": sum(not meaningful_name(c["case_name"]) or
             c["case_name"].startswith("Indian Kanoon document ") for c in cases),
        "limitations": ["Judgment PDFs must be supplied separately; proposal PDF is not corpus data.",
            "No model training, legal advice, evaluation scores, or full anonymization is claimed.",
            "External graph resource type is heuristic and court/date/text may be unknown.",
            "Rhetorical labels and historical-citation qrels are silver and need review.",
            "Phone/email redaction is limited; sensitive case content needs separate manual review.",
            "Proposal's 7,497 citations is not the observed count; see metadata.citation_rows."]}
    write_json(out_dir / "quality_report.json", report)
    write_json(out_dir / "run_manifest.json", {"schema_version": "1.0", "pipeline_version": "1.0.0",
        "cutoff_year": cutoff_year, "chunk_words": chunk_words, "overlap_words": overlap_words,
        "inputs": inputs, "benchmark_fingerprint": benchmark["fingerprint"],
        "artifacts": {str(path.relative_to(out_dir)): sha256(path) for path in sorted(out_dir.rglob("*"))
                      if path.is_file() and path.name != "run_manifest.json"}})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--pdf-root", type=Path)
    parser.add_argument("--pdf-manifest", type=Path)
    parser.add_argument("--cutoff-year", type=int, default=2018)
    parser.add_argument("--chunk-words", type=int, default=350)
    parser.add_argument("--overlap-words", type=int, default=50)
    parser.add_argument("--refresh-splits", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run(**vars(args))
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, f"Pipeline error: {error}\n")
    print(json.dumps({"metadata": report["metadata"], "text": report["text"],
                      "graph": report["graph"], "benchmark": report["benchmark"]}, indent=2))
    return 0
