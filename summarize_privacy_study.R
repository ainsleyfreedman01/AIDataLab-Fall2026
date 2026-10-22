# Usage: Rscript summarize_privacy_study.R [study directory]
source("passage_pilot.R")
args <- commandArgs(trailingOnly = TRUE)
out <- if (length(args)) args[1L] else "privacy_study"
if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Missing jsonlite.")
out <- normalizePath(out, mustWork = TRUE)
read_table <- function(name) read.csv(file.path(out, name), stringsAsFactors = FALSE)
write_table <- function(x, name) write.csv(x, file.path(out, name), row.names = FALSE, na = "")
inventory <- read_table("inventory.csv")
passages <- read_table("passages.csv")
rules <- read_table("frozen_rules_v2.csv")
stopifnot(identical(unname(tools::md5sum(file.path(out, "frozen_rules_v2.csv"))),
                    readLines(file.path(out, "rules_md5.txt"))))
categories <- c("model_training", "sharing_secondary_use", "retention_deletion")
labels <- c("Model training / improvement", "Sharing / secondary use", "Retention / deletion")
names(labels) <- categories
functions <- c("guidance", "operative_text", "template", "curriculum",
               "resource_summary", "mixed", "unknown")
files <- file.path(out, "review", paste0(c("fresh", "batch1", "batch2", "batch3"),
                                        "_review.json"))
if (!all(file.exists(files))) stop("Review incomplete: ", paste(files[!file.exists(files)], collapse = ", "))
reviewed_documents <- list()
evidence <- list()
for (f in files) {
  review <- jsonlite::fromJSON(f, simplifyVector = FALSE)
  for (d in review$documents) {
    required <- c("doc_id", "review_status", "source_function", "government_level", "notes")
    if (!all(required %in% names(d))) stop("Missing document fields in ", f)
    reviewed_documents[[length(reviewed_documents) + 1L]] <- as.data.frame(d[required],
                                                                         stringsAsFactors = FALSE)
  }
  for (e in review$evidence) {
    required <- c("evidence_id", "category", "relevance", "subcodes", "treatment",
                  "force", "actor", "conditions", "source_function", "quotation", "notes")
    if (!all(required %in% names(e))) stop("Missing evidence fields in ", f)
    e$subcodes <- paste(unlist(e$subcodes), collapse = ";")
    evidence[[length(evidence) + 1L]] <- as.data.frame(e[required], stringsAsFactors = FALSE)
  }
}
documents <- do.call(rbind, reviewed_documents)
evidence <- do.call(rbind, evidence)
evidence$original_treatment_label <- evidence$treatment
# One review used force terminology for non-prescriptive discussion.
evidence$treatment[evidence$treatment == "descriptive"] <- "discussion_or_review"
write_table(evidence[evidence$original_treatment_label != evidence$treatment, ],
            "review_label_normalization.csv")
stopifnot(!anyDuplicated(documents$doc_id),
          setequal(documents$doc_id, inventory$doc_id),
          all(documents$review_status == "complete"),
          all(documents$source_function %in% functions),
          all(documents$government_level %in% c("state", "district", "other", "unknown")),
          all(evidence$source_function %in% functions),
          all(evidence$category %in% categories),
          all(evidence$relevance %in% c("yes", "uncertain")),
          !anyDuplicated(paste(evidence$evidence_id, evidence$category)))
stopifnot(all(evidence$treatment %in% c("restricts", "conditional_permission", "permits",
                                       "discussion_or_review", "mixed", "unclear")),
          all(evidence$force %in% c("mandatory_wording", "recommendation", "descriptive",
                                   "mixed", "unclear")))
allowed_subcodes <- c("training_reuse", "service_improvement", "disclosure", "sale",
                       "advertising", "profiling", "purpose_limitation", "retention_limit",
                       "deletion_trigger", "deletion_request", "deletion_procedure")
stopifnot(all(unlist(strsplit(evidence$subcodes, ";", fixed = TRUE)) %in% allowed_subcodes))
ix <- match(evidence$evidence_id, passages$evidence_id)
if (anyNA(ix)) stop("Unknown evidence identifiers.")
normalize_quote <- function(x) gsub("[[:space:]]+", " ", trimws(x))
quote_ok <- vapply(seq_len(nrow(evidence)), function(i) {
  nzchar(trimws(evidence$quotation[i])) &&
    grepl(normalize_quote(evidence$quotation[i]),
          normalize_quote(passages$text[ix[i]]), fixed = TRUE)
}, logical(1))
if (!all(quote_ok)) {
  write_table(evidence[!quote_ok, ], "quotation_errors.csv")
  stop("Quotation validation failed; inspect quotation_errors.csv.")
}
evidence <- cbind(evidence, passages[ix, c("doc_id", "document", "pdf_page",
                                          "source_location", "section", "text",
                                          "previous_context", "next_context")])
evidence$original_source_verification <- "not_verified_against_original_source"
evidence$review_provenance <- "single_AI_review_not_independent_human_annotation"
write_table(evidence, "reviewed_evidence.csv")
documents <- cbind(inventory, documents[match(inventory$doc_id, documents$doc_id),
                                        setdiff(names(documents), "doc_id")])
write_table(documents, "reviewed_documents.csv")
source("summarize_privacy_provisions.R")
targeted <- summarize_privacy_provisions(out, evidence, documents)
grid <- expand.grid(doc_id = documents$doc_id, category = categories,
                    stringsAsFactors = FALSE)
key <- function(id, category) paste(id, category, sep = "::")
positive_keys <- key(evidence$doc_id[evidence$relevance == "yes"],
                     evidence$category[evidence$relevance == "yes"])
uncertain_keys <- key(evidence$doc_id[evidence$relevance == "uncertain"],
                      evidence$category[evidence$relevance == "uncertain"])
grid$explicit_content_found <- key(grid$doc_id, grid$category) %in% positive_keys
grid$uncertain_content_found <- key(grid$doc_id, grid$category) %in% uncertain_keys
grid$status <- ifelse(grid$explicit_content_found, "explicit_content_found",
                       ifelse(grid$uncertain_content_found, "uncertain_only",
                              "not_located_in_reviewed_excerpt"))
grid$restrictive_or_conditional_wording <- key(grid$doc_id, grid$category) %in%
  key(evidence$doc_id[evidence$relevance == "yes" &
                        evidence$treatment %in% c("restricts", "conditional_permission")],
      evidence$category[evidence$relevance == "yes" &
                          evidence$treatment %in% c("restricts", "conditional_permission")])
# Mixed paragraphs are not silently counted as prohibitions.
grid$nonresource_content_found <- key(grid$doc_id, grid$category) %in%
  key(evidence$doc_id[evidence$relevance == "yes" &
                        !evidence$source_function %in% c("resource_summary", "curriculum")],
      evidence$category[evidence$relevance == "yes" &
                          !evidence$source_function %in% c("resource_summary", "curriculum")])
write_table(grid, "document_category_matrix.csv")
coverage <- do.call(rbind, lapply(categories, function(c) {
  g <- grid[grid$category == c, ]
  data.frame(category = c, documents = nrow(g),
             explicit_content_found = sum(g$explicit_content_found),
             uncertain_only = sum(g$status == "uncertain_only"),
             not_located = sum(g$status == "not_located_in_reviewed_excerpt"),
             percent_with_content = 100 * mean(g$explicit_content_found),
             restrictive_or_conditional_wording = sum(g$restrictive_or_conditional_wording),
             nonresource_content = sum(g$nonresource_content_found))
}))
write_table(coverage, "coverage_summary.csv")

# Compare frozen retrieval with full-read labels on the fresh sample only.
predicted <- retrieve_candidates(passages, rules)
fresh <- passages[passages$doc_id %in% documents$doc_id[documents$fresh_quality_sample], ]
metrics <- list()
for (c in categories) {
  keys <- key(fresh$evidence_id, c)
  positive <- keys %in% key(evidence$evidence_id[evidence$relevance == "yes"],
                            evidence$category[evidence$relevance == "yes"])
  uncertain <- keys %in% key(evidence$evidence_id[evidence$relevance == "uncertain"],
                             evidence$category[evidence$relevance == "uncertain"])
  retrieved <- keys %in% key(predicted$evidence_id, predicted$category)
  tp <- sum(positive & retrieved)
  fp <- sum(!positive & !uncertain & retrieved)
  fn <- sum(positive & !retrieved)
  metrics[[length(metrics) + 1L]] <- data.frame(
    category = c, sample_documents = length(unique(fresh$doc_id)),
    sampled_paragraphs = nrow(fresh), true_positive = tp, false_positive = fp,
    false_negative = fn, uncertain_pairs = sum(uncertain),
    precision = if (tp + fp) tp / (tp + fp) else NA_real_,
    recall = if (tp + fn) tp / (tp + fn) else NA_real_,
    reference = "provisional_AI_full_read_labels_not_human_gold")
}
metrics <- do.call(rbind, metrics)
write_table(metrics, "fresh_sample_retrieval_quality.csv")
all_retrieval <- do.call(rbind, lapply(categories, function(c) {
  positive_ids <- evidence$evidence_id[evidence$category == c & evidence$relevance == "yes"]
  uncertain_ids <- evidence$evidence_id[evidence$category == c & evidence$relevance == "uncertain"]
  hit_ids <- predicted$evidence_id[predicted$category == c]
  tp <- sum(positive_ids %in% hit_ids)
  fp <- sum(!hit_ids %in% c(positive_ids, uncertain_ids))
  fn <- sum(!positive_ids %in% hit_ids)
  data.frame(category = c, relevant_pairs = length(positive_ids),
             retrieved_relevant = tp, missed_relevant = fn,
             irrelevant_candidates = fp,
             precision = if (tp + fp) tp / (tp + fp) else NA_real_,
             recall = if (tp + fn) tp / (tp + fn) else NA_real_,
             interpretation = "corpus_diagnostic_not_independent_validation")
}))
write_table(all_retrieval, "corpus_retrieval_diagnostic.csv")
evidence$retrieved_by_frozen_rules <- key(evidence$evidence_id, evidence$category) %in%
  key(predicted$evidence_id, predicted$category)
write_table(evidence, "reviewed_evidence.csv")
write_table(evidence[evidence$relevance == "yes" & !evidence$retrieved_by_frozen_rules, ],
            "relevant_evidence_missed_by_search.csv")
audit <- grid
audit$candidate_count <- mapply(function(d, c) {
  sum(predicted$doc_id == d & predicted$category == c)
}, audit$doc_id, audit$category)
audit$no_hit_false_negative <- audit$candidate_count == 0L & audit$explicit_content_found
write_table(audit, "no_hit_audit.csv")

# Flag shared wording; a sensitivity check, not proof of common authorship.
bodies <- vapply(documents$doc_id, function(id) {
  paste(passages$text[passages$doc_id == id], collapse = " ")
}, character(1))
shingles <- lapply(bodies, function(body) {
  words <- strsplit(gsub("[^a-z0-9 ]", " ", normalize_search_text(body)), " +")[[1L]]
  words <- words[nzchar(words)]
  if (length(words) < 50L) return(character())
  unique(vapply(seq_len(length(words) - 4L), function(i) {
    paste(words[i:(i + 4L)], collapse = " ")
  }, character(1)))
})
similar <- list()
for (i in seq_len(nrow(documents) - 1L)) for (j in (i + 1L):nrow(documents)) {
  if (!length(shingles[[i]]) || !length(shingles[[j]])) next
  overlap <- length(intersect(shingles[[i]], shingles[[j]])) /
    length(union(shingles[[i]], shingles[[j]]))
  if (overlap >= 0.7) similar[[length(similar) + 1L]] <- data.frame(
    doc_id_a = documents$doc_id[i], doc_id_b = documents$doc_id[j],
    five_word_shingle_jaccard = overlap)
}
pairs <- if (length(similar)) do.call(rbind, similar) else
  data.frame(doc_id_a = character(), doc_id_b = character(),
             five_word_shingle_jaccard = numeric())
write_table(pairs, "high_text_similarity_pairs.csv")
groups <- seq_len(nrow(documents))
if (nrow(pairs)) for (i in seq_len(nrow(pairs))) {
  a <- match(pairs$doc_id_a[i], documents$doc_id)
  b <- match(pairs$doc_id_b[i], documents$doc_id)
  groups[groups == groups[b]] <- groups[a]
}
keep <- !duplicated(groups)
documents$similarity_group <- groups
documents$kept_for_similarity_sensitivity <- keep
write_table(documents, "reviewed_documents.csv")
subsets <- list(
  all_documents = documents$doc_id,
  excluding_template_curriculum_resource_documents =
    documents$doc_id[!documents$source_function %in% c("template", "curriculum", "resource_summary")],
  one_document_per_high_similarity_group = documents$doc_id[keep],
  excerpts_at_least_1000_body_characters =
    documents$doc_id[documents$body_characters >= 1000L]
)
sensitivities <- do.call(rbind, lapply(names(subsets), function(s) {
  do.call(rbind, lapply(categories, function(c) {
    g <- grid[grid$doc_id %in% subsets[[s]] & grid$category == c, ]
    data.frame(subset = s, category = c, documents = nrow(g),
               content_found = sum(g$explicit_content_found),
               percentage = if (nrow(g)) 100 * mean(g$explicit_content_found) else NA_real_)
  }))
}))
write_table(sensitivities, "sensitivity_checks.csv")
source_counts <- as.data.frame(table(documents$source_function))
names(source_counts) <- c("source_function", "documents")
write_table(source_counts, "source_function_counts.csv")
subcodes <- do.call(rbind, lapply(allowed_subcodes, function(code) {
  matching <- evidence$relevance == "yes" &
    vapply(strsplit(evidence$subcodes, ";", fixed = TRUE),
           function(x) code %in% x, logical(1))
  data.frame(subcode = code, documents = length(unique(evidence$doc_id[matching])))
}))
write_table(subcodes, "subcode_coverage.csv")
subcode_labels <- c(
  training_reuse = "Model training / customization",
  service_improvement = "Service improvement",
  disclosure = "Downstream disclosure",
  sale = "Sale of data",
  advertising = "Advertising use",
  profiling = "Profiling",
  purpose_limitation = "Limits on purpose of use",
  retention_limit = "Retention duration / limits",
  deletion_trigger = "Deletion / return triggers",
  deletion_request = "Deletion requests",
  deletion_procedure = "Deletion procedures"
)
subcodes$label <- unname(subcode_labels[subcodes$subcode])
subcodes$percent_of_all_documents <- 100 * subcodes$documents / nrow(documents)
write_table(subcodes, "subcode_coverage.csv")
treatments <- c("restricts", "conditional_permission", "discussion_or_review",
                "permits", "mixed", "unclear")
treatment_labels <- c("Restrictive wording", "Conditional permission", "Discussion / review",
                       "Permission", "Mixed paragraph", "Unclear")
profiles <- do.call(rbind, lapply(categories, function(c) {
  do.call(rbind, lapply(treatments, function(t) {
    matching <- evidence$relevance == "yes" & evidence$category == c &
      evidence$treatment == t
    data.frame(category = c, treatment = t,
               documents = length(unique(evidence$doc_id[matching])))
  }))
}))
write_table(profiles, "treatment_profiles.csv")

dir.create(file.path(out, "figures"), showWarnings = FALSE)
colors <- c("#33658A", "#E3A857", "#D9DEE3")
draw_coverage <- function() {
  par(mar = c(7, 14, 4, 2))
  counts <- t(as.matrix(coverage[, c("explicit_content_found", "uncertain_only", "not_located")]))
  positions <- barplot(counts, horiz = TRUE, axisnames = FALSE,
          col = colors, border = NA, xlim = c(0, nrow(documents)), cex.names = 0.85,
          xlab = "Number of excerpt documents", main = "Explicit topic coverage in reviewed excerpts")
  axis(2, at = positions, labels = unname(labels[coverage$category]), las = 1,
       tick = FALSE, cex.axis = 0.85, gap.axis = -1)
  legend("bottom", inset = c(0, -0.3), xpd = NA, horiz = TRUE,
         legend = c("Explicit content found", "Uncertain only", "Not located"),
         fill = colors, bty = "n", cex = 0.75)
}
draw_treatment <- function() {
  par(mar = c(7, 14, 4, 2))
  counts <- rbind(coverage$explicit_content_found,
                   coverage$restrictive_or_conditional_wording)
  positions <- barplot(counts, beside = TRUE, horiz = TRUE, axisnames = FALSE,
          col = c("#33658A", "#43856B"),
          border = NA, cex.names = 0.85, xlab = "Documents (overlapping measures)",
          main = "Discussion is not the same as a restriction")
  axis(2, at = colMeans(positions), labels = unname(labels[coverage$category]),
       las = 1, tick = FALSE, cex.axis = 0.85, gap.axis = -1)
  legend("bottom", inset = c(0, -0.3), xpd = NA, horiz = TRUE,
         legend = c("Any explicit content", "Restrictive / conditional wording"),
         fill = c("#33658A", "#43856B"), bty = "n", cex = 0.7)
}
draw_sensitivity <- function() {
  par(mar = c(8, 14, 4, 2))
  matrix <- sapply(names(subsets), function(s) sensitivities$percentage[sensitivities$subset == s])
  positions <- barplot(t(matrix), beside = TRUE, horiz = TRUE, axisnames = FALSE,
          border = NA,
          col = c("#33658A", "#43856B", "#E3A857", "#926AA6"),
          cex.names = 0.85, xlab = "Percent of documents in each subset",
          main = "Sensitivity to source mix, overlap, and excerpt length")
  axis(2, at = colMeans(positions), labels = unname(labels), las = 1,
       tick = FALSE, cex.axis = 0.85, gap.axis = -1)
  legend("bottom", inset = c(0, -0.3), xpd = NA, ncol = 2L,
         legend = c("All", "Exclude template/curriculum/resource",
                                    "One per similarity group", "At least 1,000 body characters"),
         fill = c("#33658A", "#43856B", "#E3A857", "#926AA6"), bty = "n", cex = 0.6)
}
draw_specific_practices <- function() {
  par(mar = c(6, 16, 4, 3))
  rows <- rev(seq_len(nrow(subcodes)))
  positions <- barplot(subcodes$documents[rows], horiz = TRUE, axisnames = FALSE,
                       axes = FALSE,
                       col = rev(c(rep("#33658A", 2), rep("#43856B", 5),
                                   rep("#926AA6", 4))), border = NA,
                       xlim = c(0, max(1, subcodes$documents) * 1.2),
                       xlab = sprintf("Documents with explicit discussion (out of %d)", nrow(documents)),
                       main = "Which specific data practices are addressed?")
  axis(2, at = positions, labels = subcodes$label[rows], las = 1, tick = FALSE,
       cex.axis = 0.75, gap.axis = -1)
  axis(1, at = pretty(c(0, max(1, subcodes$documents) * 1.2), n = 5))
  text(subcodes$documents[rows], positions,
       labels = subcodes$documents[rows], pos = 4, cex = 0.75)
  mtext("Multi-label coverage; discussion does not necessarily establish a safeguard.",
        side = 1, line = 4, cex = 0.7)
}
draw_treatment_profiles <- function() {
  par(mar = c(8, 14, 4, 3))
  matrix <- matrix(profiles$documents, nrow = length(treatments))
  positions <- barplot(matrix, beside = TRUE, horiz = TRUE, axisnames = FALSE,
                       col = c("#33658A", "#43856B", "#E3A857", "#926AA6",
                               "#A65E5E", "#999999"), border = NA,
                       main = "How do documents address each broad topic?",
                       xlab = "Documents with at least one paragraph of this treatment")
  axis(2, at = colMeans(positions), labels = unname(labels), las = 1,
       tick = FALSE, cex.axis = 0.8, gap.axis = -1)
  legend("bottom", inset = c(0, -0.32), xpd = NA, ncol = 3,
         legend = treatment_labels,
         fill = c("#33658A", "#43856B", "#E3A857", "#926AA6", "#A65E5E", "#999999"),
         bty = "n", cex = 0.65)
  mtext("Treatments overlap within documents; counts must not be summed.",
        side = 1, line = 6.5, cex = 0.65)
}
for (name in c("coverage", "treatment", "sensitivity", "specific_practices",
               "treatment_profiles")) {
  draw <- get(paste0("draw_", name))
  png(file.path(out, "figures", paste0(name, ".png")), width = 1800, height = 1050, res = 160)
  draw()
  dev.off()
  pdf(file.path(out, "figures", paste0(name, ".pdf")), width = 11.25, height = 6.56)
  draw()
  dev.off()
}

format_stat <- function(c) {
  r <- coverage[coverage$category == c, ]
  sprintf("%d/%d (%.1f%%)", r$explicit_content_found, r$documents, r$percent_with_content)
}
methods <- c(
  "AI-assisted comparative analysis of student-privacy excerpt documents",
  "",
  "Research question: How explicitly do K-12 AI excerpts address model training,",
  "secondary uses, and retention/deletion of student data?",
  "",
  sprintf("Corpus: all %d PDFs present in the supplied Privacy Passages folder.", nrow(documents)),
  "Convenience collection of selected excerpts, not a representative sample of US policy.",
  "One PDF is the counting unit; multiple documents can represent one jurisdiction.",
  "No policy text from the CSV was used.",
  "",
  "Method",
  "Page-preserving local PDF extraction; editorial introductions and source headings",
  "excluded from coded body. Original extracted pages retained for auditing.",
  "Frozen keyword rules v2 identify candidates but do not assign policy meaning.",
  "The assistant fully reviewed six fresh sampled PDFs; three AI reviewers each",
  "reviewed a disjoint body-text batch. Each document received one AI review.",
  "Because only seven definite relevant pairs occurred in the fresh sample, the",
  "study did not rely on that small retrieval test alone: all extracted bodies",
  "were reviewed, including no-hit paragraphs.",
  "Reviews used body text without retrieval flags. No independent human annotation",
  "or inter-rater reliability has been measured.",
  "Relevance and treatment coded at paragraph-category level; mixed paragraphs",
  "retained as mixed rather than simplified into a single prohibition.",
  "A targeted second AI pass split previously positive training and retention",
  "paragraphs into atomic quoted provisions. This is refinement, not independent",
  "validation. It excludes previously uncertain/negative evidence and cannot",
  "establish exhaustive absence. Original broad coding remains unchanged.",
  "All yes/uncertain evidence includes a quote checked against the named paragraph.",
  "Whitespace is normalized for quote matching; this is not original-source verification.",
  "Document-category presence is counted once; uncertain-only cases shown separately.",
  "Source function and mandatory language do not establish legal enforceability.",
  "",
  "Quality checks",
  "Fresh six-PDF retrieval evaluation against provisional assistant full-read labels.",
  "Every document/category no-hit compared with full-read evidence.",
  "Frozen rule hash, unique document IDs, full review coverage, and quotes checked.",
  "High shared-text similarity flagged with five-word-shingle Jaccard >=0.70",
  "for bodies with at least 50 words; this does not establish shared authorship.",
  "Sensitivity analyses exclude template/curriculum/resource documents, keep one",
  "document per connected similarity group, and restrict to >=1,000 body characters.",
  "",
  "Limits",
  "AI coding may miss or misinterpret provisions; negative labels are provisional.",
  "Excerpt selection and extraction can omit relevant context. Not located does not",
  "mean the original policy or jurisdiction lacks protection.",
  "Original source authenticity, currency, completeness, and adoption unverified.",
  "No causal, population-representative, compliance, legal-quality, or outcome claims.",
  "No significance tests: documents are heterogeneous and not independent jurisdictions.",
  "Any poster must disclose AI assistance and follow course requirements.",
  "Independent review and original-source checks are still recommended before submission."
)
writeLines(methods, file.path(out, "methods_and_limitations.txt"))
summary <- c(
  "RESULTS: exploratory AI-assisted analysis, not a legally verified policy audit",
  "",
  sprintf("Reviewed: %d PDFs; %d extracted paragraphs.", nrow(documents), nrow(passages)),
  sprintf("Evidence: %d relevant and %d uncertain paragraph-category pairs.",
          sum(evidence$relevance == "yes"), sum(evidence$relevance == "uncertain")),
  "",
  paste(unname(labels), vapply(categories, format_stat, character(1)), sep = ": "),
  "",
  "Interpretation",
  "Sharing/secondary use appears in more supplied excerpts than model training",
  "or retention/deletion. This ordering persists in the tested sensitivity subsets.",
  "Coverage is higher in longer excerpts, so document length/selection affects",
  "the chance of locating explicit content; do not interpret silence as weaker law.",
  "Restrictions, conditional permissions, warnings, and review questions coexist.",
  "The same topic appearing in two documents does not establish equal protections.",
  "",
  "Counts indicate explicit treatment, including warnings and review questions;",
  "they do not measure protection strength or actual implementation.",
  "",
  sprintf("Targeted refinement assessed %d positive training/retention paragraph-category pairs and recorded %d atomic provisions.",
          nrow(targeted$assessments), nrow(targeted$provisions)),
  "Use provision_feature_counts.csv for specific mechanisms and README.md for",
  "direction-versus-review profiles. Refinement is not independent validation;",
  "original broad counts are preserved and sharing remains paragraph-level.",
  "",
  "Fresh sample keyword-retrieval quality (AI reference, not human gold):",
  capture.output(print(metrics, row.names = FALSE, digits = 3)),
  "",
  sprintf("Document/category no-hit cases with relevant content on full read: %d.",
          sum(audit$no_hit_false_negative)),
  sprintf("High shared-text-similarity pairs flagged: %d.", nrow(pairs)),
  "",
  "Use coverage_summary.csv for headline counts; reviewed_evidence.csv for",
  "quotations and exceptions; sensitivity_checks.csv before interpreting patterns.",
  "Do not treat source-function groups as confirmed legal-status groups.",
  "",
  "Submission readiness: exploratory draft complete; human/original-source validation",
  "not complete. No inter-rater agreement or validated legal classification claimed."
)
writeLines(summary, file.path(out, "FINDINGS.txt"))
ranked <- coverage[order(coverage$explicit_content_found, decreasing = TRUE), ]
abstract <- c(
  "DRAFT ABSTRACT",
  "",
  "Student-facing artificial intelligence raises questions about downstream uses",
  "and retention of educational data. This exploratory study examines how explicitly",
  "a supplied collection of K-12 AI privacy excerpts addresses model training,",
  "sharing/secondary use, and retention/deletion.",
  sprintf("We locally extracted %d PDF excerpt documents and %d text paragraphs.",
          nrow(documents), nrow(passages)),
  "Frozen lexical searches were evaluated on six fresh documents against provisional",
  "AI full-read labels. Because the fresh test contained few relevant cases, all",
  "extracted document bodies were also AI-reviewed without retrieval flags.",
  "Coding retained conditions, source functions, and uncertain interpretations.",
  "Supporting quotations were checked against their named extracted paragraphs.",
  sprintf("A targeted second AI pass split %d previously positive training/retention paragraphs into %d atomic provisions,",
          nrow(targeted$assessments), nrow(targeted$provisions)),
  "separating stated directions from vendor-review questions and recording named",
  "authorizers, deletion triggers, timing, backup scope, and deletion confirmation.",
  "This refinement was not independent validation or a new exhaustive search.",
  paste(unname(labels), vapply(categories, format_stat, character(1)), sep = ": "),
  sprintf("The most frequently located topic was %s; the least was %s.",
          tolower(labels[ranked$category[1L]]), tolower(labels[ranked$category[nrow(ranked)]])),
  "Coverage includes warnings and review questions as well as restrictions;",
  "it is not a measure of protection strength. Sensitivity analyses examine source",
  "mix, shared text, and excerpt length. Results describe this convenience collection",
  "of excerpts, not representative US policy or implementation. Original-source",
  "authenticity, currentness, and completeness remain unverified; no independent",
  "human annotation or inter-rater reliability is claimed. The study provides a",
  "traceable evidence base for further comparison rather than a legal ranking."
)
writeLines(abstract, file.path(out, "poster_abstract.txt"))
readme <- c(
  "# Student privacy in K-12 AI policy excerpts",
  "",
  "## What this project asks",
  "",
  "**Which downstream student-data practices do the supplied excerpts address,",
  "and how do they describe restrictions, permissions, and review procedures?**",
  "",
  "This is an exploratory, AI-assisted textual comparison, not a legal ranking.",
  "The main deliverables are static figures and the explanation below. Supporting",
  "CSV tables preserve the evidence; no website is required or generated.",
  "",
  "## What we did",
  "",
  sprintf("1. Included all **%d PDFs** in the supplied Privacy Passages folder, extracting **%d paragraphs** locally with R/pdftools.",
          nrow(documents), nrow(passages)),
  "2. Preserved excerpt PDF pages, reported original-source locations, and adjacent",
  "   text. Removed editorial introductions/headings from the coded body.",
  "3. Developed keyword rules using an earlier pilot; froze version 2 before",
  "   examining six fresh PDFs. Keywords located candidates, not policy meanings.",
  "4. Reviewed every extracted body, including no-hit paragraphs. The main assistant",
  "   reviewed the six fresh PDFs; three AI reviewers reviewed disjoint batches",
  "   covering the remainder. Each document received one AI review.",
  "5. Applied three broad categories and 11 specific multi-label subcodes.",
  "   Recorded treatment, wording force, actors, conditions, uncertainty, source",
  "   function, and quotations. A paragraph may address several practices.",
  "6. Checked all recorded quotations against their named extracted paragraphs;",
  "   checked complete document review coverage, unique IDs, and frozen-rule hashes.",
  "7. Counted each document once per category/subcode/treatment. Repeated mentions",
  "   do not increase a document's count. Categories and treatments overlap.",
  "8. Tested sensitivity to document function, shared wording, and excerpt length.",
  "9. Re-coded previously positive training and retention paragraphs into atomic",
  "   quoted provisions; distinguished actual directions from review questions and",
  "   recorded mechanisms. This was a targeted AI refinement, not human validation.",
  "",
  "**The topic-modeling pilot was exploratory and is not the method producing",
  "these counts.** These results come from structured AI-assisted text review.",
  "",
  "## Main findings",
  "",
  "| Topic | Documents with explicit content | Percent | Uncertain only |",
  "|---|---:|---:|---:|",
  vapply(seq_len(nrow(coverage)), function(i) {
    r <- coverage[i, ]
    sprintf("| %s | %d/%d | %.1f%% | %d |", labels[r$category],
            r$explicit_content_found, r$documents, r$percent_with_content, r$uncertain_only)
  }, character(1)),
  "",
  "**Sharing/secondary use is located most frequently; retention/deletion least",
  "frequently.** This ordering persists in the tested sensitivity subsets.",
  "These figures include warnings and vendor-review questions, not only rules.",
  "",
  "## More specific findings",
  "",
  "| Specific practice addressed | Documents | Percent of all documents |",
  "|---|---:|---:|",
  vapply(seq_len(nrow(subcodes)), function(i) {
    sprintf("| %s | %d | %.1f%% |", subcodes$label[i], subcodes$documents[i],
            subcodes$percent_of_all_documents[i])
  }, character(1)),
  "",
  "Explicit discussion of downstream disclosure and educational-purpose limits",
  "is more common than discussion of sale, service improvement, or deletion requests.",
  "**A deletion procedure is not necessarily a deletion right or a fixed deadline.**",
  "Likewise, a retention-limit code can mean that a document asks vendors to specify",
  "a duration, not that the document supplies a numerical duration itself.",
  "",
  "## What differs substantively?",
  "",
  "- **Training restrictions have different scopes and exceptions.** Philadelphia's",
  "  excerpt reports no-training commitments for specified contracted tools",
  "  (D145-B003), whereas Bellevue explicitly permits district authorization",
  "  (D017-B021). Charleston refers to appropriate authorization without naming",
  "  the authorizer in the passage (D037-B001). Do not read these as equivalent bans.",
  "- **Purpose matters.** The Alabama template restricts new contractor-product",
  "  training but includes prior-approval exceptions for district-specific",
  "  development (D005-B011 and D005-B013). A template is not statewide adoption.",
  "- **Deletion directions differ.** Rochester calls for awareness of periods and",
  "  procedures (D156-B002); Bellevue requires explanation of deletion practices",
  "  (D017-B021). These are not evidence of identical rights or timelines.",
  "",
  "The [evidence table](reviewed_evidence.csv) contains quotations, source locations,",
  "conditions, and surrounding text for these IDs. Original sources remain unverified.",
  "",
  "## Are we specific enough?",
  "",
  "**The three-category chart alone is not enough for a detailed comparison.**",
  "Use the specific-practice chart, the treatment profiles, and the concrete",
  "contrasts above together. They distinguish what is discussed from how it is treated.",
  "",
  "The initial broad coding is **paragraph-level**, not a complete inventory of",
  "individual legal provisions. A paragraph with several subcodes has one overall",
  "treatment label. We therefore do **not** cross-tabulate that label into claims",
  "such as 'nine policies ban selling data': that would falsely assign the same",
  "treatment to every subcode in a mixed paragraph.",
  "",
  "A targeted second pass now separates individual training and retention provisions,",
  "including authorizers, deletion triggers, numerical timing, backups, and confirmation.",
  "Its narrower scope and limits are explained below; it does not replace the",
  "original broad counts or establish independently validated legal classifications.",
  "",
  targeted$markdown,
  "## Recommended visualizations",
  "",
  "1. **[Provision mechanisms](figures/provision_mechanisms.png)**: main comparison;",
  "   scope-specific training exceptions and concrete retention/deletion mechanisms.",
  "2. **[Direction versus review](figures/provision_profiles.png)**: simpler summary",
  "   using mutually exclusive document profiles; useful as a companion figure.",
  "3. **[Specific practices](figures/specific_practices.png)**: overview; 11 practices.",
  "4. **[Treatment profiles](figures/treatment_profiles.png)**: restrictions, conditional",
  "   permissions, discussion/review, and other treatments by broad topic.",
  "5. **[Sensitivity checks](figures/sensitivity.png)**: source/excerpt selection caveat.",
  "6. [Broad coverage](figures/coverage.png): optional introductory overview.",
  "7. [Coverage versus restrictions](figures/treatment.png): optional simpler treatment view.",
  "",
  "Each figure also has a vector PDF in [figures/](figures/).",
  "Treatment-profile counts overlap: one document may contain both restrictive",
  "wording and conditional permission. Do not sum them or interpret a restrictive",
  "paragraph as a document-wide ban.",
  "",
  "## Quality and sensitivity",
  "",
  "- Fresh sample: 6 PDFs / 81 paragraphs, with only 7 definite relevant",
  "  paragraph-category pairs. All seven were retrieved, but sharing precision",
  "  was 3/10. This small AI-reference check is not general accuracy validation.",
  "- Full-body review found relevant content missed by frozen searches.",
  "  See [corpus retrieval diagnostic](corpus_retrieval_diagnostic.csv) and",
  "  [no-hit audit](no_hit_audit.csv). Counts use reviewed text, not only hits.",
  "- Longer excerpts show higher coverage. For excerpts with at least 1,000 body",
  "  characters, training/sharing/retention coverage is about 37.9%/53.8%/27.3%,",
  "  versus 28.3%/42.4%/20.1% overall. This is descriptive, not a causal effect.",
  "- Excluding template/curriculum/resource documents or collapsing high-similarity",
  "  groups preserves the topic ordering. See [sensitivity table](sensitivity_checks.csv).",
  "- Similarity flags use five-word-shingle Jaccard >= 0.70, not proof of shared",
  "  authorship or exhaustive detection of common templates.",
  "- One review used `descriptive` as a treatment; it was normalized to",
  "  `discussion_or_review` with originals retained in [the normalization log](review_label_normalization.csv).",
  "",
  "## Limitations and permitted conclusions",
  "",
  "- No independent human annotation or inter-rater reliability was measured.",
  "  Quotes matching text validates provenance, **not correctness of interpretation**.",
  "- The corpus is a convenience collection of selected excerpts; original sources,",
  "  dates, adoption, authenticity, and completeness have not been independently verified.",
  "- One PDF is not one independent jurisdiction. Do not report these as percentages",
  "  of states, districts, or all US policies.",
  "- 'Not located' is not absence of legal protection. Other documents/laws may apply.",
  "- Mandatory wording is not legal enforceability. We did not measure implementation",
  "  or student outcomes and cannot rank which jurisdiction protects students best.",
  "- AI review and source-function judgments may be inconsistent or mistaken.",
  "  Disclose AI assistance and follow course requirements.",
  "",
  "**Defensible conclusion:** The supplied excerpts differ both in which downstream",
  "data practices they explicitly address and in the scope, conditions, and type",
  "of direction they provide. Topic coverage alone does not establish equivalent safeguards.",
  "",
  "## Reproducing the outputs",
  "",
  "From the repository root, with R and jsonlite available:",
  "",
  "```sh",
  "Rscript test_passage_pilot.R",
  "Rscript test_privacy_study.R",
  "Rscript test_privacy_provisions.R",
  "Rscript summarize_privacy_study.R privacy_study",
  "```",
  "",
  "Extraction additionally requires pdftools. See",
  "[preparation script](../prepare_privacy_study.R) and",
  "[review protocol](review_protocol.txt). Original review JSON, extracted",
  "passages, source hashes, frozen rules, and CSV results are retained for audit.",
  "Re-running summarization regenerates figures/tables/this README, not review JSON.",
  "No websites are generated."
)
writeLines(readme, file.path(out, "README.md"))
stopifnot(all(coverage$explicit_content_found + coverage$uncertain_only + coverage$not_located ==
                nrow(documents)), nrow(grid) == nrow(documents) * 3L,
          all(coverage$restrictive_or_conditional_wording <= coverage$explicit_content_found))
print(coverage, row.names = FALSE)
print(metrics, row.names = FALSE)
cat("All review, quotation, counting, and rule-hash checks passed.\n")
