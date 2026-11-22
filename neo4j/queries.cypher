// :param seed_ids => ['1780900'];
// :param query_year => 2018;
// Outgoing, one hop. Filter BOTH seeds and targets to avoid future-case leakage.
MATCH (seed:Case)-[r:CITES]->(prior:Case)
WHERE seed.doc_id IN $seed_ids
  AND seed.year < $query_year
  AND prior.year < $query_year
  AND prior.has_text = true
RETURN DISTINCT prior.doc_id, prior.case_name, prior.year,
       prior.metadata_verified, r.reference_sources_json
ORDER BY prior.year DESC, prior.doc_id;

// Incoming, one hop; future citing cases must not enter historical context.
MATCH (citing:Case)-[r:CITES]->(seed:Case)
WHERE seed.doc_id IN $seed_ids
  AND seed.year < $query_year
  AND citing.year < $query_year
  AND citing.has_text = true
RETURN DISTINCT citing.doc_id, citing.case_name, citing.year;

// Report graph coverage rather than assuming every reference is a judgment.
MATCH (n:LegalDocument)
RETURN n.node_type AS type, n.metadata_verified AS verified, count(*) AS nodes
ORDER BY type, verified;
