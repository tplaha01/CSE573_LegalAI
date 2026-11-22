# Optional Neo4j visualization

The pipeline and offline `Graph` API work without Docker or Neo4j. The files in
this directory add an optional Neo4j Community 5.26 graph view.

From the project root, after producing `data/processed/graph/graph_nodes.csv` and
`data/processed/graph/graph_edges.csv`:

```bash
export NEO4J_PASSWORD='choose-a-project-password'
docker compose -f neo4j/docker-compose.yml up -d
docker compose -f neo4j/docker-compose.yml exec -T neo4j \
  cypher-shell -u neo4j -p "$NEO4J_PASSWORD" < neo4j/import.cypher
```

Wait until Neo4j reports it is ready before running the import command. Open
`http://localhost:7474`, log in with `neo4j` and your chosen password, and run:

```cypher
MATCH (a:Case)-[r:CITES]->(b:LegalDocument)
WHERE a.is_land_dispute = true
RETURN a, r, b LIMIT 100;
```

The compose file binds ports to your local machine and mounts the processed
graph CSV directory (`data/processed/graph`) read-only. It stores the graph in a named Docker volume. Set
your password locally; no credentials are included in the project.

The same snapshot can be imported repeatedly. Importing a changed snapshot
does not delete removed nodes, relationships, or old labels. Use a fresh
project-specific database/volume when switching to a new snapshot; do not
run destructive cleanup commands against a shared database.

All nodes have `LegalDocument`; additional labels are `Case`, `Statute`,
`Section`, or `UnknownReference`. Only corpus membership establishes a
verified dataset judgment. Title-based external `Case` labels are silver
hints, distinguished by `metadata_verified=false` and `type_basis`.
Only the reported `CITES` relation is imported. The source may refer to a
statute or provision; this does not imply legal reliance, treatment, or
`APPLIES`. Provenance arrays are stored as JSON strings so no APOC plugin is
required. The offline JSON graph preserves the same information. Exact raw
record indices remain in `data/processed/references.jsonl` under
`source_records`; graph edges retain their source filenames and originating
metadata fields in `source_files_json` and `reference_sources_json`.

`queries.cypher` includes historical one-hop examples. Supply `seed_ids`
and `query_year` as parameters in Neo4j Browser. Both endpoints must precede
the query year. Unknown years fail the comparison. A date-accurate benchmark
should filter both endpoints by known `decision_date < $query_date` instead.

Validation: the CSV export, graph construction, deduplication, direction,
type handling, and historical filters have offline unit tests. Neo4j import
syntax was checked against the official Neo4j 5 documentation; a live server
import was not executed in this workspace.

Official references:

- [Neo4j 5 LOAD CSV](https://neo4j.com/docs/cypher-manual/5/clauses/load-csv/)
- [Neo4j 5 constraint syntax](https://neo4j.com/docs/cypher-manual/5/constraints/syntax/)
