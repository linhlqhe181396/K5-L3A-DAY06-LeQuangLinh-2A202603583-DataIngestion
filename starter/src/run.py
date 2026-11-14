"""Build and evaluate the local pgvector retrieval benchmark."""
import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import DEFAULT_MODEL_NAME, MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_pdf
from .models import Chunk, DocumentPage
from .store import PgVectorStore


STARTER_ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = STARTER_ROOT / "data" / "my_document.pdf"
BENCHMARK_PATH = STARTER_ROOT / "benchmark" / "questions.jsonl"
RESULTS_PATH = STARTER_ROOT / "results"
DOCUMENT_ID = "my_document_01"
SOURCE = "starter/data/my_document.pdf"
SECTION_RANGES = {
    "executive_summary": (17, 26),
    "chapter_1": (31, 44),
    "chapter_2": (47, 92),
    "chapter_3": (101, 142),
    "chapter_4": (151, 191),
}
SOURCE_ATTRIBUTION = (
    "Adapted from Pradhan et al. (2026), Demographic Change in South Asia: "
    "From Tailwinds to Headwinds for Development, World Bank, "
    "https://doi.org/10.1596/978-1-4648-0959-0, CC BY 3.0 IGO."
)


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _load_selected_pages() -> list[DocumentPage]:
    if not PDF_PATH.is_file():
        raise FileNotFoundError(f"Corpus PDF not found: {PDF_PATH}")

    all_pages = load_pdf(PDF_PATH, DOCUMENT_ID, SOURCE)
    selected_pages: list[DocumentPage] = []
    for page in all_pages:
        for section, (first_page, last_page) in SECTION_RANGES.items():
            if first_page <= page.page <= last_page:
                if not page.text.strip():
                    raise ValueError(
                        f"Selected page {page.page} has no extractable text"
                    )
                page.metadata["section"] = section
                selected_pages.append(page)
                break

    if len(selected_pages) < 30:
        raise ValueError(
            f"Selected corpus has {len(selected_pages)} content pages; "
            "at least 30 are required"
        )
    return selected_pages


def _load_benchmark(pages: list[DocumentPage]) -> list[dict[str, Any]]:
    if not BENCHMARK_PATH.is_file():
        raise FileNotFoundError(f"Benchmark not found: {BENCHMARK_PATH}")

    questions = []
    with BENCHMARK_PATH.open(encoding="utf-8") as benchmark_file:
        for line_number, line in enumerate(benchmark_file, start=1):
            if line.strip():
                try:
                    questions.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"Invalid benchmark JSON on line {line_number}"
                    ) from error

    ids = [question.get("id") for question in questions]
    if len(questions) < 20 or len(ids) != len(set(ids)) or None in ids:
        raise ValueError("Benchmark must have at least 20 uniquely identified questions")
    if sum(question.get("split") == "dev" for question in questions) < 15:
        raise ValueError("Benchmark must have at least 15 dev questions")
    if sum(question.get("split") == "test" for question in questions) < 5:
        raise ValueError("Benchmark must have at least 5 test questions")
    if any(question.get("split") not in {"dev", "test"} for question in questions):
        raise ValueError("Every benchmark question must use the dev or test split")

    page_by_number = {page.page: page for page in pages}
    filtered_questions = [
        question for question in questions if question.get("filter")
    ]
    if (
        len(filtered_questions) < 3
        or not any(question["split"] == "test" for question in filtered_questions)
    ):
        raise ValueError("Benchmark requires at least 3 filtered questions, including 1 test")

    for question in questions:
        gold_page = page_by_number.get(question.get("gold_page"))
        if (
            question.get("gold_source_id") != DOCUMENT_ID
            or gold_page is None
            or not question.get("evidence_quote")
            or _normalized(question["evidence_quote"]) not in _normalized(gold_page.text)
        ):
            raise ValueError(
                f"Benchmark evidence for {question.get('id')!r} is not on its "
                "selected gold page"
            )
        filters = question.get("filter")
        if filters is not None:
            if not isinstance(filters, dict) or not filters:
                raise ValueError(f"Invalid metadata filter for {question['id']}")
            if any(gold_page.metadata.get(key) != value for key, value in filters.items()):
                raise ValueError(
                    f"Filter for {question['id']} does not match gold-page metadata"
                )
    return questions


def _build_strategies(
    pages: list[DocumentPage],
) -> dict[str, list[Chunk]]:
    fixed_chunks = [
        chunk
        for page in pages
        for chunk in fixed_size(page, size=500, overlap=50)
    ]
    paragraph_chunks = [
        chunk for page in pages for chunk in by_paragraph(page, max_size=500)
    ]
    return {
        "A": fixed_chunks,
        "B": paragraph_chunks,
        "C": paragraph_chunks,
    }


def _shared_coherence_samples(
    pages: list[DocumentPage],
    chunks_by_strategy: dict[str, list[Chunk]],
    count: int = 10,
) -> dict[str, list[tuple[Chunk, str, str]]]:
    if count <= 0 or len(pages) < count:
        raise ValueError("Need at least one source page per coherence sample")

    candidates_by_page: list[dict[str, tuple[Chunk, str, str]]] = []
    for page in pages:
        page_chunks = {
            strategy: [
                chunk for chunk in chunks
                if chunk.document_id == page.document_id and chunk.page == page.page
            ]
            for strategy, chunks in chunks_by_strategy.items()
        }
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"(?<=[.!?])\s+|\n+", page.text)
            if paragraph.strip()
            and len(paragraph.split()) >= 14
            and len(paragraph) >= 100
            and not re.match(
                r"(?i)^(?:note:|sources?:|for country code abbreviations|"
                r"(?:figure|table)\s*\d|a\.b\.|[a-d]\.\s*(?:bars|share|by|percent))",
                paragraph,
            )
            and "http://" not in paragraph.casefold()
            and "https://" not in paragraph.casefold()
        ]
        anchors: list[tuple[int, str]] = []
        for paragraph in sorted(paragraphs, key=len, reverse=True):
            anchor_length = min(60, len(paragraph))
            local_start = max(0, (len(paragraph) - anchor_length) // 2)
            anchor = paragraph[local_start:local_start + anchor_length]
            source_start = page.text.find(paragraph)
            if source_start >= 0:
                anchors.append((source_start + local_start, anchor))

        selected: dict[str, tuple[Chunk, str, str]] | None = None
        for source_offset, anchor in anchors:
            normalized_anchor = _normalized(anchor)
            matches = {
                strategy: next(
                    (
                        chunk for chunk in candidates
                        if normalized_anchor in _normalized(chunk.text)
                    ),
                    None,
                )
                for strategy, candidates in page_chunks.items()
            }
            if all(matches.values()):
                selected = {
                    strategy: (chunk, anchor, f"page-{page.page}-offset-{source_offset}")
                    for strategy, chunk in matches.items()
                    if chunk is not None
                }
                break

        if selected is not None:
            candidates_by_page.append(selected)

    if len(candidates_by_page) < count:
        raise ValueError(
            f"Found only {len(candidates_by_page)} pages with shared prose "
            f"positions; {count} are required"
        )
    page_indexes = sorted(
        {
            round(index * (len(candidates_by_page) - 1) / (count - 1))
            for index in range(count)
        }
    ) if count > 1 else [len(candidates_by_page) // 2]

    samples = {strategy: [] for strategy in chunks_by_strategy}
    for page_index in page_indexes:
        for strategy, sample in candidates_by_page[page_index].items():
            samples[strategy].append(sample)
    return samples


def _manual_assessment_rows(
    pages: list[DocumentPage],
    chunks_by_strategy: dict[str, list[Chunk]],
    traces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    if any(trace["split"] == "dev" for trace in traces):
        coherence_samples = _shared_coherence_samples(pages, chunks_by_strategy)
        for strategy, samples in coherence_samples.items():
            for chunk, source_excerpt, source_position in samples:
                rows.append(
                    {
                        "assessment_type": "chunk_coherence",
                        "source_attribution": SOURCE_ATTRIBUTION,
                        "strategy": strategy,
                        "source_position": source_position,
                        "source_excerpt": source_excerpt,
                        "chunk_id": chunk.chunk_id,
                        "source": chunk.source,
                        "page": chunk.page,
                        "text": chunk.text,
                        "score_0_to_2": None,
                        "reason": "",
                    }
                )

    for trace in traces:
        if trace["split"] != "test":
            continue
        rows.append(
            {
                "assessment_type": "grounding_quality",
                "source_attribution": SOURCE_ATTRIBUTION,
                "strategy": trace["strategy"],
                "question_id": trace["question_id"],
                "question": trace["question"],
                "expected_answer": trace["expected_answer"],
                "gold_page": trace["gold_page"],
                "top_3": [
                    {
                        "source": hit["source"],
                        "page": hit["page"],
                        "text": hit["text"],
                        "score": hit["score"],
                    }
                    for hit in trace["hits"][:3]
                ],
                "score_0_to_2": None,
                "reason": "",
            }
        )
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as output_file:
        for row in rows:
            output_file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _run(split: str) -> None:
    load_dotenv(STARTER_ROOT / ".env")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            f"DATABASE_URL is missing; configure it in {STARTER_ROOT / '.env'}"
        )

    pages = _load_selected_pages()
    questions = _load_benchmark(pages)
    chunks_by_strategy = _build_strategies(pages)
    model_name = os.getenv("EMBEDDING_MODEL", "").strip() or DEFAULT_MODEL_NAME

    model_started = time.perf_counter()
    embedder = MyEmbedder(model_name=model_name)
    model_load_seconds = time.perf_counter() - model_started
    store = PgVectorStore(database_url, embedder.dimensions)
    store.create_schema()

    strategy_stats: dict[str, dict[str, Any]] = {}
    vectors_by_strategy: dict[str, list[list[float]]] = {}
    for strategy, chunks in chunks_by_strategy.items():
        if strategy == "C":
            vectors_by_strategy[strategy] = vectors_by_strategy["B"]
            embedding_seconds = 0.0
        else:
            started = time.perf_counter()
            vectors = embedder.embed_documents([chunk.text for chunk in chunks])
            embedding_seconds = time.perf_counter() - started
            vectors_by_strategy[strategy] = vectors

        started = time.perf_counter()
        store.upsert(strategy, chunks, vectors_by_strategy[strategy])
        upsert_seconds = time.perf_counter() - started
        lengths = [len(chunk.text) for chunk in chunks]
        strategy_stats[strategy] = {
            "chunk_count": len(chunks),
            "chunk_characters": {
                "min": min(lengths) if lengths else 0,
                "mean": sum(lengths) / len(lengths) if lengths else 0,
                "max": max(lengths) if lengths else 0,
            },
            "embedding_seconds": embedding_seconds,
            "upsert_seconds": upsert_seconds,
            "vectors_reused_from": "B" if strategy == "C" else None,
        }

    selected_questions = [
        question
        for question in questions
        if split == "all" or question["split"] == split
    ]
    query_vectors: dict[str, list[float]] = {}
    query_embedding_seconds = 0.0
    for question in selected_questions:
        started = time.perf_counter()
        query_vectors[question["id"]] = embedder.embed_query(question["question"])
        query_embedding_seconds += time.perf_counter() - started

    traces = []
    for question in selected_questions:
        for strategy in ("A", "B", "C"):
            applied_filter = strategy == "C" and bool(question.get("filter"))
            filters = question.get("filter") if applied_filter else None
            hits = store.search(
                strategy,
                query_vectors[question["id"]],
                top_k=3,
                filters=filters,
            )
            trace = evaluate_query(question, hits)
            trace["strategy"] = strategy
            trace["source_attribution"] = SOURCE_ATTRIBUTION
            trace["filter_applied"] = applied_filter
            trace["filter_compliant"] = (
                bool(hits)
                and all(
                    all(hit["metadata"].get(key) == value for key, value in filters.items())
                    for hit in hits
                )
                if applied_filter
                else False
            )
            traces.append(trace)

    summary = summarize(traces)
    summary["run"] = {
        "split": split,
        "selected_content_pages": len(pages),
        "model": embedder.model_name,
        "embedding_dimensions": embedder.dimensions,
        "search": "exact cosine similarity via pgvector",
        "model_load_seconds": model_load_seconds,
        "query_embedding_seconds": query_embedding_seconds,
        "strategies": strategy_stats,
        "source_attribution": SOURCE_ATTRIBUTION,
        "automated_metrics_note": (
            "String-based evidence matching is a retrieval proxy only; "
            "chunk coherence and grounding quality require manual scoring."
        ),
    }

    RESULTS_PATH.mkdir(parents=True, exist_ok=True)
    trace_path = RESULTS_PATH / f"traces_{split}.jsonl"
    summary_path = RESULTS_PATH / f"summary_{split}.json"
    manual_path = RESULTS_PATH / f"manual_assessment_{split}.jsonl"
    _write_jsonl(trace_path, traces)
    _write_jsonl(
        manual_path,
        _manual_assessment_rows(pages, chunks_by_strategy, traces),
    )
    with summary_path.open("w", encoding="utf-8") as summary_file:
        json.dump(summary, summary_file, ensure_ascii=False, indent=2)
        summary_file.write("\n")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Traces: {trace_path}")
    print(f"Manual assessment template: {manual_path}")
    print(f"Summary: {summary_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split",
        choices=("dev", "test", "all"),
        default="dev",
        help="Benchmark split to retrieve; default is dev to keep test unseen.",
    )
    args = parser.parse_args()
    _run(args.split)


if __name__ == "__main__":
    main()
