import unittest

from app.schemas import CaseAnalysisRequest
from app.services.query_builder import LegalQueryBuilder


class TestLegalQueryBuilder(unittest.TestCase):

    def test_builds_legal_query(self):

        request = CaseAnalysisRequest(
            facts=(
                "An estate broker introduced a purchaser."
            ),
            legal_issues=(
                "Whether the broker had authority "
                "to conclude the sale."
            ),
            petitioner_arguments=(
                "The broker says the authority was sufficient."
            ),
            respondent_arguments=(
                "The owner says the broker could only "
                "introduce a purchaser."
            ),
        )

        builder = LegalQueryBuilder()

        query = builder.build(request)

        self.assertIn(
            "broker",
            query.full_query.lower(),
        )

        self.assertIn(
            "authority",
            query.full_query.lower(),
        )


if __name__ == "__main__":
    unittest.main()