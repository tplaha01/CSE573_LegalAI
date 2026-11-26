from typing import List, Optional

from app.schemas import Passage
from app.services.retriever import Retriever


MOCK_PASSAGES = [
    Passage(
        chunk_id="mock_case_001_p3_c1",
        doc_id="mock_case_001",
        case_name="Sharma v. State",
        year=2012,
        page=3,
        section="REASONING",
        text=(
            "The Court considered whether documentary evidence "
            "was sufficient to establish the claimed interest in the property."
        ),
        score=0.92,
    ),
    Passage(
        chunk_id="mock_case_002_p8_c2",
        doc_id="mock_case_002",
        case_name="Kumar v. Singh",
        year=2015,
        page=8,
        section="FACTS",
        text=(
            "The claimant relied upon documentary records and witness "
            "testimony in support of the asserted property interest."
        ),
        score=0.86,
    ),
    Passage(
        chunk_id="mock_case_003_p12_c1",
        doc_id="mock_case_003",
        case_name="Patel v. Rao",
        year=2017,
        page=12,
        section="RATIO",
        text=(
            "The Court emphasized that conclusions concerning title "
            "must be supported by evidence established in the record."
        ),
        score=0.81,
    ),
]


class MockRetriever(Retriever):

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        as_of_year: Optional[int] = None,
        exclude_doc_id: Optional[str] = None,
    ) -> List[Passage]:

        results = MOCK_PASSAGES

        if exclude_doc_id:
            results = [
                passage
                for passage in results
                if passage.doc_id != exclude_doc_id
            ]

        if as_of_year is not None:
            results = [
                passage
                for passage in results
                if passage.year is not None
                and passage.year < as_of_year
            ]

        return results[:top_k]