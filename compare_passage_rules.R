# Usage: Rscript compare_passage_rules.R <pilot output directory>
source("passage_pilot.R")
args <- commandArgs(trailingOnly = TRUE)
if (!length(args)) stop("Supply pilot output directory.")
output <- normalizePath(args[1L], mustWork = TRUE)
passages <- read.csv(file.path(output, "pilot_passages.csv"), stringsAsFactors = FALSE)
reference <- read.csv(file.path(output, "provisional_full_read_reference.csv"),
                       stringsAsFactors = FALSE)
rules <- search_rules("v2")
candidates <- retrieve_candidates(passages, rules)
key <- function(id, category) paste(id, category, sep = "::")
indexes <- match(key(candidates$passage_id, candidates$category),
                 key(reference$passage_id, reference$category))
candidates$assistant_relevance <- reference$relevance[indexes]
candidates$assistant_notes <- reference$reference_notes[indexes]
write.csv(rules, file.path(output, "revised_search_rules_v2.csv"), row.names = FALSE)
write.csv(candidates, file.path(output, "candidate_evidence_v2.csv"), row.names = FALSE)
rows <- list()
for (split in c("development", "validation")) {
  for (category in rules$category) {
    r <- reference[reference$split == split & reference$category == category, ]
    predicted <- key(r$passage_id, r$category) %in%
      key(candidates$passage_id, candidates$category)
    positive <- r$relevance == "yes"
    certain <- r$relevance != "uncertain"
    tp <- sum(predicted & positive)
    fp <- sum(predicted & !positive & certain)
    fn <- sum(!predicted & positive)
    rows[[length(rows) + 1L]] <- data.frame(
      original_split = split, category = category, true_positive = tp,
      false_positive = fp, false_negative = fn,
      precision = if (tp + fp) tp / (tp + fp) else NA_real_,
      recall = if (tp + fn) tp / (tp + fn) else NA_real_,
      evaluation_status = "reused_sample_NOT_fresh_validation"
    )
  }
}
metrics <- do.call(rbind, rows)
write.csv(metrics, file.path(output, "revised_rules_in_sample_quality.csv"),
          row.names = FALSE, na = "")
writeLines(c(
  "v2 revision: explicit purpose limitations and indirect availability language added;",
  "model development/customization added; generic storage/keep/termination removed;",
  "duration and no-longer-needed retention phrases added.",
  "Rules were revised after all ten PDFs were read.",
  "Any improved metrics are in-sample debugging evidence, NOT new validation.",
  "Next evaluation requires a new unseen sample and independent reference review.",
  "Do not use keyword hits as policy judgments."
), file.path(output, "revision_v2_notes.txt"))
print(metrics, row.names = FALSE, digits = 3)
overview <- c(
  "START HERE: student privacy evidence-finding pilot",
  "",
  "Completed",
  "- Inventoried 184 local PDFs; retrieved evidence from only 10 sampled PDFs.",
  "- Read all 140 extracted pilot paragraphs, including paragraphs without hits.",
  "- Kept PDF pages, original-source labels, and neighboring context.",
  "- Used a frozen first rule set with five development and five validation PDFs.",
  "- Recorded assistant relevance labels and ambiguous cases, not automatic judgments.",
  "- Audited no-hit document/category pairs.",
  "- Visually checked Alabama page 2 and Springfield page 2 against extraction.",
  "- Verified all illustrative quotations against the extracted passages.",
  "",
  "Original direct-hit search: validation results",
  "Model training: 10 of 11 relevant paragraph/category pairs retrieved.",
  "Sharing/secondary use: 5 of 9 relevant pairs retrieved.",
  "Retention/deletion: 2 of 2 relevant pairs retrieved (very small denominator).",
  "These are measured against provisional assistant labels, not independent human gold.",
  "",
  "Revision after failure analysis",
  "Added indirect availability, purpose restrictions, and customization language.",
  "Removed generic storage and termination terms from retention retrieval.",
  "The revised rules retrieved all labeled relevant pairs in the old sample.",
  "Sharing precision remains about 44-45%: many hits need to be rejected.",
  "This improvement reuses reviewed data and is NOT fresh validation.",
  "",
  "Open these files",
  "candidate_evidence_v2.csv: revised candidate passages with source and context.",
  "illustrative_provisions_with_sources.csv: 11 separately coded examples.",
  "quality_report.txt: original search metrics and methodological limitations.",
  "revised_rules_in_sample_quality.csv: revised in-sample metrics.",
  "full_read_review_template.csv: unfilled form for independent teammate review.",
  "document_inventory_reviewed.csv: inventory with provisional pilot metadata.",
  "",
  "Quality decision",
  "Useful as an evidence finder, NOT ready for automatic policy classification.",
  "Next gate: freeze v2; test on fresh PDFs and obtain independent human review.",
  "Do not use these ten documents for collection-wide percentages or legal rankings.",
  "Templates, curriculum, and guidance must remain distinct from adopted policies.",
  "No full-corpus substantive coding or poster-ready findings have been produced."
)
writeLines(overview, file.path(output, "START_HERE.txt"))
