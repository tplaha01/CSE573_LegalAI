from typing import List

from app.schemas import Citation, Passage


def validate_citations(
    citations: List[Citation],
    passages: List[Passage],
) -> bool:

    allowed_chunk_ids = {
        passage.chunk_id
        for passage in passages
    }

    for citation in citations:
        if citation.chunk_id not in allowed_chunk_ids:
            return False

    return True