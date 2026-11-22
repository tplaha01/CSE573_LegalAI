# Legal AI: Evidence-Grounded Precedent Research

Course project for **CSE 573: Semantic Web Mining**. The project builds and evaluates a prototype that helps explore Indian Supreme Court land-dispute judgments by retrieving earlier, potentially relevant precedents and producing analysis grounded in passages from those judgments.

The system is a research prototype, not legal advice. Its purpose is to study retrieval, citation grounding, and the limits of automated legal analysis.

## Final project scope

The project uses the **6,954 land-dispute cases** identified by the second citation file shared in the course Canvas group discussion as its target case set. The citation file supplies case relationships and metadata; usable full-text judgments must be matched and verified separately. The target count is not the same as the number of cases available for text-based experiments.

The planned end-to-end workflow is:

1. Validate case identifiers, citation records, dates, and available judgment PDFs.
2. Extract and normalize judgment text while retaining case, page, and passage provenance.
3. Build a citation knowledge graph and lexical and semantic retrieval indexes.
4. Retrieve only precedents eligible as of the query judgment's date.
5. Generate structured legal analysis grounded in retrieved passages, with citations attached to claims.
6. Evaluate retrieval, citation validity and support, and legal-analysis quality using automatic checks and a small human-reviewed gold subset.

Indian Kanoon API data is an optional source for specific missing metadata. Any API-derived fields must retain source provenance. API access does not replace validation of the citation file or judgment-text matches.

## Current implementation

The repository includes a data-normalization and citation-graph pipeline, PDF text extraction and chunking, temporal benchmark preparation, validation utilities, and prototype model scripts:

- `src/agentic_law_data/` — metadata normalization, text processing, graph construction, and benchmark preparation.
- `run_pipeline.py` — build processed case, text, graph, and benchmark artifacts.
- `validate_outputs.py` — validate a generated data snapshot and citation graph outputs.
- `models/classical_model.py` — TF-IDF + Linear SVM and CRF rhetorical-role classification prototypes.
- `models/deep_learning.py` — InLegalBERT chunk embeddings and FAISS semantic index prototype.
- `models/bypass_classical_model.py` — plumbing-only experiment with synthetic labels; its metrics are not model-performance results and must not be reported as such.
- `docs/` and `HANDOFF.md` — implementation notes, validation details, and integration guidance.

These scripts are starting points for the final system, not proof that the end-to-end system or its evaluation is complete. In particular, classification is meaningful only if the sentence labels contain sufficient reviewed examples across multiple classes. The `UNKNOWN` label must be retained rather than replaced with invented targets.

## Data and evaluation principles

- Use the Canvas second citation file as the reference source for the 6,954-case land-dispute scope.
- Preserve case IDs as strings and retain provenance when records are merged or metadata is supplemented.
- Match PDFs to cases by authoritative case ID or an explicit mapping manifest; manually spot-check matches.
- Report counts for cases with citation metadata, verified judgment text, and both. Never imply that all 6,954 cases have usable text without measuring it.
- Split data by case, not by sentence or chunk, to prevent leakage between training and evaluation.
- For historical queries, exclude the query judgment and any later cases from retrieval candidates.
- Treat citation links as **partial silver relevance labels**: a cited case may be relevant, but uncited cases are not automatically irrelevant.
- Validate a small sample with human reviewers. Report citation validity, citation support, and citation coverage separately.
- Score legal analysis on the planned dimensions: relevance, correctness, evidence grounding, reasoning, argument quality, and counterargument quality. An LLM judge is supplementary and must be compared with human ratings.
- Report component metrics separately; do not collapse them into one headline score.

## Setup

Use Python 3.11 or later. From the repository root:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks environment activation, use `.venv\Scripts\python.exe` in place of `python`.

## Run the data pipeline

Place the approved citation and metadata inputs under `data/raw/`. Keep large or restricted PDF corpora outside Git. Point `--pdf-root` at the directory containing judgment PDFs; use `--pdf-manifest` when filenames cannot be matched through the normal mapping.

```powershell
python run_pipeline.py --raw-dir data/raw --out-dir data/processed --pdf-root "D:\datasets\supreme_court_judgments"
python validate_outputs.py
```

The PDF root is optional for metadata and graph processing, but retrieval and text-based answer evaluation require usable judgment text. Review `data/processed/quality_report.json`, `split_manifest.json`, and `benchmark_queries.jsonl` before training or reporting results. Confirm that the pipeline is consuming the **second Canvas citation file** and that the selected snapshot corresponds to the intended 6,954-case scope.

## Model prototypes

Run model scripts from the repository root after checking their input paths and the generated label/split reports. The classical script trains a TF-IDF/SVM baseline and a CRF; the deep-learning script creates an InLegalBERT/FAISS index. Before using either in the final comparison:

1. Verify that its paths point to the current `data/processed/` snapshot and split manifest.
2. Confirm usable text and, for classification, valid multi-class labels.
3. Keep every case wholly within one split and fit learned preprocessing only on training data.
4. Save configurations, model versions, outputs, and evaluation results with the data/split version.

The synthetic-label bypass script is for checking that code paths execute. Its predictions and scores do not measure classification quality.

## Planned final evaluation

| Component | Evaluation |
|---|---|
| Precedent retrieval | Recall@K, MRR, and nDCG@K against citation silver labels and a reviewed gold subset |
| Optional rhetorical-role classification | Macro-F1, precision, recall, and confusion matrix, only if labels are usable |
| Citation grounding | Citation validity, passage support, citation coverage, and unsupported-claim rate |
| Legal analysis | Human ratings on the six rubric dimensions; report agreement for a double-scored subset |
| End-to-end system | Reproducible held-out examples, component scorecard, and qualitative error analysis |

Only report results reproduced from the frozen evaluation split. Document the actual text coverage, annotation limits, temporal-filtering policy, and failure cases in the final report.

## Repository map

```text
data/                 Raw inputs and processed snapshots
docs/                 Project, implementation, and validation documentation
models/               Classification and semantic-index prototypes
neo4j/                Graph import and query resources
src/agentic_law_data/  Data, text, graph, and benchmark pipeline
tests/                Pipeline and component tests
experiments/           Experiment outputs and analysis
```

See `PROJECT_PLAN.md` in the parent project folder for team sequencing and deliverables, and `HANDOFF.md` for data contracts and integration notes.
