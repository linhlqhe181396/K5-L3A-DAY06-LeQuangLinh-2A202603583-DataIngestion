import unittest
from unittest.mock import patch

from src.embeddings import DEFAULT_MODEL_NAME, MyEmbedder


class FakeModel:
    def __init__(self, _model_name: str) -> None:
        self.calls = []

    def get_embedding_dimension(self) -> int:
        return 2

    def encode(self, texts: list[str], **kwargs) -> list[list[float]]:
        self.calls.append((texts, kwargs))
        return [[0.6, 0.8] for _ in texts]


class MyEmbedderTests(unittest.TestCase):
    @patch("src.embeddings.SentenceTransformer", FakeModel)
    def test_embeds_documents_and_queries_with_the_same_model(self) -> None:
        embedder = MyEmbedder()

        documents = embedder.embed_documents(["first", "second"])
        query = embedder.embed_query("question")

        self.assertEqual(embedder.model_name, DEFAULT_MODEL_NAME)
        self.assertEqual(embedder.dimensions, 2)
        self.assertEqual(documents, [[0.6, 0.8], [0.6, 0.8]])
        self.assertEqual(query, [0.6, 0.8])
        self.assertEqual(len(embedder._model.calls), 2)
        self.assertTrue(all(call[1]["normalize_embeddings"] for call in embedder._model.calls))

    @patch("src.embeddings.SentenceTransformer", FakeModel)
    def test_returns_empty_list_for_empty_document_batch(self) -> None:
        embedder = MyEmbedder()

        self.assertEqual(embedder.embed_documents([]), [])
        self.assertEqual(embedder._model.calls, [])


if __name__ == "__main__":
    unittest.main()
