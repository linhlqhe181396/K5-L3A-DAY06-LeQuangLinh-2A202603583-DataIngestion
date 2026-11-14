import unittest

from src.chunking import by_paragraph, fixed_size
from src.models import DocumentPage
from src.run import _shared_coherence_samples


class SharedCoherenceSamplesTests(unittest.TestCase):
    def test_selects_the_same_source_position_for_each_strategy(self) -> None:
        page = DocumentPage(
            document_id="doc-1",
            source="doc.pdf",
            page=5,
            text=(
                "A meaningful sentence keeps its context in the document and "
                "explains the intended subject with enough detail for a reader "
                "to understand the surrounding argument. "
            ) * 20,
            metadata={"section": "chapter_1"},
        )
        fixed_chunks = fixed_size(page, size=120, overlap=20)
        paragraph_chunks = by_paragraph(page, max_size=120)
        strategies = {
            "A": fixed_chunks,
            "B": paragraph_chunks,
            "C": paragraph_chunks,
        }

        samples = _shared_coherence_samples([page], strategies, count=1)

        self.assertEqual(
            {
                sample[2]
                for strategy_samples in samples.values()
                for sample in strategy_samples
            },
            {samples["A"][0][2]},
        )
        self.assertEqual(
            {
                sample[1]
                for strategy_samples in samples.values()
                for sample in strategy_samples
            },
            {samples["A"][0][1]},
        )
        for strategy, strategy_samples in samples.items():
            chunk, excerpt, _ = strategy_samples[0]
            self.assertIn(excerpt, chunk.text)
            self.assertEqual(chunk.page, 5)


if __name__ == "__main__":
    unittest.main()
