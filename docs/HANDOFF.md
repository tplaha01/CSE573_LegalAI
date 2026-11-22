# Team handoff

This document defines how the other workstreams can build on Yashwardhan's data pipeline without changing document identity, losing provenance, or contaminating evaluation.

## 1. Agree on the shared snapshot

Run the metadata pipeline once, inspect `quality_report.json`, and share the resulting output folder. When judgment PDFs become available, rerun extraction and review its failures before freezing the modeling benchmark.

The raw files are the source of truth. Do not edit them to fix a downstream result. Put normalization fixes in code, rerun the pipeline, and document the changed output snapshot. Input hashes and split metadata make the chosen version traceable.

The supplied package includes metadata and citation graph outputs. It has **zero real judgment text records** because the attachments contain no judgment PDFs. These outputs support graph/data integration immediately; classification and retrieval training require the PDF corpus.

## 2. Shared identifiers and joins

Use `doc_id` as a **string**, never a case title, filename, integer row index, or floating-point number. The same Indian Kanoon ID identifies a resource throughout the package.

| Source | Identity and mapping |
|---|---|
| Land workbook | `doc id`, checked against the ID in `url` |
| Standard citation JSON | ID parsed from `url` |
| Alternate citation JSON | `source_doc_id`, checked against `source_url` |
| Reference entry | `doc_id` if supplied, otherwise the ID in its URL |
| PDF | Matched by a known case's portable path or an explicit manifest |

Join `chunks`, `pages`, and `sentences` to `cases` on `doc_id`. Join graph nodes to cases by document ID; graph exports also include external resources absent from `cases.jsonl`.

Duplicate source records contribute the **union** of their references. They are not independent training examples. A title can be absent or unreliable while its ID remains valid.

## 3. Case and reference contracts

Core fields in `cases.jsonl`:

| Field | Meaning |
|---|---|
| `doc_id` | Stable Indian Kanoon resource ID, encoded as a string |
| `case_name` | Normalized source/filename title; a fallback can indicate unknown title |
| `year` | Integer decision year, or null when unavailable/disputed |
| `decision_date` | ISO date if defensibly extracted from metadata, otherwise null |
| `date_source` | Provenance for a parsed date; filename/title dates are silver metadata |
| `url` | Canonical HTTPS Indian Kanoon URL |
| `filename`, `original_path`, `relative_pdf_path` | Original and portable file mapping information |
| `is_land_dispute` | Membership in the supplied filtered workbook, not a new classifier prediction |
| `has_citation_metadata` | A source citation record was provided |
| `has_text` | Usable judgment text was extracted during this run |
| `source_files` | Inputs contributing to this metadata record |
| `source_records` | Exact contributing JSON indices, workbook rows, or manifest keys |
| `metadata_conflicts` | Recorded disagreements for review |

The workbook's `classification=Judgment` describes a document type. It does **not** label a sentence as facts, issue, reasoning, or decision. Its land-dispute flag does not supply ownership/tenancy/partition subtype gold labels.

Core fields in `references.jsonl`:

| Field | Meaning |
|---|---|
| `source_id`, `target_id` | Citing document and cited resource, respectively |
| `source_title`, `target_title` | Available source labels; they may be incomplete |
| `source_url`, `target_url` | Canonical resource URLs |
| `source_files` | Citation files containing the relation |
| `reference_sources` | Original relation lists, such as `precedents` or `cited_by` |
| `occurrences` | Raw observations merged into this directed pair |
| `source_records` | Exact input file/record/list indices and original labels |

For `cited_by`, an entry under document A saying B cited A becomes **B → A**. It must never be exported as A → B. The edge alone expresses no legal treatment or support judgment.

## 4. Connect the PDF corpus

For land cases, the preferred directory layout is `<pdf_root>/<year>/<filename>`. Keep the corpus outside Git. Preserve the original workbook paths for provenance, but do not hard-code their Colab root into teammates' machines.

Use a JSON manifest when a file cannot be identified from the standard layout:

```json
{
  "1780900": "1950/Abdulla_Ahmed_vs_Animendra_Kissen_Mitter_on_14_March_1950_1.PDF",
  "378583": "1950/custom_filename.pdf"
}
```

Manifest keys must be authoritative numeric Indian Kanoon IDs. A key absent from
the metadata adds a text-only case with no supplied outgoing citation record.
This is how the remainder of the 26,688-PDF corpus can be ingested without
guessing identity. Resolve relative paths under `--pdf-root`; absolute paths
are supported. A manifest provides identity mapping, not evidence that a file
is a judgment. Check representative mappings manually.

```bash
python run_pipeline.py --raw-dir data/raw --out-dir data/processed --pdf-root /datasets/supreme_court_judgments --pdf-manifest mapping.json
```

Inspect extraction warnings for missing files, image-only pages, corrupt PDFs, and low text coverage. OCR is a separate preprocessing step. Never replace missing judgment text with a metadata title or the proposal's text.

Chunks stay within page and section boundaries. Their character offsets refer to the cleaned, redacted page text, not raw PDF byte positions. Preserve `chunk_id`, `doc_id`, page location, section, source file, and text hash when creating embeddings or a vector store.

Pages with fewer than 20 alphabetic characters are flagged for OCR/manual
review and excluded from chunks/sentences. This is an extraction-quality
heuristic, not an OCR detector. Pages retain `usable_text`; explicit PDF-header
dates enrich case metadata, and disagreements are flagged and excluded from
historical eligibility.

## 5. Jhon: classification and retrieval

Read JSONL without converting IDs to integers:

```python
import json
from pathlib import Path

def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)

cases = {row["doc_id"]: row for row in read_jsonl("data/processed/cases.jsonl")}
chunks = list(read_jsonl("data/processed/chunks.jsonl"))
sentences = list(read_jsonl("data/processed/sentences.jsonl"))
```

For rhetorical-role models, use only reviewed labels or explicitly identified silver labels. Preserve `UNKNOWN`; do not invent a label from paragraph position. Review the proposal's approximately 50-judgment sample before treating section rules as trustworthy targets.

Split at **case level before training**, not by random sentences or chunks. Every sentence and chunk from one judgment must remain in the same partition. Fit TF-IDF vocabulary, feature selection, and any learned preprocessing on training data. Do not tune on the held-out test set.

For retrieval, index usable chunks with stable IDs and provenance. Apply the query's historical eligibility filter to candidate judgments. Do not let the query judgment retrieve its own chunks. Preserve the same query set and relevance labels when comparing BM25, dense, and hybrid retrieval.

## 6. Anushka: RAG and Graph-RAG

The offline graph works without a database server. From this project folder:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))
from agentic_law_data.graph import Graph

graph = Graph.from_directory(Path("data/processed/graph"))
# Replace these with document IDs returned by the text retriever.
seed_ids = ["1780900"]
neighbors = graph.expand(
    seed_ids,
    direction="outgoing",
    hops=1,
    as_of_year=2018,
    require_text=True,
    case_only=True,
    exclude_ids=[],  # Set to [held_out_query_doc_id] for a benchmark query.
)
```

With the supplied metadata-only outputs, `require_text=True` should return no usable text neighbors. This is expected. Use `require_text=False` for graph inspection, not as a claim that evidence passages exist.

Temporal graph cutoffs are strict: `as_of_year=2018` permits records before 2018; it does not permit all of 2018. Use `as_of_date` when a reliable query date is available. Unknown dates are excluded under an active cutoff. Seeds must also satisfy the filter. This is suitable for expanding already retrieved prior cases; do not seed expansion with the held-out query judgment.

Treat the graph as a route to candidate evidence. Retrieve actual passages for each added case and retain their provenance. The graph cannot by itself establish that a passage supports a generated claim. Cap expansion to avoid overwhelming the context window, and evaluate whether graph expansion improves retrieval.

For Neo4j, follow the files in `neo4j/`. The graph CSVs contain external resource stubs as well as corpus cases. Preserve their resource type and metadata uncertainty during import. Add `APPLIES`, `HAS_RATIO`, `HAS_ISSUE`, or `OVERRULES` only when a later component extracts and validates those relationships with evidence.

## 7. Tarandeep: evaluation and freezing

Use `quality_report.json` to distinguish metadata coverage from text coverage. Do not count 558 metadata candidates as 558 executable test queries.

The intended test pool consists of cases decided in 2018 or later; earlier cases support development. Citation-based queries need source citation metadata **and** judgment text. The land subset is the preferred domain. Missing text leaves the benchmark pending.

Only earlier eligible judgments with usable text can be relevant retrieval targets. Date comparisons should be strict. If only a year is reliable, exclude same-year candidates because their relative order is unknown. Exclude disputed or unknown dates from temporal eligibility.

Freeze the selected snapshot before model tuning. Rebuilding a frozen split against changed inputs should require an explicit refresh. `--refresh-splits` is a deliberate dataset-version change, not a way to keep tuning until test results improve. Retain the old manifest and label any later comparison with its new snapshot.

`split_manifest.json` records `train_text_ids`, `development_query_ids`,
`test_case_ids`, and `silver_query_ids_needing_review`. `frozen=true` freezes
candidate identities and derived query/qrel content; it does not mean gold
review is complete. Read `gold_review_complete` and each query's
`review_status=needs_human_review`. The pipeline stops before overwriting a
changed frozen benchmark. Save human approvals in a separate review file;
do not edit auto-generated outputs and expect them to survive a rebuild.

If no text-bearing land/citation overlap exists, the query pool falls back to
all text-bearing citation sources and records that scope. It never moves the
2018 cutoff automatically. When the test pool is too small, the team must agree
on a cutoff before tuning and regenerate every compared system consistently.

Use query facts/issues with explicit citations removed. Treat citation qrels as **partial silver labels**: a court's citation list is not an exhaustive list of relevant cases. Review query text for residual case names and citation clues. Keep the query judgment's known citation edges, future citing cases, and outcome text out of the retrieval context.

Human review still owns the gold sample, legal support judgments, unsupported-claim labels, and calibration of any LLM judge. This package does not supply gold legal answers or an accuracy claim.

## 8. Shared Git workflow

1. Create one shared repository from this folder and agree on a stable main branch.
2. Each teammate uses a separate branch, such as `jhon/retrieval`, `anushka/rag`, or `tarandeep/evaluation`.
3. Preserve the `agentic_law_data` module's contracts. Discuss a schema change before merging it; update example consumers and tests together.
4. Keep raw PDFs, credentials, machine-specific paths, embeddings, and large model files outside Git. Share the agreed metadata snapshot through the team's approved file location.
5. Run `python -m unittest discover -s tests -v` and the pipeline on a small PDF sample before opening a pull request.
6. Review the quality report and split manifest when a change affects data, then merge through a pull request.

Do not change IDs to resolve a merge conflict. Do not independently regenerate a held-out split for each model. Add a small fixture and a regression test when fixing an ID join, citation orientation, section rule, or temporal-filter bug.

## 9. What remains after this handoff

| Work item | Owner |
|---|---|
| Supply judgment PDFs and review extraction failures | Yashwardhan with the team |
| Spot-check metadata, graph types, and silver section labels | Yashwardhan with the team |
| Train SVM/CRF/InLegalBERT and build retrieval indexes | Jhon |
| Build grounded generation, Graph-RAG, and interface | Anushka |
| Review/freeze benchmark and implement scoring harness | Tarandeep |
| Review privacy, bias, hallucination, and support claims | Whole team |
