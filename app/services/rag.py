from typing import Optional

from app.schemas import Citation, QueryResponse
from app.services.retriever import Retriever


class RAGService:

    def __init__(self, retriever: Retriever):
        self.retriever = retriever

    def answer(
        self,
        query: str,
        top_k: int = 5,
        as_of_year: Optional[int] = None,
        query_doc_id: Optional[str] = None,
    ) -> QueryResponse:

        passages = self.retriever.retrieve(
            query=query,
            top_k=top_k,
            as_of_year=as_of_year,
            exclude_doc_id=query_doc_id,
        )

        if not passages:
            return QueryResponse(
                query=query,
                answer=(
                    "No eligible supporting passages were retrieved "
                    "for this query."
                ),
                passages=[],
                citations=[],
                mode="mock-rag",
            )

        citations = []

        for index, passage in enumerate(passages, start=1):
            citations.append(
                Citation(
                    citation_id=index,
                    chunk_id=passage.chunk_id,
                    doc_id=passage.doc_id,
                    case_name=passage.case_name,
                    page=passage.page,
                    supporting_text=passage.text,
                )
            )

        answer_parts = [
            "This is a mock grounded response used to test the "
            "Agentic Law infrastructure."
        ]

        for citation in citations:
            answer_parts.append(
                f"[{citation.citation_id}] "
                f"{citation.case_name}: "
                f"{citation.supporting_text}"
            )

        return QueryResponse(
            query=query,
            answer="\n\n".join(answer_parts),
            passages=passages,
            citations=citations,
            mode="mock-rag",
        )