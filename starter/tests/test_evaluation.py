import unittest

from src.evaluation import evaluate_query, summarize


QUESTION = {
    "id": "q1",
    "split": "dev",
    "question": "What happened?",
    "expected_answer": "It happened.",
    "gold_source_id": "doc-1",
    "gold_page": 7,
    "evidence_quote": "The evidence says this happened.",
    "filter": {"section": "chapter_1"},
}


class EvaluateQueryTests(unittest.TestCase):
    def test_requires_matching_source_page_and_evidence(self) -> None:
        hits = [
            {
                "document_id": "doc-1",
                "source": "doc.pdf",
                "page": 8,
                "text": "The evidence says this happened.",
                "metadata": {"section": "chapter_1"},
                "score": 0.9,
            },
            {
                "document_id": "doc-1",
                "source": "doc.pdf",
                "page": 7,
                "text": "The evidence says\nthis happened.",
                "metadata": {"section": "chapter_1"},
                "score": 0.8,
            },
        ]

        result = evaluate_query(QUESTION, hits)

        self.assertFalse(result["hit_at_1"])
        self.assertTrue(result["evidence_hit_at_3"])
        self.assertFalse(result["hits"][0]["source_page_match"])
        self.assertTrue(result["hits"][1]["gold_match"])

    def test_supports_alternative_gold_pages_and_quotes(self) -> None:
        question = {
            **QUESTION,
            "alternative_gold_pages": [9],
            "alternative_evidence_quotes": ["An alternate verified excerpt."],
        }
        hit = {
            "document_id": "doc-1",
            "source": "doc.pdf",
            "page": 9,
            "text": "An alternate verified excerpt.",
            "metadata": {},
            "score": 0.9,
        }

        result = evaluate_query(question, [hit])

        self.assertTrue(result["hit_at_1"])

    def test_summarizes_retrieval_and_filter_metrics(self) -> None:
        trace = evaluate_query(
            QUESTION,
            [
                {
                    "document_id": "doc-1",
                    "source": "doc.pdf",
                    "page": 7,
                    "text": QUESTION["evidence_quote"],
                    "metadata": {"section": "chapter_1"},
                    "score": 0.9,
                }
            ],
        )
        trace.update(
            {
                "strategy": "C",
                "filter_applied": True,
                "filter_compliant": True,
            }
        )

        result = summarize([trace])["C"]["dev"]

        self.assertEqual(result["hit_at_1"]["rate"], 1.0)
        self.assertEqual(result["evidence_hit_at_3"]["rate"], 1.0)
        self.assertEqual(result["metadata_traceability"]["rate"], 1.0)
        self.assertEqual(result["filter_compliance"]["rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
