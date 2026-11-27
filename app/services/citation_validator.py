from typing import List

from app.schemas import Citation, PrecedentResult


def validate_citations(
    citations: List[Citation],
    precedents: List[PrecedentResult],
) -> bool:

    allowed_chunk_ids = set()

    for precedent in precedents:

        for passage in precedent.passages:

            allowed_chunk_ids.add(
                passage.chunk_id
            )

    for citation in citations:

        if citation.chunk_id not in allowed_chunk_ids:

            return False

    return True