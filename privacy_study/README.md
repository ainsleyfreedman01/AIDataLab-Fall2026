# Student privacy in K-12 AI policy excerpts

## What this project asks

**Which downstream student-data practices do the supplied excerpts address,
and how do they describe restrictions, permissions, and review procedures?**

This is an exploratory, AI-assisted textual comparison, not a legal ranking.
The main deliverables are static figures and the explanation below. Supporting
CSV tables preserve the evidence; no website is required or generated.

## What we did

1. Included all **184 PDFs** in the supplied Privacy Passages folder, extracting **2355 paragraphs** locally with R/pdftools.
2. Preserved excerpt PDF pages, reported original-source locations, and adjacent
   text. Removed editorial introductions/headings from the coded body.
3. Developed keyword rules using an earlier pilot; froze version 2 before
   examining six fresh PDFs. Keywords located candidates, not policy meanings.
4. Reviewed every extracted body, including no-hit paragraphs. The main assistant
   reviewed the six fresh PDFs; three AI reviewers reviewed disjoint batches
   covering the remainder. Each document received one AI review.
5. Applied three broad categories and 11 specific multi-label subcodes.
   Recorded treatment, wording force, actors, conditions, uncertainty, source
   function, and quotations. A paragraph may address several practices.
6. Checked all recorded quotations against their named extracted paragraphs;
   checked complete document review coverage, unique IDs, and frozen-rule hashes.
7. Counted each document once per category/subcode/treatment. Repeated mentions
   do not increase a document's count. Categories and treatments overlap.
8. Tested sensitivity to document function, shared wording, and excerpt length.
9. Re-coded previously positive training and retention paragraphs into atomic
   quoted provisions; distinguished actual directions from review questions and
   recorded mechanisms. This was a targeted AI refinement, not human validation.

**The topic-modeling pilot was exploratory and is not the method producing
these counts.** These results come from structured AI-assisted text review.

## Main findings

| Topic | Documents with explicit content | Percent | Uncertain only |
|---|---:|---:|---:|
| Model training / improvement | 52/184 | 28.3% | 6 |
| Sharing / secondary use | 78/184 | 42.4% | 19 |
| Retention / deletion | 37/184 | 20.1% | 4 |

**Sharing/secondary use is located most frequently; retention/deletion least
frequently.** This ordering persists in the tested sensitivity subsets.
These figures include warnings and vendor-review questions, not only rules.

## More specific findings

| Specific practice addressed | Documents | Percent of all documents |
|---|---:|---:|
| Model training / customization | 52 | 28.3% |
| Service improvement | 8 | 4.3% |
| Downstream disclosure | 63 | 34.2% |
| Sale of data | 9 | 4.9% |
| Advertising use | 15 | 8.2% |
| Profiling | 14 | 7.6% |
| Limits on purpose of use | 40 | 21.7% |
| Retention duration / limits | 29 | 15.8% |
| Deletion / return triggers | 9 | 4.9% |
| Deletion requests | 7 | 3.8% |
| Deletion procedures | 22 | 12.0% |

Explicit discussion of downstream disclosure and educational-purpose limits
is more common than discussion of sale, service improvement, or deletion requests.
**A deletion procedure is not necessarily a deletion right or a fixed deadline.**
Likewise, a retention-limit code can mean that a document asks vendors to specify
a duration, not that the document supplies a numerical duration itself.

## What differs substantively?

- **Training restrictions have different scopes and exceptions.** Philadelphia's
  excerpt reports no-training commitments for specified contracted tools
  (D145-B003), whereas Bellevue explicitly permits district authorization
  (D017-B021). Charleston refers to appropriate authorization without naming
  the authorizer in the passage (D037-B001). Do not read these as equivalent bans.
- **Purpose matters.** The Alabama template restricts new contractor-product
  training but includes prior-approval exceptions for district-specific
  development (D005-B011 and D005-B013). A template is not statewide adoption.
- **Deletion directions differ.** Rochester calls for awareness of periods and
  procedures (D156-B002); Bellevue requires explanation of deletion practices
  (D017-B021). These are not evidence of identical rights or timelines.

The [evidence table](reviewed_evidence.csv) contains quotations, source locations,
conditions, and surrounding text for these IDs. Original sources remain unverified.

## Are we specific enough?

**The three-category chart alone is not enough for a detailed comparison.**
Use the specific-practice chart, the treatment profiles, and the concrete
contrasts above together. They distinguish what is discussed from how it is treated.

The initial broad coding is **paragraph-level**, not a complete inventory of
individual legal provisions. A paragraph with several subcodes has one overall
treatment label. We therefore do **not** cross-tabulate that label into claims
such as 'nine policies ban selling data': that would falsely assign the same
treatment to every subcode in a mixed paragraph.

A targeted second pass now separates individual training and retention provisions,
including authorizers, deletion triggers, numerical timing, backups, and confirmation.
Its narrower scope and limits are explained below; it does not replace the
original broad counts or establish independently validated legal classifications.

## Targeted provision-level comparison

A second AI-assisted pass assessed **206 previously positive paragraph-category pairs** and recorded **200 atomic provisions**.
This pass revisited training/improvement and retention/deletion only. It split
mixed paragraphs into separately quoted directions, preserving data/tool scope,
exceptions, authorizing actor, triggers, timing, backup scope, and confirmation.
Paragraphs that only supplied context or remained uncertain were logged rather
than forced into a provision. The original broad coding was preserved.
Primary comparisons exclude hypothetical exercises, proposed/model clauses,
unclear-status language, and separately identified out-of-scope content takedowns.
These remain in the evidence table with explicit
context labels. Recommended guidance and reported commitments are included;
inclusion still does not establish adoption or enforceability.
Of 200 recorded provisions, 160 enter primary comparisons; 40 are retained
only as illustrative/proposed/unclear or out-of-scope context. This is a record count, not
a document count. See [context counts](provision_context_counts.csv).

### Directions versus review questions

See [direction-versus-review profiles](figures/provision_profiles.png) for a
simpler poster-ready view of the distinction.
The following document profiles are mutually exclusive within each topic.
A 'direction' can be recommended or mandatory; it does not imply adoption
or enforceability. A document can combine a direction with review questions.

| Topic | Direction only | Both direction and review | Review/transparency only | Other or excluded context | Total |
|---|---:|---:|---:|---:|---:|
| Training / improvement | 13 | 6 | 20 | 13 | 52 |
| Retention / deletion | 9 | 7 | 17 | 4 | 37 |

### Specific mechanisms

**[Provision mechanisms](figures/provision_mechanisms.png) is the recommended
main comparison figure.** Counts below use unique documents, not mentions.
Features overlap. The second column counts any qualifying wording, including
recommendations and descriptions; the third identifies the subset with mandatory
wording for that exact feature. Neither establishes legal authority.

| Explicit feature in targeted evidence | Documents | With mandatory wording | Reviewed topic documents |
|---|---:|---:|---:|
| Training: Restriction; no exception in quoted clause | 8 | 7 | 52 |
| Training: Exception: district authorization | 4 | 4 | 52 |
| Training: Exception: parent/guardian consent | 0 | 0 | 52 |
| Training: Exception: student consent | 0 | 0 | 52 |
| Training: Exception: consent, actor unspecified | 1 | 1 | 52 |
| Training: Exception: authorization, actor unspecified | 5 | 5 | 52 |
| Training: Other conditional use | 3 | 3 | 52 |
| Training: Permission without consent condition | 0 | 0 | 52 |
| Training: Review instruction or warning | 26 | 4 | 52 |
| Retention: Actual retention limit stated | 11 | 5 | 37 |
| Retention: Deletion/return direction stated | 6 | 3 | 37 |
| Retention: Deletion-request mechanism stated | 2 | 0 | 37 |
| Retention: Deletion tied to end of purpose/use | 3 | 0 | 37 |
| Retention: Deletion/return tied to contract end | 0 | 0 | 37 |
| Retention: Numerical retention/deletion time limit | 0 | 0 | 37 |
| Retention: Deletion explicitly includes backups | 0 | 0 | 37 |
| Retention: Explicit deletion confirmation | 0 | 0 | 37 |
| Retention: Review/transparency rather than deletion rule | 24 | 7 | 37 |

The targeted evidence contains numerical retention/deletion limits in **0 documents**, explicit backup inclusion in **0**, and deletion confirmation in **0**.
These counts exclude questions merely asking a vendor to specify a period or
deletion practice, hypothetical exercises, and proposed/model clauses.
Intimate-image content takedown deadlines are also excluded: removal of
content is not the same mechanism as deletion of retained student service data.
Numerical limits on unrelated records are not counted as
student-data deletion deadlines.

**Interpretation:** In the primary comparison, the excerpts more often
tell readers to inspect or understand vendor practices than spell out
specific deletion mechanisms. Training clauses also differ in who authorizes
exceptions. These are textual differences, not evidence of comparative
legal strength, compliance, or actual student outcomes.

### How to audit the finer findings

- [Atomic provisions](atomic_provisions.csv): exact quotation, treatment, force,
  actor, exception, timing, scope, source, and neighboring context for each record.
- [Feature-to-evidence map](provision_feature_evidence.csv): every chart bar
  linked to provisions, with an inclusion flag distinguishing illustrative,
  proposed/model, unclear-status, and out-of-scope records excluded from primary counts.
- [Feature counts](provision_feature_counts.csv): document counts and explicit
  denominators, including mandatory-wording subsets and sensitivity counts
  excluding template/curriculum/resource-summary documents; an all-context
  count separately shows how including illustrative/proposed language changes counts.
- [Assessment log](provision_assessments.csv): every originally positive
  paragraph-category pair accounted for, including exclusions and ambiguity.
- [Document profiles](provision_document_profiles.csv): mutually exclusive
  direction/review profiles behind the table above.

### Boundaries of this refinement

This is targeted re-coding of previously positive evidence, not an independent
human validation or a new full-corpus search. It cannot recover provisions
missed by the original review, including uncertain-only paragraphs. A zero is
not proof of absence from an excerpt, original policy, or jurisdiction.
The training 'no exception' bar describes the quoted clause, not an absolute
document-wide ban; other clauses or external law may qualify it. Authorizers
were recorded only where named, not inferred from passive 'authorization'.
The source-function caveats apply equally to these provisions: a proposed
contract or template can contain mandatory wording without being adopted.
Sharing/sale/advertising remain paragraph-level; no per-practice ban counts
are claimed for those topics. Written-consent requirements were not separately coded.

## Recommended visualizations

1. **[Provision mechanisms](figures/provision_mechanisms.png)**: main comparison;
   scope-specific training exceptions and concrete retention/deletion mechanisms.
2. **[Direction versus review](figures/provision_profiles.png)**: simpler summary
   using mutually exclusive document profiles; useful as a companion figure.
3. **[Specific practices](figures/specific_practices.png)**: overview; 11 practices.
4. **[Treatment profiles](figures/treatment_profiles.png)**: restrictions, conditional
   permissions, discussion/review, and other treatments by broad topic.
5. **[Sensitivity checks](figures/sensitivity.png)**: source/excerpt selection caveat.
6. [Broad coverage](figures/coverage.png): optional introductory overview.
7. [Coverage versus restrictions](figures/treatment.png): optional simpler treatment view.

Each figure also has a vector PDF in [figures/](figures/).
Treatment-profile counts overlap: one document may contain both restrictive
wording and conditional permission. Do not sum them or interpret a restrictive
paragraph as a document-wide ban.

## Quality and sensitivity

- Fresh sample: 6 PDFs / 81 paragraphs, with only 7 definite relevant
  paragraph-category pairs. All seven were retrieved, but sharing precision
  was 3/10. This small AI-reference check is not general accuracy validation.
- Full-body review found relevant content missed by frozen searches.
  See [corpus retrieval diagnostic](corpus_retrieval_diagnostic.csv) and
  [no-hit audit](no_hit_audit.csv). Counts use reviewed text, not only hits.
- Longer excerpts show higher coverage. For excerpts with at least 1,000 body
  characters, training/sharing/retention coverage is about 37.9%/53.8%/27.3%,
  versus 28.3%/42.4%/20.1% overall. This is descriptive, not a causal effect.
- Excluding template/curriculum/resource documents or collapsing high-similarity
  groups preserves the topic ordering. See [sensitivity table](sensitivity_checks.csv).
- Similarity flags use five-word-shingle Jaccard >= 0.70, not proof of shared
  authorship or exhaustive detection of common templates.
- One review used `descriptive` as a treatment; it was normalized to
  `discussion_or_review` with originals retained in [the normalization log](review_label_normalization.csv).

## Limitations and permitted conclusions

- No independent human annotation or inter-rater reliability was measured.
  Quotes matching text validates provenance, **not correctness of interpretation**.
- The corpus is a convenience collection of selected excerpts; original sources,
  dates, adoption, authenticity, and completeness have not been independently verified.
- One PDF is not one independent jurisdiction. Do not report these as percentages
  of states, districts, or all US policies.
- 'Not located' is not absence of legal protection. Other documents/laws may apply.
- Mandatory wording is not legal enforceability. We did not measure implementation
  or student outcomes and cannot rank which jurisdiction protects students best.
- AI review and source-function judgments may be inconsistent or mistaken.
  Disclose AI assistance and follow course requirements.

**Defensible conclusion:** The supplied excerpts differ both in which downstream
data practices they explicitly address and in the scope, conditions, and type
of direction they provide. Topic coverage alone does not establish equivalent safeguards.

## Reproducing the outputs

From the repository root, with R and jsonlite available:

```sh
Rscript test_passage_pilot.R
Rscript test_privacy_study.R
Rscript test_privacy_provisions.R
Rscript summarize_privacy_study.R privacy_study
```

Extraction additionally requires pdftools. See
[preparation script](../prepare_privacy_study.R) and
[review protocol](review_protocol.txt). Original review JSON, extracted
passages, source hashes, frozen rules, and CSV results are retained for audit.
Re-running summarization regenerates figures/tables/this README, not review JSON.
No websites are generated.
