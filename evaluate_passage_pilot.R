# Usage: Rscript evaluate_passage_pilot.R <pilot output directory> [source directory]
args <- commandArgs(trailingOnly = TRUE)
if (!length(args)) stop("Supply the pilot output directory.")
output <- normalizePath(args[1L], mustWork = TRUE)
source_dir <- if (length(args) >= 2L) args[2L] else "."
read_table <- function(name) read.csv(file.path(output, name), stringsAsFactors = FALSE)
write_table <- function(x, name) write.csv(x, file.path(output, name),
                                          row.names = FALSE, na = "")
passages <- read_table("pilot_passages.csv")
candidates <- read_table("candidate_evidence.csv")
rules <- read_table("frozen_search_rules.csv")
frozen_hash <- readLines(file.path(output, "rules_md5.txt"))
stopifnot(identical(unname(tools::md5sum(file.path(output, "frozen_search_rules.csv"))),
                    frozen_hash))
annotations <- read.csv(file.path(source_dir, "passage_reference_labels.csv"),
                         stringsAsFactors = FALSE)
documents <- read.csv(file.path(source_dir, "passage_review_documents.csv"),
                       stringsAsFactors = FALSE)
stem <- sub("_Privacy_Passages[.]pdf$", "", passages$document)
stopifnot(setequal(unique(stem), documents$document_stem),
          all(passages$split == documents$split[match(stem, documents$document_stem)]))
block <- as.integer(sub(".*::b", "", passages$passage_id))
passage_key <- paste(stem, block, sep = "::")
annotation_key <- paste(annotations$document_stem, annotations$block, sep = "::")
stopifnot(all(annotation_key %in% passage_key),
          all(annotations$category %in% rules$category),
          all(annotations$relevance %in% c("yes", "no", "uncertain")),
          !anyDuplicated(paste(annotation_key, annotations$category)))
reference <- passages[rep(seq_len(nrow(passages)), each = nrow(rules)), ]
reference$category <- rep(rules$category, nrow(passages))
reference$relevance <- "no"
reference$reference_notes <- "Full-read review: no explicit in-scope content in this paragraph."
reference$reviewer <- "assistant_single_reviewer"
reference$reference_status <- "provisional_requires_independent_review"
reference_key <- paste(
  rep(passage_key, each = nrow(rules)), reference$category, sep = "::"
)
indexes <- match(paste(annotation_key, annotations$category, sep = "::"), reference_key)
reference$relevance[indexes] <- annotations$relevance
reference$reference_notes[indexes] <- annotations$notes
pair_key <- function(id, category) paste(id, category, sep = "::")
reference$retrieved <- pair_key(reference$passage_id, reference$category) %in%
  pair_key(candidates$passage_id, candidates$category)

# Context expansion is reported separately; it was not the frozen direct-hit method.
reference$context_retrieved <- reference$retrieved
for (i in seq_len(nrow(reference))) {
  neighbors <- reference$document == reference$document[i] &
    reference$category == reference$category[i] &
    abs(as.integer(sub(".*::b", "", reference$passage_id)) -
          as.integer(sub(".*::b", "", reference$passage_id[i]))) <= 1L
  reference$context_retrieved[i] <- any(reference$retrieved[neighbors])
}
metrics <- list()
for (split in c("development", "validation")) {
  for (category in rules$category) {
    r <- reference[reference$split == split & reference$category == category, ]
    for (method in c("retrieved", "context_retrieved")) {
      certain <- r$relevance != "uncertain"
      positive <- r$relevance == "yes"
      predicted <- r[[method]]
      tp <- sum(predicted & positive)
      fp <- sum(predicted & !positive & certain)
      fn <- sum(!predicted & positive)
      metrics[[length(metrics) + 1L]] <- data.frame(
        split = split, category = category, method = method,
        true_positive = tp, false_positive = fp, false_negative = fn,
        uncertain_pairs = sum(!certain),
        precision = if (tp + fp > 0L) tp / (tp + fp) else NA_real_,
        recall = if (tp + fn > 0L) tp / (tp + fn) else NA_real_
      )
    }
  }
}
metrics <- do.call(rbind, metrics)
write_table(reference, "provisional_full_read_reference.csv")
write_table(metrics, "retrieval_quality.csv")
write_table(reference[reference$relevance == "yes" & !reference$retrieved, ],
            "missed_passages.csv")
write_table(reference[reference$relevance == "no" & reference$retrieved, ],
            "false_positive_passages.csv")
write_table(reference[reference$relevance == "uncertain", ],
            "ambiguous_passages.csv")
review_indexes <- match(pair_key(candidates$passage_id, candidates$category),
                         pair_key(reference$passage_id, reference$category))
candidates$review_relevance <- reference$relevance[review_indexes]
candidates$review_notes <- reference$reference_notes[review_indexes]
write_table(candidates, "candidate_evidence_assistant_review.csv")
coverage <- read_table("retrieval_coverage.csv")
coverage$reference_relevant_paragraphs <- mapply(function(d, c) {
  sum(reference$document == d & reference$category == c & reference$relevance == "yes")
}, coverage$document, coverage$category)
coverage$reference_uncertain_paragraphs <- mapply(function(d, c) {
  sum(reference$document == d & reference$category == c & reference$relevance == "uncertain")
}, coverage$document, coverage$category)
coverage$no_hit_audit_result <- ifelse(
  coverage$candidate_count > 0L, "not_a_no_hit_pair",
  ifelse(coverage$reference_relevant_paragraphs > 0L,
         "missed_content_on_full_read",
         ifelse(coverage$reference_uncertain_paragraphs > 0L,
                "ambiguous_on_full_read", "no_explicit_content_found_on_full_read"))
)
write_table(coverage, "audited_retrieval_coverage.csv")
inventory <- read_table("document_inventory.csv")
metadata_indexes <- match(sub("_Privacy_Passages[.]pdf$", "", inventory$document),
                          documents$document_stem)
for (field in c("jurisdiction", "government_level", "source_type", "source_date")) {
  matched <- which(!is.na(metadata_indexes))
  inventory[[field]][matched] <- documents[[field]][metadata_indexes[matched]]
}
inventory$metadata_basis <- ifelse(is.na(metadata_indexes), "not_reviewed",
                                    "excerpt_compilation_only_unverified")
write_table(inventory, "document_inventory_reviewed.csv")
copy_files <- c("passage_reference_labels.csv", "passage_review_documents.csv",
                "passage_codebook.txt", "passage_provision_examples.csv",
                "passage_pilot_instructions.txt")
for (name in copy_files) {
  if (!file.copy(file.path(source_dir, name), file.path(output, name), overwrite = TRUE)) {
    stop("Unable to archive ", name)
  }
}
examples <- read.csv(file.path(source_dir, "passage_provision_examples.csv"),
                      stringsAsFactors = FALSE)
example_indexes <- match(paste(examples$document_stem, examples$block, sep = "::"),
                          passage_key)
stopifnot(!anyNA(example_indexes))
normalize_quote <- function(x) gsub("[[:space:]]+", " ", trimws(x))
for (i in seq_len(nrow(examples))) {
  if (!grepl(normalize_quote(examples$quotation[i]),
             normalize_quote(passages$text[example_indexes[i]]), fixed = TRUE)) {
    stop("Illustrative quotation does not match extracted text: example ", i)
  }
}
examples$document <- passages$document[example_indexes]
examples$pdf_page <- passages$pdf_page[example_indexes]
examples$source_location <- passages$source_location[example_indexes]
examples$full_passage <- passages$text[example_indexes]
examples$previous_context <- passages$previous_context[example_indexes]
examples$next_context <- passages$next_context[example_indexes]
examples$review_status <- "assistant_example_requires_independent_review"
write_table(examples, "illustrative_provisions_with_sources.csv")
report <- c(
  "Student privacy passage pilot: quality report",
  "",
  sprintf("PDFs inventoried: %d; sampled: %d; reviewed paragraphs: %d.",
          nrow(inventory), length(unique(passages$document)), nrow(passages)),
  "Five development and five held-out PDFs; sampling seed 20261016.",
  "The held-out PDFs were not used to revise the frozen direct-hit rules.",
  "Reference: assistant full-read review of extracted text, NOT independent human gold.",
  "Metrics count paragraph-category pairs, not provisions, jurisdictions, or protection strength.",
  "Uncertain reference judgments are excluded from precision/recall denominators.",
  "",
  capture.output(print(metrics, row.names = FALSE, digits = 3)),
  "",
  "Interpretation",
  "Direct lexical matches miss paraphrases and context-dependent provisions.",
  "Context expansion (+/- one paragraph) is a post-review sensitivity analysis:",
  "it is not fresh held-out evidence and can add many irrelevant passages.",
  "Staff training, generic storage, and termination of employment/contracts are false hits.",
  "No-hit document/category pairs were checked against full-read reference labels.",
  "No-hit success does not establish complete retrieval within documents with some hits.",
  "No substantive policy ranking or full-corpus protection counts have been generated.",
  "",
  "Decision: NOT READY for unattended corpus-wide classification or poster claims.",
  "Next: independent teammate annotation; visual extraction/source checks;",
  "revise contextual retrieval on development data; evaluate on fresh unseen PDFs.",
  "Retain a human verification stage, including exceptions and neighboring passages.",
  "A template, curriculum, or resource summary is not an adopted operative policy.",
  "Inventory metadata is provisional; dates/URLs absent from excerpts are left blank.",
  "Only exact text repetition is flagged; near-template duplication remains unchecked.",
  "Candidate substantive fields remain blank; illustrative_provisions_with_sources.csv",
  "contains a small set of separately coded assistant examples, not exhaustive results."
)
writeLines(report, file.path(output, "quality_report.txt"))
print(metrics, row.names = FALSE, digits = 3)
cat("\nQuality report saved to", file.path(output, "quality_report.txt"), "\n")
