// Run after data/processed/graph/graph_nodes.csv and graph_edges.csv exist.
// A repeated import of the SAME snapshot is idempotent. Importing a changed
// snapshot does not delete stale rows: use a new project database/volume for it.
CREATE CONSTRAINT legal_document_id IF NOT EXISTS
FOR (d:LegalDocument) REQUIRE d.doc_id IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///graph_nodes.csv' AS row
MERGE (d:LegalDocument {doc_id: row.doc_id})
SET d.node_type = row.node_type,
    d.case_name = row.case_name,
    d.url = row.url,
    d.year = toInteger(row.year),
    d.decision_date = CASE WHEN row.decision_date = '' THEN null ELSE date(row.decision_date) END,
    d.is_corpus = toBoolean(row.is_corpus),
    d.metadata_verified = toBoolean(row.metadata_verified),
    d.type_basis = row.type_basis,
    d.is_land_dispute = toBoolean(row.is_land_dispute),
    d.has_citation_metadata = toBoolean(row.has_citation_metadata),
    d.has_text = toBoolean(row.has_text),
    d.aliases_json = row.aliases_json,
    d.source_files_json = row.source_files_json
FOREACH (_ IN CASE WHEN row.node_type = 'Case' THEN [1] ELSE [] END | SET d:Case)
FOREACH (_ IN CASE WHEN row.node_type = 'Statute' THEN [1] ELSE [] END | SET d:Statute)
FOREACH (_ IN CASE WHEN row.node_type = 'Section' THEN [1] ELSE [] END | SET d:Section)
FOREACH (_ IN CASE WHEN row.node_type = 'UnknownReference' THEN [1] ELSE [] END | SET d:UnknownReference);

LOAD CSV WITH HEADERS FROM 'file:///graph_edges.csv' AS row
MATCH (source:LegalDocument {doc_id: row.source_id})
MATCH (target:LegalDocument {doc_id: row.target_id})
MERGE (source)-[r:CITES]->(target)
SET r.occurrences = toInteger(row.occurrences),
    r.is_self_reference = toBoolean(row.is_self_reference),
    r.source_files_json = row.source_files_json,
    r.reference_sources_json = row.reference_sources_json;
