import unittest

from app.services.mock_retriever import MockRetriever


class TestMockRetriever(unittest.TestCase):

    def test_returns_passages(self):
        retriever = MockRetriever()

        results = retriever.retrieve(
            query="property ownership evidence",
            top_k=2,
        )

        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].chunk_id)
        self.assertTrue(results[0].doc_id)
        self.assertTrue(results[0].text)


if __name__ == "__main__":
    unittest.main()