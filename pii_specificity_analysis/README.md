# PII Specificity vs. Downstream Data-Use Guidance

**Independent exploratory analysis — K–12 AI student-privacy policies**

## Research question

> Are school districts that name more categories of personally identifiable information (PII) in their AI-privacy excerpts more likely to include directions on AI model training and student-data retention or deletion?

This extends the repository's PII-category inventory and atomic privacy-provision coding by **joining the existing datasets at the district level**. It does not reclassify any source policy as legally compliant or noncompliant. It is not a new scrape or an independent audit.

## Why this analysis matters

Simply referring to "student privacy" does not tell educators what counts as sensitive information, or how AI vendors should use and delete that information. We compare the *specificity of information categories named* with the *presence of directions about downstream data practices*—two distinct policy-text features. The result can help school districts identify concrete questions to ask while drafting or reviewing AI guidance.

## Inputs (already in the repository)

| File | How it is used |
|---|---|
| `PII and AI Tools/pii_spectrum_by_organization.csv` | Unique districts and 29-category PII item counts |
| `PII and AI Tools/pii_and_tools_by_document.csv` | Link district names to their excerpt-PDF filenames |
| `privacy_study/reviewed_documents.csv` | Link PDF filenames to stable `doc_id` and excerpt length |
| `privacy_study/provision_document_profiles.csv` | Flag direction-only or combined direction/review profiles for model training and retention/deletion |
| `privacy_study/document_category_matrix.csv` | Compare discussion of model training, sharing/secondary use, and retention/deletion |
| `privacy_study/atomic_provisions.csv` | Create a small quotation-based manual review queue |

## Quick start

Keep this entire `pii_specificity_analysis/` folder directly inside the **`AIDataLab-Fall2026`** repository (next to `PII and AI Tools/` and `privacy_study/`). In the VS Code terminal:

```bash
cd "/Users/jiayi/Documents/K12-AI-Privacy-Work/AIDataLab-Fall2026"
python3 -m pip install -r pii_specificity_analysis/requirements.txt
python3 pii_specificity_analysis/analyze.py
```

Or use an explicit root path:

```bash
python3 pii_specificity_analysis/analyze.py --root "/path/to/AIDataLab-Fall2026"
```

The script only writes to this analysis directory. It does not modify or overwrite your teammates' upstream files. Running again refreshes the files inside this directory.

## Deliverables

- `analyze.py` — reproducible Python/pandas analysis and figures.
- `results/group_summary.csv` — grouped comparison with denominators and percentages.
- `results/district_level.csv` — 110 matched districts, one row per district, with coding flags and source coverage diagnostics (after running locally).
- `results/long_excerpt_summary.csv` — sensitivity analysis for districts with a 1,000+ character privacy excerpt.
- `results/manual_review_queue.csv` — small, unverified quotation sample to audit against original policy sources.
- `figures/pii_vs_directions.png` — directions about model training or retention/deletion by PII specificity.
- `figures/pii_vs_topics.png` — prevalence of discussion across three downstream practices.
- `figures/pii_vs_excerpt_length.png` — how the apparent pattern changes in longer excerpts.
- `FINDINGS.md` — generated results and limitations.

Pre-populated group summaries and images are a snapshot computed from repository revision `90bc32d` on 2026-10-29. **Rerun `analyze.py` in your clone before presenting or committing** to regenerate all outputs from the source files. The script produces the district-level file and review queue on that first run.

## Units and operational definitions

1. **District is the unit.** State-level entries are excluded, and multiple documents for one district are aggregated with an `any` rule. Only districts with a matching excerpt PDF can be analyzed.
2. **PII specificity** is grouped as 0, 1–3, or 4+ *named* PII categories in the existing organization-level coding. A value of zero may reflect general wording or omitted context; it does **not** mean no privacy protection.
3. **Any direction** means the district has at least one existing document profile with `direction_only` or `both` for `model_training` or `retention_deletion`. These labels can include recommendations, not just binding rules.
4. **Topic discussed** means existing `explicit_content_found=TRUE` for that topic. Warnings and vendor-review questions count. No specific actions are inferred for *sharing/secondary use*, which was not independently coded into atomic provisions.
5. **Excerpt length check** retains districts with at least one matching reviewed excerpt containing 1,000+ body characters. This is descriptive and not a statistical adjustment.

## Baseline results (exploratory)

| PII types named | Districts | Any training/retention direction |
|---|---:|---:|
| 0 | 56 | 8 (14.3%) |
| 1–3 | 28 | 5 (17.9%) |
| 4+ | 26 | 6 (23.1%) |
| **Total** | **110** | **19 (17.3%)** |

The observed association is modest. Differences in excerpt length, policy type, selection and missing evidence may explain the pattern. These are descriptive counts, **not a significant association, causal finding, privacy-strength rating, or nationally representative estimate**.

## What should be validated next?

Open `results/manual_review_queue.csv`, compare each quoted provision with the **original** district policy, and fill in reviewer columns. Check whether excerpts are complete, whether the source is an adopted policy, who is being instructed, and whether the clause creates an actual data practice or only asks a question. Compare at least a few districts with similar excerpt length and different PII specificity groups.

## Research and authorship caveats

- This analysis reuses previously coded data. Upstream coding was AI-assisted and has not been independently validated; direct-source authenticity, currency, completeness, and adoption may be uncertain.
- A district's silence in a **selected excerpt** does not prove its full policy is silent. Model-policy templates are not evidence that districts adopted them.
- The analysis is not a FERPA/COPPA compliance audit, vendor-security review, causal study, or national comparison of all districts.
- Do not present the code's output as human-audited evidence until original policy checks are completed.
- Appropriate attribution to the repository's earlier data collection and coding work is important.

## Suggested presentation language

> We linked existing policy-excerpt data across 110 districts and compared how many personal-information categories each district names with whether its excerpts contain directions about AI model training or data retention/deletion. In this exploratory sample, 23.1% of districts listing four or more categories had such a direction, compared with 14.3% listing none. The difference is descriptive; it may reflect excerpt selection and length. Next we will validate a sample of original policies and translate recurring gaps into a district-facing checklist.

### Important sensitivity result

Restricting the comparison to districts with at least one privacy excerpt of 1,000+ body-text characters gives approximately **24.1% (7/29)**, **21.7% (5/23)**, and **24.0% (6/25)** with a direction in the 0, 1–3, and 4+ PII groups respectively. Thus, the apparent gradient in the full matched data is **not stable** under this simple coverage restriction. This strengthens the need to consider document length and sampling before drawing conclusions.
