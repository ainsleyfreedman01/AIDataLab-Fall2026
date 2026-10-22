args <- commandArgs(trailingOnly = TRUE)
root <- if (length(args)) args[1L] else tempdir()
dir.create(root, recursive = TRUE, showWarnings = FALSE)
out <- tempfile("privacy-study-check-", tmpdir = root)
dir.create(out)
dir.create(file.path(out, "review"))
source("passage_pilot.R")
ids <- sprintf("D%03d", 1:4)
text <- c(
  "Vendors must not train models on student data.",
  "Student data may be shared only with permission.",
  "Districts should specify data retention periods.",
  "This curriculum teaches general privacy awareness."
)
inventory <- data.frame(
  doc_id = ids, document = paste0(ids, ".pdf"), path = paste0(ids, ".pdf"),
  md5 = paste0("fixture", 1:4), pages = 1L,
  body_characters = nchar(text), paragraphs = 1L,
  fresh_quality_sample = c(TRUE, FALSE, FALSE, FALSE),
  metadata_excerpt = "Synthetic test fixture", batch = c("fresh", "batch1", "batch2", "batch3")
)
passages <- data.frame(
  document = inventory$document, pdf_page = 1L, line_start = 1L, line_end = 1L,
  source_location = "Source: synthetic fixture", section = "Fixture",
  extraction_status = "source_labeled", text = text,
  passage_id = paste0(ids, "::p01::b001"), doc_id = ids, block = 1L,
  evidence_id = paste0(ids, "-B001"), previous_context = "", next_context = ""
)
write.csv(inventory, file.path(out, "inventory.csv"), row.names = FALSE)
write.csv(passages, file.path(out, "passages.csv"), row.names = FALSE)
write.csv(search_rules("v2"), file.path(out, "frozen_rules_v2.csv"), row.names = FALSE)
writeLines(unname(tools::md5sum(file.path(out, "frozen_rules_v2.csv"))),
           file.path(out, "rules_md5.txt"))
cats <- c("model_training", "sharing_secondary_use", "retention_deletion")
subcodes <- c("training_reuse", "disclosure", "retention_limit")
for (i in 1:4) {
  evidence <- if (i == 4L) list() else list(list(
    evidence_id = passages$evidence_id[i], category = cats[i], relevance = "yes",
    subcodes = list(subcodes[i]),
    treatment = c("restricts", "conditional_permission", "discussion_or_review")[i],
    force = c("mandatory_wording", "mandatory_wording", "recommendation")[i],
    actor = "unspecified", conditions = "", source_function = "guidance",
    quotation = text[i], notes = "Synthetic, not a real policy."
  ))
  review <- list(reviewer = "synthetic test", documents = list(list(
    doc_id = ids[i], review_status = "complete",
    source_function = if (i == 4L) "curriculum" else "guidance",
    government_level = "unknown", notes = "Synthetic fixture."
  )), evidence = evidence)
  jsonlite::write_json(review, file.path(out, "review", paste0(inventory$batch[i], "_review.json")),
                       auto_unbox = TRUE, pretty = TRUE)
}
for (i in c(1L, 3L)) {
  training <- i == 1L
  review <- list(
    category = cats[i], reviewer = "AI_assisted_targeted_review_not_independent_validation",
    assessments = list(list(evidence_id = passages$evidence_id[i], disposition = "coded", notes = "Fixture.")),
    provisions = list(list(
      provision_id = if (training) "T001" else "R001",
      evidence_id = passages$evidence_id[i], quotation = text[i],
      practice = if (training) "model_training" else "retention_deletion_transparency",
      treatment = if (training) "prohibits" else "review_or_warning",
      force = if (training) "mandatory_wording" else "recommendation",
      actor = if (training) "Vendors" else "Districts",
      authorization = if (training) "not_stated" else "not_applicable",
      trigger = "not_applicable", timing = if (training) "not_applicable" else "unspecified",
      timing_detail = "", backups = if (training) "not_applicable" else "not_stated",
      verification = if (training) "not_applicable" else "not_stated",
      scope = "student data", conditions = "", notes = "Synthetic fixture.",
      context_kind = "directive_or_guidance"
    ))
  )
  jsonlite::write_json(review, file.path(out, "review",
                                        if (training) "training_provisions.json" else "retention_provisions.json"),
                       auto_unbox = TRUE, pretty = TRUE)
}
result <- system2(file.path(R.home("bin"), "Rscript"),
                  c("summarize_privacy_study.R", shQuote(out)),
                  stdout = TRUE, stderr = TRUE)
if (!is.null(attr(result, "status"))) stop(paste(result, collapse = "\n"))
coverage <- read.csv(file.path(out, "coverage_summary.csv"))
grid <- read.csv(file.path(out, "document_category_matrix.csv"))
stopifnot(nrow(grid) == 12L, all(coverage$documents == 4L),
          all(coverage$explicit_content_found == 1L),
          all(coverage$not_located == 3L),
          identical(coverage$restrictive_or_conditional_wording, c(1L, 1L, 0L)),
          file.exists(file.path(out, "README.md")),
          !file.exists(file.path(out, "poster_draft.html")),
          !file.exists(file.path(out, "evidence_explorer.html")),
          file.exists(file.path(out, "figures", "specific_practices.pdf")),
          file.exists(file.path(out, "figures", "treatment_profiles.png")),
          file.exists(file.path(out, "figures", "provision_mechanisms.png")),
          file.exists(file.path(out, "figures", "provision_mechanisms.pdf")),
          file.exists(file.path(out, "figures", "provision_profiles.png")),
          file.exists(file.path(out, "atomic_provisions.csv")),
          file.exists(file.path(out, "figures", "coverage.pdf")))
# A corrupt quotation must fail instead of producing plausible-looking output.
path <- file.path(out, "review", "fresh_review.json")
review <- jsonlite::fromJSON(path, simplifyVector = FALSE)
review$evidence[[1L]]$quotation <- "Invented unsupported quotation."
jsonlite::write_json(review, path, auto_unbox = TRUE, pretty = TRUE)
result <- suppressWarnings(system2(file.path(R.home("bin"), "Rscript"),
                                    c("summarize_privacy_study.R", shQuote(out)),
                                    stdout = TRUE, stderr = TRUE))
stopifnot(!is.null(attr(result, "status")),
          any(grepl("Quotation validation failed", result, fixed = TRUE)))
cat("Passed synthetic end-to-end checks: complete review coverage, document-level\n",
    "counting, treatment subsets, static figures/README, and rejection of invented quotes.\n")
cat("Synthetic artifacts:", out, "\n")
