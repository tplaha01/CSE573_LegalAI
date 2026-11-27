import unittest

from app.schemas import LegalQuery
from app.services.mock_retriever import MockRetriever


class TestMockRetriever(unittest.TestCase):

    def test_contract_retrieval(self):

        retriever = MockRetriever()

        query = LegalQuery(
            full_query=(
                "Whether an estate broker had authority "
                "to conclude a contract of sale."
            )
        )

        results = retriever.retrieve(
            query=query,
            top_k=3,
        )

        self.assertGreater(
            len(results),
            0,
        )

        self.assertEqual(
            results[0].doc_id,
            "mock_contract_case",
        )


if __name__ == "__main__":
    unittest.main()