from typing import List

from app.schemas import LegalQuery, Passage
from app.services.retriever import Retriever


MOCK_PASSAGES = [

    Passage(
        chunk_id="contract_authority_001",
        doc_id="mock_contract_case",
        case_name="Mock Contract Authority Case",
        page=6,
        section="COURT_REASONING",
        text=(
            "The scope of an agent's authority depends upon "
            "the language of the authorization and the "
            "surrounding circumstances."
        ),
    ),

    Passage(
        chunk_id="property_evidence_001",
        doc_id="mock_property_case",
        case_name="Mock Property Evidence Case",
        page=12,
        section="COURT_REASONING",
        text=(
            "A claim concerning title to property must be "
            "supported by evidence sufficient to establish "
            "the asserted legal interest."
        ),
    ),

    Passage(
        chunk_id="speech_001",
        doc_id="mock_constitution_case",
        case_name="Mock Freedom of Speech Case",
        page=4,
        section="COURT_REASONING",
        text=(
            "Restrictions imposed upon publication engage "
            "the constitutional protection of freedom of "
            "speech and expression."
        ),
    ),
]


class MockRetriever(Retriever):

    def retrieve(
        self,
        query: LegalQuery,
        top_k: int = 5,
    ) -> List[Passage]:

        query_text = query.full_query.lower()

        scored_results = []

        for passage in MOCK_PASSAGES:

            score = 0.0
            reasons = []

            passage_text = passage.text.lower()

            # Contract / agency logic
            contract_terms = [
                "contract",
                "agent",
                "broker",
                "authority",
                "sale",
            ]

            contract_matches = sum(
                term in query_text
                and term in passage_text
                for term in contract_terms
            )

            if contract_matches:
                score += contract_matches * 0.2
                reasons.append(
                    "Similar contract/agency legal issue"
                )

            # Property / evidence logic
            property_terms = [
                "property",
                "ownership",
                "title",
                "evidence",
            ]

            property_matches = sum(
                term in query_text
                and term in passage_text
                for term in property_terms
            )

            if property_matches:
                score += property_matches * 0.2
                reasons.append(
                    "Similar property/evidence issue"
                )

            # Constitutional / speech logic
            speech_terms = [
                "speech",
                "expression",
                "publication",
                "constitution",
            ]

            speech_matches = sum(
                term in query_text
                and term in passage_text
                for term in speech_terms
            )

            if speech_matches:
                score += speech_matches * 0.2
                reasons.append(
                    "Similar constitutional issue"
                )

            if score > 0:

                result = passage.model_copy(
                    update={
                        "combined_score": round(score, 3),
                        "relevance_reasons": reasons,
                    }
                )

                scored_results.append(result)

        scored_results.sort(
            key=lambda item: item.combined_score or 0,
            reverse=True,
        )

        return scored_results[:top_k]