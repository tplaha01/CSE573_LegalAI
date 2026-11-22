"""Prepare temporal partitions and silver citation qrels, never invent queries.

This is a data handoff, not Tarandeep's scoring harness. Metadata-only partitions
remain pending. A materialized benchmark is frozen against input/text hashes.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .normalize import write_json, write_jsonl


def strictly_earlier(candidate: dict, query: dict) -> bool:
    if candidate["doc_id"] == query["doc_id"]:
        return False
    if candidate.get("metadata_conflicts") or query.get("metadata_conflicts"):
        return False
    if query.get("decision_date") and candidate.get("decision_date"):
        return candidate["decision_date"] < query["decision_date"]
    return (candidate.get("year") is not None and query.get("year") is not None
            and candidate["year"] < query["year"])


def mask_citations(text: str) -> str:
    """Best effort only. Human review is required before a query is approved."""
    patterns = [r"https?://\S+", r"\b(?:AIR\s+\d{4}\s+\w+\s+\d+)",
                r"\(?\b\d{4}\)?\s*\d*\s*SCC(?:\s*\([^)]*\))?\s*\d+",
                r"\b(?:supra|ibid)\.?\b"]
    for pattern in patterns:
        text = re.sub(pattern, "[CITATION REMOVED]", text, flags=re.I)
    return text


def build_benchmark(cases: list[dict], references: list[dict], chunks: list[dict],
                    input_files: list[dict], out_dir: Path, cutoff_year: int = 2018,
                    refresh_splits: bool = False) -> dict:
    lookup = {case["doc_id"]: case for case in cases}
    metadata_pool = [c for c in cases if c["is_land_dispute"] and c["has_citation_metadata"]]
    text_pool = [c for c in metadata_pool if c["has_text"] and c["year"] is not None]
    scope = "land_disputes"
    if not text_pool:
        text_pool = [c for c in cases if c["has_text"] and c["has_citation_metadata"] and c["year"] is not None]
        scope = "all_citation_sources" if text_pool else "pending"
    train = sorted((c["doc_id"] for c in cases if c["has_text"] and c["year"] is not None and c["year"] < cutoff_year), key=int)
    test_pool = sorted((c["doc_id"] for c in text_pool if c["year"] >= cutoff_year), key=int)
    development = sorted((c["doc_id"] for c in text_pool if c["year"] < cutoff_year), key=int)
    unknown = sorted((c["doc_id"] for c in cases if c["has_text"] and c["year"] is None), key=int)
    data_identity = {"benchmark_version": "1.0", "inputs": input_files, "cutoff_year": cutoff_year,
        "text_hashes": sorted((c["doc_id"], c.get("text_fingerprint", "")) for c in cases if c["has_text"])}
    split_path = out_dir / "split_manifest.json"
    by_source = {}
    for ref in references:
        # Historical outgoing precedents alone are silver labels. Future cited_by is not.
        if "precedents" not in ref.get("reference_sources", []):
            continue
        source, target = ref["source_id"], ref["target_id"]
        if source in lookup and target in lookup and lookup[target]["has_text"] and strictly_earlier(lookup[target], lookup[source]):
            by_source.setdefault(source, set()).add(target)
    # Reconstruct page-local unions so overlap used for retrieval is not repeated
    # in the query. Chunks are exact slices; their offsets retain provenance.
    facts = {}
    for chunk in chunks:
        if str(chunk.get("section", "")).lower() in {"facts", "issue", "issues"}:
            facts.setdefault(chunk["doc_id"], []).append(chunk)
    queries, qrels = [], []
    for query_id in test_pool:
        positives = sorted(by_source.get(query_id, []), key=int)
        if not positives or not facts.get(query_id):
            continue
        pieces, last_end, last_page = [], 0, None
        for chunk in sorted(facts[query_id], key=lambda c: (c.get("page_start", 0), c.get("char_start", 0))):
            page = chunk.get("page_start", 0)
            start = chunk.get("char_start", 0)
            end = chunk.get("char_end", start + len(chunk["text"]))
            trim = max(0, last_end - start) if page == last_page else 0
            if trim < len(chunk["text"]):
                pieces.append(chunk["text"][trim:])
            last_end = max(last_end, end) if page == last_page else end
            last_page = page
        query_text = mask_citations("\n".join(pieces))
        # Mask known reference labels too; incomplete citations still need human review.
        cited_names = [lookup[t]["case_name"] for t in positives]
        for name in sorted(cited_names, key=len, reverse=True):
            if len(name) > 12:
                query_text = re.sub(re.escape(name), "[CASE NAME REMOVED]", query_text, flags=re.I)
        queries.append({"query_id": query_id, "doc_id": query_id, "query": query_text,
            "year": lookup[query_id]["year"], "decision_date": lookup[query_id]["decision_date"],
            "query_source": "explicit_facts_issues_silver", "review_status": "needs_human_review",
            "exclude_doc_ids": [query_id], "temporal_policy": "strictly_earlier"})
        qrels.extend({"query_id": query_id, "doc_id": target, "relevance": 1,
                      "label_source": "historical_citation_silver"} for target in positives)
    data_identity.update({"queries": queries, "qrels": qrels, "train_ids": train,
                          "test_case_ids": test_pool, "development_ids": development})
    fingerprint = hashlib.sha256(json.dumps(data_identity, sort_keys=True).encode()).hexdigest()
    if split_path.exists():
        old = json.loads(split_path.read_text(encoding="utf-8"))
        if old.get("frozen") and old.get("fingerprint") != fingerprint and not refresh_splits:
            raise ValueError("Frozen benchmark differs from inputs, queries, qrels, or cutoff. Use a NEW output directory, or explicitly --refresh-splits before retraining all compared systems.")
    result = {"schema_version": "1.0", "cutoff_year": cutoff_year,
        "status": "pending_pdf_corpus" if not any(c["has_text"] for c in cases) else
                  ("frozen_candidates_need_human_review" if test_pool else "pending_eligible_test_cases"),
        "frozen": bool(test_pool), "fingerprint": fingerprint, "scope": scope,
        "metadata_land_citation_candidate_ids": sorted((c["doc_id"] for c in metadata_pool if c["year"] is not None and c["year"] >= cutoff_year), key=int),
        "train_text_ids": train, "development_query_ids": development,
        "test_case_ids": test_pool, "text_ids_with_unknown_year": unknown,
        "silver_query_ids_needing_review": [q["query_id"] for q in queries],
        "silver_qrels_count": len(qrels), "gold_review_complete": False,
        "notes": ["No automatic cutoff adjustment; change explicitly before tuning.",
                  "Empty text/query outputs are pending, not evidence of zero retrieval quality.",
                  "Citation relevance is incomplete silver supervision; it does not establish support.",
                  "Query redaction is heuristic and requires human review.",
                  "Graph retrieval must exclude query node and filter future edges at every hop."]}
    write_json(split_path, result)
    write_jsonl(out_dir / "benchmark_queries.jsonl", queries)
    write_jsonl(out_dir / "qrels.jsonl", qrels)
    return result
