"""Evidence-based retrieval metrics and per-query traces."""
import re
from typing import Any


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Score source/page/evidence matches without inferring answer quality."""
    gold_sources = {question["gold_source_id"]}
    gold_sources.update(question.get("alternative_gold_source_ids", []))
    gold_pages = {int(question["gold_page"])}
    gold_pages.update(int(page) for page in question.get("alternative_gold_pages", []))
    evidence_quotes = [question["evidence_quote"]]
    evidence_quotes.extend(question.get("alternative_evidence_quotes", []))
    normalized_quotes = [_normalize(quote) for quote in evidence_quotes if quote.strip()]
    if not normalized_quotes:
        raise ValueError(f"Question {question.get('id')!r} has no evidence quote")

    evaluated_hits = []
    for hit in hits:
        source_page_match = (
            hit.get("document_id") in gold_sources
            and int(hit.get("page", -1)) in gold_pages
        )
        normalized_text = _normalize(hit.get("text", ""))
        evidence_match = any(quote in normalized_text for quote in normalized_quotes)
        evaluated_hits.append(
            {
                **hit,
                "source_page_match": source_page_match,
                "evidence_match": evidence_match,
                "gold_match": source_page_match and evidence_match,
            }
        )

    return {
        "question_id": question["id"],
        "split": question["split"],
        "question": question["question"],
        "expected_answer": question["expected_answer"],
        "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"],
        "filter": question.get("filter"),
        "hits": evaluated_hits,
        "hit_at_1": bool(evaluated_hits and evaluated_hits[0]["gold_match"]),
        "evidence_hit_at_3": any(hit["gold_match"] for hit in evaluated_hits[:3]),
    }


def _rate(successes: int, total: int) -> dict[str, Any]:
    return {
        "successes": successes,
        "total": total,
        "rate": successes / total if total else None,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate retrieval and traceability metrics by strategy and split."""
    summary: dict[str, Any] = {}
    strategies = sorted({trace["strategy"] for trace in traces})
    for strategy in strategies:
        summary[strategy] = {}
        splits = sorted(
            {trace["split"] for trace in traces if trace["strategy"] == strategy}
        )
        for split in splits:
            group = [
                trace
                for trace in traces
                if trace["strategy"] == strategy and trace["split"] == split
            ]
            hits = [hit for trace in group for hit in trace["hits"]]
            traceable_hits = sum(
                bool(hit.get("source")) and int(hit.get("page", 0)) > 0
                for hit in hits
            )
            filtered = [
                trace for trace in group if trace.get("filter_applied", False)
            ]
            summary[strategy][split] = {
                "question_count": len(group),
                "hit_at_1": _rate(
                    sum(trace["hit_at_1"] for trace in group), len(group)
                ),
                "evidence_hit_at_3": _rate(
                    sum(trace["evidence_hit_at_3"] for trace in group), len(group)
                ),
                "metadata_traceability": _rate(traceable_hits, len(hits)),
                "filter_compliance": _rate(
                    sum(bool(trace["filter_compliant"]) for trace in filtered),
                    len(filtered),
                ),
            }
    return summary
