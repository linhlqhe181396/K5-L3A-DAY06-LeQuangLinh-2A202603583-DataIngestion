"""Sentence Transformers adapter for local text embeddings."""
from typing import Protocol

from sentence_transformers import SentenceTransformer


DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """Create normalized vectors with one local Sentence Transformers model."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        if not model_name.strip():
            raise ValueError("model_name must not be empty")

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)
        dimensions = self._model.get_embedding_dimension()
        if dimensions is None or dimensions <= 0:
            raise RuntimeError(f"Model {model_name!r} did not report a valid embedding dimension")
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_query(self, question: str) -> list[float]:
        return self._encode([question])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        encoded = self._model.encode(
            texts,
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        if len(encoded) != len(texts):
            raise RuntimeError(
                f"Model returned {len(encoded)} vectors for {len(texts)} input texts"
            )

        vectors = [[float(value) for value in vector] for vector in encoded]
        if any(len(vector) != self.dimensions for vector in vectors):
            raise RuntimeError(
                f"Model returned a vector with an unexpected dimension; "
                f"expected {self.dimensions}"
            )
        return vectors
