# Exploratory Findings — PII Specificity and Downstream Guidance

Source repo revision: `90bc32d737af8d8a9abdb11d78ca6257dc46c8f2` (baseline from 2026-10-29).

## Research question

Are districts that identify more categories of personal information in AI privacy excerpts
also more likely to include directions about AI model training or data retention/deletion?

## Comparison

| PII categories named | Districts | Any direction | Training direction | Retention/deletion direction |
|---|---:|---:|---:|---:|
| 0 types | 56 | 8/56 (14.3%) | 6 | 4 |
| 1-3 types | 28 | 5/28 (17.9%) | 4 | 2 |
| 4+ types | 26 | 6/26 (23.1%) | 5 | 2 |

Matched 110 districts across 126 district privacy excerpts.
The organization-level PII spectrum contains 110 districts with coded privacy excerpts; document-level source data also include
districts without matching excerpts, which cannot be included in this comparison.

## Interpretation

Compare the group rates as exploratory descriptive summaries; do not assume that a
larger number of named PII categories implies more effective privacy safeguards.
The analysis does not establish statistical significance, causality, implemented
protections, or legal quality.
The relationship may reflect excerpt length, source type, selection, and coding differences.

## Excerpt-length sensitivity

A district is included below if at least one matching privacy excerpt contains 1,000+
body-text characters. PII specificity still comes from the district-level summary of its
available documents; this is a descriptive coverage check, not a causal adjustment.

| PII categories named | Districts with longer excerpt | Any direction |
|---|---:|---:|
| 0 types | 29 | 7/29 (24.1%) |
| 1-3 types | 23 | 5/23 (21.7%) |
| 4+ types | 25 | 6/25 (24.0%) |

Across PII groups, the range of observed rates is 8.8 percentage points
in the full matched sample and 2.4 points in the longer-excerpt subset.
This is a **sensitivity check**, not proof that length causes the pattern to change.

## Recommended independent validation

An audit sample of 15 included atomic provisions was exported to
`results/manual_review_queue.csv`. Open the original sources, check quotation and context,
then record your decision in the empty reviewer columns. This has **not** been done yet.

## Definitions and limitations

- Unit of analysis is **distinct district**; state guidance is excluded.
- PII specificity = count of named PII categories in the existing organization summary,
  grouped into 0, 1–3, or 4+ categories. This is not privacy quality.
- `direction` means the existing atomic-provision profile is `direction_only` or `both`
  for **model_training** or **retention_deletion**. It may be recommended, not mandatory.
- The three 'discusses' outcomes use `explicit_content_found` for training, sharing,
  and retention. They are **topic mentions**, not implemented protections.
- Missing profile/topic content means not located in the *reviewed excerpt*, not absent
  from the full policy or actual district practice.
- Some districts have multiple documents; aggregation uses `any` per district.
- AI-assisted upstream coding lacks independent human reliability checks, and excerpt
  authenticity, currency, completeness, and policy adoption have not been verified.
- Avoid causal claims, significance claims, policy-strength rankings, or national generalizations.

## Files

- `results/district_level.csv`: one row per included district.
- `results/group_summary.csv`: one row per PII group; counts and percentages.
- `results/long_excerpt_summary.csv`: length-based sensitivity check.
- `results/manual_review_queue.csv`: quotations requiring original-source validation.
- `figures/pii_vs_directions.png`: main visualization.
- `figures/pii_vs_topics.png`: explicit discussion by topic.
- `figures/pii_vs_excerpt_length.png`: full-sample vs. longer-excerpt sensitivity.

## Data and provenance

Data from the `AIDataLab-Fall2026` repository, with no scraping or changes to upstream
sources in this folder. Do not treat this exploratory output as an independent policy audit.
