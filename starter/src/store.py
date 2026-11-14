"""Persistent vector storage and cosine-similarity search with pgvector."""
import math
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .models import Chunk


_TABLE_NAME = "ingestion_chunks"


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if not database_url.strip():
            raise ValueError("database_url must not be empty")
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")

        self.database_url = database_url
        self.dimensions = dimensions

    def create_schema(self) -> None:
        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {_TABLE_NAME} (
                        strategy TEXT NOT NULL,
                        chunk_id TEXT NOT NULL,
                        document_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        page INTEGER NOT NULL,
                        text TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        embedding VECTOR({self.dimensions}) NOT NULL,
                        PRIMARY KEY (strategy, chunk_id)
                    )
                    """
                )
                cursor.execute(
                    """
                    SELECT format_type(atttypid, atttypmod)
                    FROM pg_attribute
                    WHERE attrelid = %s::regclass
                      AND attname = 'embedding'
                      AND NOT attisdropped
                    """,
                    (_TABLE_NAME,),
                )
                row = cursor.fetchone()
                expected_type = f"vector({self.dimensions})"
                if row is None or row[0] != expected_type:
                    actual_type = row[0] if row else "missing"
                    raise ValueError(
                        f"Existing embedding column is {actual_type}; "
                        f"configured model requires {expected_type}"
                    )

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Atomically replace all chunks for one strategy without stale rows."""
        if not strategy.strip():
            raise ValueError("strategy must not be empty")
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError(f"duplicate chunk IDs in strategy {strategy!r}")

        rows = []
        for chunk, vector in zip(chunks, vectors):
            vector_literal = self._vector_literal(vector)
            rows.append(
                (
                    strategy,
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.source,
                    chunk.page,
                    chunk.text,
                    Jsonb(chunk.metadata),
                    vector_literal,
                )
            )

        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"DELETE FROM {_TABLE_NAME} WHERE strategy = %s",
                    (strategy,),
                )
                if rows:
                    cursor.executemany(
                        f"""
                        INSERT INTO {_TABLE_NAME}
                            (strategy, chunk_id, document_id, source, page, text, metadata, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                        """,
                        rows,
                    )

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return nearest chunks, optionally filtering JSONB metadata in SQL."""
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        vector_literal = self._vector_literal(query_vector)
        if filters is not None and not isinstance(filters, dict):
            raise TypeError("filters must be a dictionary or None")

        filter_clause = " AND metadata @> %s::jsonb" if filters is not None else ""
        parameters: list[Any] = [vector_literal, strategy]
        if filters is not None:
            parameters.append(Jsonb(filters))
        parameters.extend([vector_literal, top_k])

        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT chunk_id, document_id, source, page, text, metadata,
                           1 - (embedding <=> %s::vector) AS score
                    FROM {_TABLE_NAME}
                    WHERE strategy = %s{filter_clause}
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    parameters,
                )
                return [
                    {
                        "chunk_id": row[0],
                        "document_id": row[1],
                        "source": row[2],
                        "page": row[3],
                        "text": row[4],
                        "metadata": row[5],
                        "score": float(row[6]),
                    }
                    for row in cursor.fetchall()
                ]

    def _vector_literal(self, vector: list[float]) -> str:
        if len(vector) != self.dimensions:
            raise ValueError(
                f"vector has {len(vector)} dimensions; expected {self.dimensions}"
            )
        values = [float(value) for value in vector]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("vector values must be finite numbers")
        return "[" + ",".join(format(value, ".9g") for value in values) + "]"
