"""Normalize the two supplied JSON schemas and the land-dispute workbook.

IDs are strings. Every relationship is oriented citing document -> cited document.
Original inputs are never modified; disagreements are emitted for review.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path


def clean_string(value) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or ""))).strip()


def document_id(value=None, url=None) -> str | None:
    if isinstance(value, bool):
        return None
    text = str(value or "").strip()
    if re.fullmatch(r"[0-9]+(?:\.0)?", text):
        return str(int(text.split(".")[0])) if int(text.split(".")[0]) > 0 else None
    match = re.fullmatch(r"https?://(?:www\.)?indiankanoon\.org/doc/(\d+)/?(?:[?#].*)?", str(url or text))
    return str(int(match[1])) if match and int(match[1]) > 0 else None


def canonical_url(doc_id: str) -> str:
    return f"https://indiankanoon.org/doc/{doc_id}/"


def parse_year(value) -> int | None:
    try:
        result = int(str(value).split(".")[0])
        return result if 1800 <= result <= 2100 else None
    except (ValueError, TypeError):
        return None


def title_from_filename(filename) -> str:
    text = re.sub(r"\.pdf$", "", clean_string(filename), flags=re.I)
    text = re.sub(r"_\d+$", "", text)
    return clean_string(text.replace("_", " "))


def date_from_title(title: str) -> str | None:
    normalized = clean_string(title.replace("_", " ")).replace(",", "")
    match = re.search(r"\bon\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b", normalized, re.I)
    if not match:
        return None
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(" ".join(match.groups()), fmt).date().isoformat()
        except ValueError:
            continue
    return None


def meaningful_name(value) -> bool:
    text = clean_string(value)
    return bool(text and text.lower() not in {"indian kanoon - search engine for indian law", "indiankanoon.org"})


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_metadata(raw_dir: Path):
    import pandas as pd

    cases, edge_map, issues, input_files = {}, {}, [], []
    counters = {"citation_rows": 0, "land_rows": 0, "precedent_mentions": 0,
                "cited_by_mentions": 0, "duplicate_source_rows": 0}

    def case_for(doc_id):
        if doc_id not in cases:
            cases[doc_id] = {"doc_id": doc_id, "case_name": "", "year": None,
                "decision_date": None, "date_source": None, "url": canonical_url(doc_id),
                "filename": None, "original_path": None, "relative_pdf_path": None,
                "is_land_dispute": False, "has_citation_metadata": False,
                "has_text": False, "source_files": [], "source_records": [], "metadata_conflicts": []}
        return cases[doc_id]

    def merge(case, field, value, source):
        if value is None or value == "":
            return
        old = case.get(field)
        if old not in (None, "") and old != value:
            conflict = {"doc_id": case["doc_id"], "field": field, "kept": old,
                        "alternative": value, "source": source}
            case["metadata_conflicts"].append(conflict)
            issues.append({"reason": "metadata_conflict", **conflict})
        else:
            case[field] = value

    books = sorted(raw_dir.glob("*.xlsx"))
    if len(books) != 1:
        raise ValueError(f"Expected one land workbook in {raw_dir}, found {len(books)}")
    workbook = books[0]
    frame = pd.read_excel(workbook, dtype=object)
    frame = frame.where(pd.notna(frame), "")
    required = {"filename", "year", "path", "url", "doc id", "is_land_property_dispute"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Workbook is missing columns: {sorted(required - set(frame.columns))}")
    input_files.append({"path": workbook.name, "sha256": sha256(workbook), "rows": len(frame)})
    seen_land = set()
    for position, row in enumerate(frame.to_dict("records"), start=2):
        counters["land_rows"] += 1
        doc_id = document_id(row["doc id"], row["url"])
        url_id = document_id(url=row["url"])
        if not doc_id or (url_id and doc_id != url_id):
            issues.append({"reason": "invalid_land_id", "source": workbook.name, "row": position})
            continue
        if doc_id in seen_land:
            issues.append({"reason": "duplicate_land_id", "doc_id": doc_id, "row": position})
        seen_land.add(doc_id)
        case = case_for(doc_id)
        case["source_files"].append(workbook.name)
        case["source_records"].append({"file": workbook.name, "excel_row": position})
        case["is_land_dispute"] = str(row["is_land_property_dispute"]).strip().lower() in {"yes", "true", "1"}
        filename = clean_string(row["filename"])
        merge(case, "filename", filename, workbook.name)
        merge(case, "original_path", clean_string(row["path"]), workbook.name)
        merge(case, "year", parse_year(row["year"]), workbook.name)
        merge(case, "case_name", title_from_filename(filename), workbook.name)
        case["relative_pdf_path"] = f"{case['year']}/{filename}" if case["year"] else filename
        date = date_from_title(case["case_name"])
        if date:
            merge(case, "decision_date", date, workbook.name)
            case["date_source"] = "filename_silver"

    paths = sorted(raw_dir.glob("citations*.json"))
    if not paths:
        raise ValueError(f"No citations*.json files in {raw_dir}")
    citation_ids = set()
    for path in paths:
        records = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError(f"{path.name} must contain a JSON array")
        input_files.append({"path": path.name, "sha256": sha256(path), "rows": len(records)})
        for index, record in enumerate(records):
            counters["citation_rows"] += 1
            if not isinstance(record, dict):
                issues.append({"reason": "invalid_citation_record", "source": path.name, "row": index})
                continue
            source_id = document_id(record.get("source_doc_id"), record.get("source_url") or record.get("url"))
            if not source_id:
                issues.append({"reason": "invalid_source_id", "source": path.name, "row": index})
                continue
            explicit_id = document_id(record.get("source_doc_id"))
            url_id = document_id(url=record.get("source_url") or record.get("url"))
            if explicit_id and url_id and explicit_id != url_id:
                issues.append({"reason": "source_id_url_mismatch", "source": path.name, "row": index})
                continue
            counters["duplicate_source_rows"] += int(source_id in citation_ids)
            citation_ids.add(source_id)
            case = case_for(source_id)
            case["has_citation_metadata"] = True
            case["source_files"].append(path.name)
            case["source_records"].append({"file": path.name, "json_index": index})
            title = clean_string(clean_string(record.get("source_name") or record.get("case")).replace("_", " "))
            if meaningful_name(title):
                # Workbook filename has consistent complete dates; preserve its title.
                if not case["case_name"]:
                    case["case_name"] = title
                date = date_from_title(title)
                merge(case, "decision_date", date, path.name)
                if date and not case["date_source"]:
                    case["date_source"] = "citation_title_silver"
            year = parse_year(record.get("year"))
            merge(case, "year", year, path.name)
            if case["year"] is None and case["decision_date"]:
                case["year"] = int(case["decision_date"][:4])
            for relation in ("precedents", "cited_by"):
                targets = record.get(relation, [])
                if targets is None:
                    targets = []
                if not isinstance(targets, list):
                    issues.append({"reason": "invalid_reference_list", "source": path.name,
                                   "row": index, "relation": relation})
                    continue
                for ref_index, reference in enumerate(targets):
                    counters["precedent_mentions" if relation == "precedents" else "cited_by_mentions"] += 1
                    if not isinstance(reference, dict):
                        issues.append({"reason": "invalid_reference", "source": path.name, "row": index})
                        continue
                    target_id = document_id(reference.get("doc_id"), reference.get("url"))
                    if not target_id:
                        issues.append({"reason": "invalid_reference_id", "source": path.name, "row": index})
                        continue
                    explicit_target = document_id(reference.get("doc_id"))
                    target_url_id = document_id(url=reference.get("url"))
                    if explicit_target and target_url_id and explicit_target != target_url_id:
                        issues.append({"reason": "reference_id_url_mismatch", "source": path.name, "row": index})
                        continue
                    name = clean_string(clean_string(reference.get("name") or reference.get("case")).replace("_", " "))
                    citing, cited = (source_id, target_id) if relation == "precedents" else (target_id, source_id)
                    citing_title, cited_title = (title, name) if relation == "precedents" else (name, title)
                    key = (citing, cited)
                    if key not in edge_map:
                        edge_map[key] = {"source_id": citing, "target_id": cited,
                            "source_title": citing_title if meaningful_name(citing_title) else "",
                            "target_title": cited_title if meaningful_name(cited_title) else "",
                            "source_url": canonical_url(citing), "target_url": canonical_url(cited),
                            "source_files": [], "reference_sources": [], "occurrences": 0,
                            "source_records": []}
                    edge = edge_map[key]
                    edge["occurrences"] += 1
                    edge["source_files"].append(path.name)
                    edge["reference_sources"].append(relation)
                    edge["source_records"].append({"file": path.name, "json_index": index,
                        "field": relation, "reference_index": ref_index,
                        "raw_source_label": record.get("source_name") or record.get("case") or "",
                        "raw_reference_label": reference.get("name") or reference.get("case") or ""})
                    if not meaningful_name(edge["source_title"]) and meaningful_name(citing_title):
                        edge["source_title"] = citing_title
                    if not meaningful_name(edge["target_title"]) and meaningful_name(cited_title):
                        edge["target_title"] = cited_title

    for case in cases.values():
        case["source_files"] = sorted(set(case["source_files"]))
        case["case_name"] = case["case_name"] or f"Indian Kanoon document {case['doc_id']}"
        if case["decision_date"] and case["year"] != int(case["decision_date"][:4]):
            issues.append({"reason": "date_year_conflict", "doc_id": case["doc_id"],
                "year": case["year"], "decision_date": case["decision_date"]})
            case["metadata_conflicts"].append({"field": "decision_date", "reason": "date_year_conflict"})
            # Do not use disputed dates/years for temporal eligibility.
            case["decision_date"], case["year"] = None, None
        if any(c["field"] in {"year", "decision_date"} for c in case["metadata_conflicts"]):
            case["decision_date"], case["year"] = None, None
    for edge in edge_map.values():
        edge["source_files"] = sorted(set(edge["source_files"]))
        edge["reference_sources"] = sorted(set(edge["reference_sources"]))
    counters.update({"unique_citation_sources": len(citation_ids), "unique_land_ids": len(seen_land),
        "land_citation_overlap": len(seen_land & citation_ids), "metadata_cases": len(cases),
        "unique_directed_references": len(edge_map)})
    return ([cases[k] for k in sorted(cases, key=int)],
            [edge_map[k] for k in sorted(edge_map, key=lambda k: (int(k[0]), int(k[1])))],
            issues, input_files, counters)
