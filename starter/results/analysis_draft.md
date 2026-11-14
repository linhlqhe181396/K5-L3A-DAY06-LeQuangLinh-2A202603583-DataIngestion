# Retrieval benchmark analysis draft

**Status:** working draft. Retrieval and metadata numbers below were measured.
Manual score suggestions are AI-assisted and still require the student's
independent review before being reported as manual assessments.

## Setup and selection rule

The corpus is 153 extracted-content pages from the World Bank report
*Demographic Change in South Asia: From Tailwinds to Headwinds for Development*.
The benchmark has 20 questions split into 15 dev and 5 test, with section
metadata assigned from the documented physical-page ranges. All strategies use
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions)
and PostgreSQL 16.16 with pgvector 0.8.7, using exact cosine search. The model
runs locally; no hosted embedding API cost was incurred.

The selection rule was recorded in `selection_rule.txt` before running test:
maximize dev Evidence Hit@3; in a tie, prefer metadata filtering when
question-provided section filters are required. The test split has now been
viewed and was not used to change the configurations.

## Retrieval results

| Strategy | Dev Hit@1 | Dev Evidence Hit@3 | Test Hit@1 | Test Evidence Hit@3 |
|---|---:|---:|---:|---:|
| A: 500-character fixed chunks, 50-character overlap | 5/15 (33.3%) | 6/15 (40.0%) | 2/5 (40.0%) | 2/5 (40.0%) |
| B: paragraph chunks, maximum 500 characters | 4/15 (26.7%) | 8/15 (53.3%) | 1/5 (20.0%) | 2/5 (40.0%) |
| C: B plus question-provided section filter | 4/15 (26.7%) | 8/15 (53.3%) | 1/5 (20.0%) | 2/5 (40.0%) |

Evidence Hit@3 is strict: the retrieved chunk must match the benchmark's
recorded source/page and evidence quote. A retrieved equivalent passage on a
different page may support an answer but is not counted by this automatic
metric unless listed as alternative gold evidence.

## Metadata audit

An audit against the corpus page ranges found correct `document_id`, source,
page, and section metadata on **180/180** retrieved test/dev top-three records.
For C, all question-level section filters complied: **5/5 dev** and **3/3
test** questions; all returned chunks for those queries matched the requested
section (**24/24** combined). A and B intentionally do not apply filters, so
their filter-compliance rate is not applicable.

`section` is useful when a question names a chapter, but it is page-level
metadata: it cannot distinguish topics within a chapter, and it depends on the
documented physical-page-to-section mapping.

## Chunk and resource comparison

| Strategy | Chunks | Test embedding time | Notes |
|---|---:|---:|---|
| A | 1,015 | 79.1 s | Fixed windows; sometimes cuts a sentence or table row |
| B | 987 | 79.7 s | Paragraph grouping; chunks may still hit the 500-character limit |
| C | 987 | 0 s additional | Reuses B vectors; upserts the filtered-search strategy separately |

Embedding time is local wall-clock time, not a billed cost. It varies by
hardware and run conditions. The measured timings do not justify a general
performance conclusion.

## Manual assessment: provisional AI-assisted suggestions

The same 10 source positions are now presented for A, B, and C in
`manual_assessment_dev.jsonl`. The separate
`assessment_suggestions_test.jsonl` gives an initial score and reason for each
of those 30 chunks and each of the 15 test strategy/question cases. These are
suggestions, **not the student's manual scores**; review the chunk and top-three
evidence, then enter your own confirmed score and reason in the assessment
templates.

The draft coherence means are A **1.3/2**, B **1.6/2**, and C **1.6/2**. The
provisional grounding suggestions are **2.0/2** for each strategy. In several
test cases, the top-three contains a sufficient equivalent passage but not the
benchmark's exact gold page, explaining why the suggested manual grounding
score can be higher than strict automatic Evidence Hit@3.

The test grounding template is `manual_assessment_test.jsonl` (five questions
per strategy). The coherence template is in the dev assessment file; score
each shared position once, not again in the test file.

## Interpretation and limitations

- On dev, B/C improve Evidence Hit@3 over A (8/15 vs. 6/15), while A has more
  Hit@1 successes (5/15 vs. 4/15).
- On test, all three tie on Evidence Hit@3 (2/5); A has one more Hit@1 success
  than B/C (2/5 vs. 1/5). The test set is too small to claim a general winner.
- C matches B's retrieval metrics while enforcing the provided section filter.
  Prefer C when a question needs that filter; for unfiltered queries B and C
  use the same chunks and vectors. A may be preferable when top-1 ranking is
  more important, but the small test result is not conclusive.
- The test examples include equivalent evidence on a different page (for
  example, q05 has the 69-percent peak statement on page 37). This is a
  limitation of the strict single-page gold metric, not proof that the answer
  is unsupported. Do not edit the test labels after seeing these results and
  present them as an untouched holdout.
- The manual scores are provisional until reviewed and confirmed by the author.

## Reproducibility

From `starter/`, run `python -m src.run` for dev and
`python -m src.run --split test` for test. Results are in `results/summary_*.json`,
`results/traces_*.jsonl`, and the manual assessment templates. The source is
attributed in the trace and assessment records under CC BY 3.0 IGO.
