# K-12 AI Policy Research

This repository collects and analyzes U.S. K-12 artificial-intelligence policies
and guidance, with a focus on student privacy. It includes the policy corpus,
privacy excerpts, evidence tables, analysis scripts, and research figures.

## Work in this repository

- **Policy corpus and policy analysis.** The root CSV files hold the K-12 AI
  policy inventory and a single-line version used for analysis. The project
  also includes work categorizing AI investments and state policy guidance.
- **Privacy passage collection.** Privacy and student-data passages were
  collected from a 205-document policy inventory. The collection contains 184
  PDFs with privacy content, plus a log covering the full inventory. See
  [`Privacy Passages/README.md`](Privacy%20Passages/README.md) for collection
  methods, coverage, and source-access caveats.
- **PII and AI-tool coding.** The [`PII and AI Tools/`](PII%20and%20AI%20Tools/)
  analysis identifies personal-data categories and records how policies
  describe AI tools (approved, conditional, not approved, or mentioned).
  Its README describes the evidence, coding rules, and limitations.
- **Student privacy study.** The exploratory study in [`privacy_study/`](privacy_study/)
  examines model training, data sharing/secondary use, and retention/deletion
  across the 184 privacy-excerpt PDFs. It includes reviewed quotations, CSV
  summaries, sensitivity checks, and static PNG/PDF figures. Its
  [`README.md`](privacy_study/README.md) contains the methods and detailed
  findings.
- **Research pilots.** Root-level R scripts implement passage retrieval,
  evaluation, provision coding, and a separate topic-modeling pilot. The
  pilot instructions explain how to run and review the passage pipeline.

## Selected results

In the exploratory privacy study, explicit discussion was found in:

| Topic | Documents | Share of 184 |
|---|---:|---:|
| Model training / improvement | 52 | 28.3% |
| Sharing / secondary use | 78 | 42.4% |
| Retention / deletion | 37 | 20.1% |

These are counts of topics located in the supplied excerpts, not ratings of
protection strength, legal compliance, or implementation. A topic not located
in an excerpt does not mean the original policy lacks a relevant provision.
The study is exploratory and AI-assisted; it has not been independently
human-validated, and original-source authenticity, currency, and completeness
have not been verified. See the study README and methods notes before citing
or interpreting the results.

## Reproducing the R checks

Run from the repository root with R installed:

```sh
Rscript test_passage_pilot.R
Rscript test_privacy_provisions.R
Rscript test_privacy_study.R
```

The PDF extraction and study-preparation scripts require the R package
`pdftools`; the study summarizer also requires `jsonlite`. The topic-model
pilot has its own package requirements. See [`passage_pilot_instructions.txt`](passage_pilot_instructions.txt)
for the pilot workflow and output-directory safeguards.

## Repository map

| Path | Contents |
|---|---|
| `k12_ai_policies.csv`, `k12_ai_policies_singleline.csv` | Policy inventory data |
| `Privacy Passages/` | Per-document privacy excerpt PDFs, coverage log, and collection notes |
| `PII and AI Tools/` | PII and AI-tool evidence tables, summaries, and charts |
| `privacy_study/` | Study evidence, summaries, methods, and figures |
| `passage_*.R`, `prepare_privacy_study.R`, `summarize_*.R` | Extraction and analysis code |
| `test_*.R` | Focused R checks for extraction, provisions, and study summaries |
