# Benchmark source and page selection

## Corpus selection

`my_document.pdf` contains 204 physical PDF pages. Based on its table of
contents, the selected substantive ranges are:

- Executive Summary: physical pages 17-26
- Chapter 1: physical pages 31-44
- Chapter 2: physical pages 47-92
- Chapter 3: physical pages 101-142
- Chapter 4: physical pages 151-191

This yields 153 selected pages with extractable text. Front matter,
acknowledgments, author biographies, abbreviations, notes/references,
inter-chapter material, and back matter are excluded. Physical page numbers
refer to the PDF, not the book's printed page labels. See
`../results/my_document_page_inventory.csv` for extraction status and character
counts for every physical page.

The `section` metadata values used by benchmark filters are assigned from the
same table-of-contents ranges. Apply the filter only when a question explicitly
asks for a chapter; questions with no filter use `null`.

## Split and verification

The 20 questions are split into 15 dev and 5 test questions. Evidence quotes
were checked against normalized text from the cited physical PDF pages. The
test split must remain fixed while selecting or tuning retrieval strategies.
Filter questions include the requested section in the question so that the
filter is available before retrieval.

## Attribution and license

Adapted from: Pradhan, Elina, Syud Amer Ahmed, Lynn Hu, Jumana Alaref, Zoe
Xie, Omoniyi Alimi, Miglena Abels, and Margaret Triyana. 2026. *Demographic
Change in South Asia: From Tailwinds to Headwinds for Development*. South Asia
Development Matters. World Bank.
https://doi.org/10.1596/978-1-4648-0959-0. License: Creative Commons
Attribution 3.0 IGO (CC BY 3.0 IGO).

The question wording, split, and benchmark record are adaptations. Figure,
table, and other third-party content are not included in this benchmark; check
their separate rights before reusing them.
