import re
import unittest

from src.chunking import by_paragraph, fixed_size
from src.models import DocumentPage


def make_page(text: str) -> DocumentPage:
    return DocumentPage(
        document_id="doc-1",
        source="source.pdf",
        page=7,
        text=text,
        metadata={"section": "chapter_1"},
    )


class FixedSizeTests(unittest.TestCase):
    def test_splits_with_overlap_and_retains_source_metadata(self) -> None:
        chunks = fixed_size(make_page("abcdefghij"), size=6, overlap=2)

        self.assertEqual([chunk.text for chunk in chunks], ["abcdef", "efghij"])
        self.assertEqual(chunks[0].page, 7)
        self.assertEqual(chunks[0].metadata["section"], "chapter_1")
        self.assertEqual(chunks[0].metadata["chunk_strategy"], "fixed_size")
        self.assertNotEqual(chunks[0].chunk_id, chunks[1].chunk_id)

    def test_rejects_invalid_size_and_overlap(self) -> None:
        page = make_page("text")

        with self.assertRaises(ValueError):
            fixed_size(page, size=0, overlap=0)
        with self.assertRaises(ValueError):
            fixed_size(page, size=4, overlap=4)


class ParagraphTests(unittest.TestCase):
    def test_groups_and_splits_paragraphs_without_losing_words(self) -> None:
        text = "Short first paragraph.\n\nA longer paragraph has several words to split safely."
        chunks = by_paragraph(make_page(text), max_size=30)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk.text) <= 30 for chunk in chunks))
        normalized_chunks = re.sub(r"\s+", " ", " ".join(chunk.text for chunk in chunks)).strip()
        normalized_source = re.sub(r"\s+", " ", text).strip()
        self.assertEqual(normalized_chunks, normalized_source)
        self.assertTrue(all(chunk.metadata["section"] == "chapter_1" for chunk in chunks))
        self.assertTrue(all(chunk.metadata["chunk_strategy"] == "by_paragraph" for chunk in chunks))

    def test_empty_pages_make_no_chunks(self) -> None:
        self.assertEqual(by_paragraph(make_page(" \n "), max_size=20), [])
