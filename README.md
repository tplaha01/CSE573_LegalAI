<<<<<<< HEAD
# Agentic Law: Yashwardhan's data pipeline and knowledge graph

This package implements **Yashwardhan Ramchaware's assigned workstream** in the G12-P15 proposal: prepare the legal dataset and deliver a citation graph that the modeling, RAG, and evaluation workstreams can use.

It includes Python source, the supplied metadata inputs, generated metadata/graph outputs, tests, and teammate handoff instructions. It does not train the other workstreams' models.

## What is ready

- Join the land-dispute workbook and both citation JSON schemas using Indian Kanoon document IDs.
- Normalize metadata, retain source provenance, merge duplicate sources, and record conflicts.
- Orient every citation as **citing document → cited document**, including reversed `cited_by` records.
- Export a directed graph for offline use and Neo4j, with separate case, statute, section, and unresolved reference types.
- Ingest local judgment PDFs when supplied; clean text, preserve page provenance, emit chunks and silver section labels, and report extraction problems.
- Prepare temporal split and citation benchmark artifacts without treating missing judgment text as completed benchmark data.

**The attachments do not contain judgment PDFs.** The project proposal PDF is documentation, not a judgment. The included metadata/graph run therefore has no real judgment pages, text chunks, or eligible full-text test queries. The PDF extraction path is implemented and tested; run it on the judgment corpus before model training.

## Quick start

Use Python 3.11 or later. Extract the archive, then open a terminal in this folder.

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_pipeline.py --raw-dir data/raw --out-dir data/processed
python -m unittest discover -s tests -v
```

For all synthetic-PDF tests, install `requirements-dev.txt` instead of
`requirements.txt` (adds ReportLab). The verified build passed **21 tests**.
`notebooks/01_data_pipeline.ipynb` provides a guided Jupyter/Colab entry point;
`examples/consume_outputs.py` is a runnable teammate consumer.
Run `python validate_outputs.py` to check the included snapshot's hashes,
graph endpoints, and every citation observation against its original direction.

Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_pipeline.py --raw-dir data/raw --out-dir data/processed
python -m unittest discover -s tests -v
```

If PowerShell blocks activation, use `.venv\Scripts\python.exe` instead of `python` in the last three commands. Metadata processing and offline graph traversal do not require Docker, Neo4j, an API key, or an LLM.

## Add the judgment PDFs

Obtain the judgment corpus referenced in the proposal and keep it outside the code repository. Set the PDF root to the directory containing year folders:

```text
supreme_court_judgments/
  1950/
    Abdulla_Ahmed_vs_Animendra_Kissen_Mitter_on_14_March_1950_1.PDF
  ...
```

Then run:

```bash
python run_pipeline.py --raw-dir data/raw --out-dir data/processed --pdf-root /absolute/path/to/supreme_court_judgments
```

Use a quoted Windows path such as `--pdf-root "D:\datasets\supreme_court_judgments"` on Windows. The workbook's old `/content/drive/MyDrive/...` paths are retained as provenance; they are not assumed to exist on your computer. Matching uses portable paths and explicit document IDs. If files use another naming convention, provide `--pdf-manifest mapping.json`; see [the handoff](docs/HANDOFF.md).

Do not point `--pdf-root` at the folder containing the proposal. Scanned/image-only PDFs require OCR before their text can be used. Missing files and empty extraction are reported, not silently replaced with invented text.

The metadata inputs identify 10,205 known cases, rather than all 26,688 PDFs
described in the proposal. To ingest text-only judgments absent from these
subsets, supply their authoritative Indian Kanoon IDs in `--pdf-manifest`.
The pipeline adds those mapped cases with `has_citation_metadata=false`;
it never guesses a document ID from an unrelated filename.

## Main outputs

All paths below are relative to the selected output directory, normally `data/processed`.

| File | Use |
|---|---|
| `cases.jsonl` | One normalized case per document ID; join and coverage metadata |
| `references.jsonl` | Deduplicated, correctly oriented citation edges and provenance |
| `pages.jsonl` | Cleaned judgment pages and page-level source information |
| `chunks.jsonl` | Stable retrieval units with document/page/section provenance |
| `sentences.jsonl` | Sentence records and silver rhetorical-role labels |
| `quality_report.json` | Input counts, joins, missing text, warnings, and run status |
| `run_manifest.json`, `cases.csv` | Artifact hashes for the shared snapshot and a flat metadata view |
| `metadata_issues.jsonl` | Conflicts and rejected metadata requiring review |
| `split_manifest.json` | Temporal partition, benchmark eligibility, and snapshot information |
| `benchmark_queries.jsonl`, `qrels.jsonl` | Available benchmark queries and citation silver relevance labels |
| `graph/graph_nodes.csv`, `graph/graph_edges.csv` | Neo4j-compatible graph exports |
| `graph/graph.json` | Offline graph representation |

JSONL means one JSON object per line. Preserve document IDs as strings in every downstream file. Empty text/benchmark files in the supplied metadata-only run are expected.

## Observed input counts

| Measure | Count |
|---|---:|
| Citation JSON rows | 7,493 |
| Unique citation source IDs | 7,101 |
| Duplicate source rows merged | 392 |
| Land-dispute IDs | 6,954 |
| Land/citation-source intersection | 3,850 |
| Intersection with year 2018 or later | 558 |
| Unified metadata case IDs | 10,205 |
| Unique citation edges, including reversed `cited_by` | 237,250 |
| Graph document/resource IDs | 128,436 |

The proposal's 7,497 citation cases is a stated dataset description; the attached files actually contain 7,493 rows. The 558 cases are **metadata candidates**, not a completed full-text test set.

The graph includes 10,205 corpus records and 118,231 external resources.
External `Case` types are title-based hints with `metadata_verified=false`;
they must not be counted as verified Supreme Court judgments.

## Work with the team

| Owner | Starts with |
|---|---|
| Yashwardhan | This data pipeline, extraction quality, graph, and data contracts |
| Jhon Reymond | `sentences.jsonl` for classification and `chunks.jsonl` for retrieval |
| Anushka | `chunks.jsonl`, normalized cases, and the graph for RAG/Graph-RAG |
| Tarandeep | Frozen split artifacts, citation qrels, provenance, and the quality report |

Read [HANDOFF.md](docs/HANDOFF.md) before integrating outputs. It explains joins, leakage controls, graph use, PDF mapping, and a shared Git workflow. [IMPLEMENTATION_REPORT.md](docs/IMPLEMENTATION_REPORT.md) provides a report-ready account of this work, including the limits of the supplied run.

## Boundaries that matter

- A citation means “cites”; it does not establish that a case applies, supports a claim, overrules another case, or is binding authority.
- External references may be statutes, sections, judgments from other courts, or unresolved resources. They are not all Supreme Court cases.
- Header-derived section labels are silver labels, not manually verified ground truth. `UNKNOWN` is a valid outcome.
- Direct contact redaction is a limited heuristic, not complete anonymization. Review extracted text before sharing it.
- Temporal evaluation must exclude the query judgment and future information. A current graph snapshot cannot be used unfiltered for historical benchmark retrieval.

No model accuracy, retrieval improvement, or legal-answer quality is claimed by this data implementation.
=======
# CSE573_LegalAI
>>>>>>> 9870d8b074446d9155d43aa801f1fa460d10fb2b
