from app.schemas import (
    CaseAnalysisRequest,
    CaseAnalysisResponse,
    Citation,
    PrecedentResult,
)

from app.services.query_builder import LegalQueryBuilder
from app.services.retriever import Retriever


class RAGService:

    def __init__(
        self,
        retriever: Retriever,
    ):
        self.retriever = retriever
        self.query_builder = LegalQueryBuilder()

    def analyze(
        self,
        request: CaseAnalysisRequest,
    ) -> CaseAnalysisResponse:

        legal_query = self.query_builder.build(
            request
        )

        passages = self.retriever.retrieve(
            query=legal_query,
            top_k=request.top_k,
        )

        if not passages:

            return CaseAnalysisResponse(
                analysis=(
                    "No sufficiently relevant precedent "
                    "was retrieved for the supplied case "
                    "material."
                ),
                precedents=[],
                citations=[],
                retrieval_mode="mock-logic-aware",
            )

        citations = []

        precedents = []

        for index, passage in enumerate(
            passages,
            start=1,
        ):

            citations.append(
                Citation(
                    citation_id=index,
                    chunk_id=passage.chunk_id,
                    doc_id=passage.doc_id,
                    case_name=passage.case_name,
                    page=passage.page,
                    section=passage.section,
                    supporting_text=passage.text,
                )
            )

            precedents.append(
                PrecedentResult(
                    doc_id=passage.doc_id,
                    case_name=passage.case_name,
                    score=passage.combined_score,
                    reasons=passage.relevance_reasons,
                    passages=[passage],
                )
            )

        analysis_lines = [
            (
                "Prototype analysis based only on "
                "retrieved supporting passages."
            ),
            "",
        ]

        for citation, precedent in zip(
            citations,
            precedents,
        ):

            reasons = ", ".join(
                precedent.reasons
            )

            analysis_lines.append(
                f"[{citation.citation_id}] "
                f"{citation.case_name}"
            )

            if reasons:
                analysis_lines.append(
                    f"Why relevant: {reasons}"
                )

            analysis_lines.append(
                citation.supporting_text
            )

            analysis_lines.append("")

        return CaseAnalysisResponse(
            analysis="\n".join(analysis_lines),
            precedents=precedents,
            citations=citations,
            retrieval_mode="mock-logic-aware",
        )