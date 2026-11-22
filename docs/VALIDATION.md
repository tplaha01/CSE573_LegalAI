# Validation record

Validation date: November 6, 2026. Runtime: Python 3.12, pandas 2.2.3,
openpyxl 3.1.5, pdfplumber 0.11.9. Synthetic PDF tests use ReportLab.

| Check | Result |
|---|---|
| Unit and integration tests | 21 passed; none skipped in this workspace |
| Full attached metadata pipeline | Completed successfully |
| Source citation rows / distinct source IDs | 7,493 / 7,101 |
| Repeated source rows merged by union | 392 |
| Known metadata case IDs | 10,205 |
| Graph nodes / directed edges | 128,436 / 237,250 |
| Known-corpus-to-known-corpus edges | 23,117 |
| Graph self references | 0 |
| Normalization issues on supplied inputs | 0 |
| Unknown case years | 295 |
| PDF matches / usable judgment texts | 0 / 0; judgment PDFs not supplied |
| Text-eligible test cases / benchmark queries | 0 / 0; pending PDFs |
| Repeated complete runs | Identical run manifest and artifact hashes |
| Teammate consumer example | Loaded shared snapshot and traversed prior-case neighbors |
| Notebook | All Python code cells compile |
| Live Neo4j import | Not run; Docker/Neo4j server unavailable |

Commands:

```bash
python -m unittest discover -s tests -v
python run_pipeline.py
python validate_outputs.py
python examples/consume_outputs.py
```

The standalone validator checked 14 artifact hashes, unique case IDs, unique
reference edges, all graph endpoints, complete graph/reference agreement,
and raw-record provenance/direction for 238,994 citation observations.

Tests include both source schemas, duplicate merging, reversal of `cited_by`,
external reference types, future/unknown case exclusion, query node exclusion,
historical graph traversal, frozen query identity, overlap deduplication,
ambiguous PDF mapping, exact page-local offsets, limited contact redaction,
real synthetic-PDF extraction, OCR-only scraps, and PDF-date enrichment.

These are data engineering checks. They do not measure legal accuracy,
retrieval effectiveness, classification quality, or generated-claim support.
