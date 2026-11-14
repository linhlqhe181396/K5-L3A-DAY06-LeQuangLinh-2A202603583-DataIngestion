import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.ingestion import load_pdf, normalize_text


class NormalizeTextTests(unittest.TestCase):
    def test_normalizes_unicode_and_whitespace_preserving_paragraphs(self) -> None:
        self.assertEqual(
            normalize_text("  e\u0301  \r\n\tline\x00\n\n\nnext  "),
            "é\nline\n\nnext",
        )


class LoadPdfTests(unittest.TestCase):
    @patch("src.ingestion.PdfReader")
    def test_preserves_page_trace_and_marks_pages_without_text(self, reader_class) -> None:
        reader_class.return_value.pages = [
            SimpleNamespace(extract_text=lambda: " first page "),
            SimpleNamespace(extract_text=lambda: None),
        ]

        pages = load_pdf("document.pdf", "doc-1", "document.pdf")

        self.assertEqual([page.page for page in pages], [1, 2])
        self.assertEqual([page.text for page in pages], ["first page", ""])
        self.assertEqual(pages[0].metadata["extraction_status"], "extracted")
        self.assertEqual(pages[0].metadata["char_count"], 10)
        self.assertEqual(pages[1].metadata["extraction_status"], "no_text")
        self.assertEqual(pages[1].metadata["char_count"], 0)
        self.assertTrue(all(page.document_id == "doc-1" for page in pages))
        self.assertTrue(all(page.source == "document.pdf" for page in pages))


if __name__ == "__main__":
    unittest.main()
