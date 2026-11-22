# Implementation: data pipeline and citation knowledge graph

**Project:** G12-P15, Legal AI - Agentic Law  
**Workstream owner:** Yashwardhan Ramchaware  
**Scope:** Data preparation and knowledge graph, as assigned in Section 8 of the supplied proposal.

## Objective

The implementation converts the supplied land-dispute spreadsheet and citation JSON files into a normalized, traceable dataset and a directed citation graph. It also provides judgment-PDF ingestion so that the modeling and RAG workstreams can consume page-level text, retrieval chunks, and silver section labels once the full judgment corpus is available.

The data pipeline is separate from model training and legal-answer generation. Its outputs establish stable document identity, source provenance, coverage information, and graph relationships shared by the other team members.

## Inputs inspected

The supplied inputs comprise ten citation JSON files, the land-dispute workbook, a dataset README, and the project proposal PDF. The judgment PDFs described in the proposal are not included in the attachments.

The audit found two citation schemas. Most files provide a case title, year, URL, and precedent list. One file instead supplies explicit source IDs and both `precedents` and `cited_by` lists, with many placeholder source titles and no explicit source year. The spreadsheet contains filenames, years, original Colab paths, URLs, document IDs, a document classification, and a land-dispute flag.

| Observed measure | Count |
|---|---:|
| Citation source rows | 7,493 |
| Unique citation source IDs | 7,101 |
| Repeated citation source rows | 392 |
| Land-dispute rows and unique IDs | 6,954 |
| Land/citation-source overlap | 3,850 |
| Overlap with year 2018 or later | 558 |
| Unified known metadata case IDs | 10,205 |
| Raw precedent observations | 144,353 |
| Raw cited-by observations | 94,641 |
| Unique directed edges after union | 237,250 |
| All graph resource IDs | 128,436 |

These counts describe the attached files. The proposal's 7,497 citation-case figure does not match the observed 7,493 rows. The 558 post-cutoff overlapping records are metadata candidates only; they are not a completed text-based benchmark.

## Data normalization and integration

Indian Kanoon document IDs serve as the shared join key and remain strings. IDs are taken from explicit metadata or parsed from source URLs, then checked for consistency. URLs are normalized to a canonical HTTPS format. The land workbook enriches matching citation sources with known filenames, years, and portable PDF paths.

Repeated citation sources are merged by taking the union of their directed references. Keeping only the first or last record would lose citation information because the duplicate records contain different reference sets. The implementation preserves source-file provenance and observation counts on the merged relations.

Missing and conflicting metadata are recorded for review. Dates parsed from filenames or citation titles retain silver provenance. Missing dates are not guessed from document IDs, citation order, or a statute's year. Disputed temporal metadata is excluded from historical eligibility.

The workbook's original absolute Colab paths are preserved as source metadata. A portable `<year>/<filename>` suffix and an explicit PDF manifest allow the same pipeline to run on other teammates' machines.

## Judgment text pipeline

The PDF ingestion module uses `pdfplumber` for text extraction. Its processing preserves page provenance, conservatively removes repeated headers/footers and standalone page numbers, normalizes text, and applies limited direct-contact redaction. It reports extraction problems and image-only pages instead of manufacturing text.

Chunks remain within page and section boundaries. Each chunk carries a stable identifier and the document/page/source information needed to attach provenance to retrieval results. Character offsets refer to the final cleaned page text. Sentence records support the later classification workstream.

Explicit section headings can supply silver rhetorical-role labels. Text without a defensible section heading remains `UNKNOWN`. A generic opening “JUDGMENT” heading is not sufficient to label an entire judgment as its final decision. These labels require manual spot-checking before supervised use.

The limited redaction rules do not constitute complete anonymization. Names, addresses, and other sensitive material may remain, and extracted text requires review before broad sharing. OCR and comprehensive entity-based de-identification are outside the completed extraction path.

## Citation graph construction

Every edge is oriented from the citing document to the cited resource. Standard precedent entries directly create this direction. A `cited_by` entry is reversed: when B appears in A's cited-by list, the relationship is B → A.

The graph distinguishes known dataset cases from external references. Reference lists contain statutes, sections, articles, rules, and unresolved resources as well as judgments. Therefore, treating every citation target as a case would misrepresent the data. External resource typing uses conservative metadata rules and retains uncertainty; outside courts, dates, and text availability are not assumed.

The graph exports CSVs suitable for Neo4j and an offline JSON representation. Offline expansion supports bounded traversal and historical eligibility filters. The same resource ID can join a graph node to a normalized case and, when present, to its evidence passages.

The implemented relation is `CITES`. The source data does not establish `APPLIES`, `HAS_RATIO`, `HAS_ISSUE`, `OVERRULES`, binding authority, or passage-level claim support. Those relationships require a later validated extraction process.

## Temporal preparation and evaluation handoff

The proposal's default temporal cutoff is 2018: earlier cases support development and later cases form the test pool. Executable citation benchmarks require both source citation metadata and judgment text. Relevant retrieval targets must be available judgments decided before the query judgment.

When reliable dates are available, temporal comparisons are strict. When only years are available, same-year candidates are excluded because their order is uncertain. Unknown or disputed dates cannot establish historical eligibility.

The split artifacts distinguish metadata candidates from text-eligible benchmark records. A frozen snapshot must be retained before tuning models; changing the inputs and explicitly refreshing the split creates a new benchmark version. The evaluation workstream must remove query citations and keep query outcomes and known query citation edges out of retrieval context.

Historical citation lists are partial silver relevance labels. They do not establish an exhaustive list of relevant precedent. A manually reviewed gold subset remains necessary for retrieval validation, rhetorical-role verification, and generated claim support.

## Delivered interfaces

| Output | Downstream purpose |
|---|---|
| Normalized cases and references | Shared document identity, joins, and citation provenance |
| Page, chunk, and sentence JSONL | Classification, retrieval, and evidence grounding after PDFs are supplied |
| Quality report and metadata issues | Coverage review and reproducible data corrections |
| Split manifest and benchmark artifacts | Consistent evaluation snapshot and temporal eligibility |
| Graph CSV/JSON and traversal code | Offline exploration and Graph-RAG/Neo4j integration |
| README, handoff guide, and tests | Reproduction and teammate integration |

Jhon can build models and retrieval indexes from the text outputs, Anushka can combine retrieved passages with graph expansion, and Tarandeep can use the split/provenance artifacts in the evaluation harness. None of these components needs to reimplement the source-file joins.

## Validation and current limits

Validation includes input audits, deterministic output checks, graph direction and resource-type checks, temporal-filter checks, and text-cleaning/chunk provenance tests. The package's test command is:

```bash
python -m unittest discover -s tests -v
```

The metadata and citation graph can be run on all supplied inputs. The current supplied run has no judgment pages, chunks, or text-eligible test queries because the judgment corpus was not attached. It must not be described as completed full-corpus text extraction or as a trained/evaluated legal chatbot.

The completed validation run passed **21 unit and integration tests**. The
full attached metadata produced 128,436 graph nodes and 237,250 directed edges,
including 23,117 edges between known corpus records and no self-references.
There are 295 known cases whose decision year and source title remain
unavailable. Graph resource types outside the 10,205 corpus records remain
unverified metadata hints. Neo4j import files are provided; a live Neo4j server
was not available for integration testing.

The implementation provides the data and graph foundation assigned to Yashwardhan. Full-corpus extraction, manual gold review, model training, RAG integration, and final evaluation require the remaining inputs and the corresponding team workstreams. No model accuracy, retrieval gain, or generated-answer correctness is claimed here.
