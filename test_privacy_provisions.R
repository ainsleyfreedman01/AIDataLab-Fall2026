source("summarize_privacy_provisions.R")
out <- tempfile("provision-check-")
dir.create(out)
dir.create(file.path(out, "review"))
documents <- data.frame(doc_id = c("D001", "D002", "D003"),
                        source_function = c("guidance", "guidance", "template"))
texts <- c(
  "Vendors must not train models unless the district approves.",
  "Review whether vendors delete data within 30 days.",
  "Vendors must delete student data, including backups, within 30 days of contract end and certify deletion.",
  "Vendors must delete student data at contract end.",
  "Unrelated student-work guidance."
)
evidence <- data.frame(
  evidence_id = paste0("E", 1:5),
  category = c("model_training", rep("retention_deletion", 4)),
  relevance = "yes", doc_id = c("D001", "D002", "D003", "D003", "D002"),
  document = c("1.pdf", "2.pdf", "3.pdf", "3.pdf", "2.pdf"),
  pdf_page = 1L, source_location = "Synthetic",
  source_function = c("guidance", "guidance", "template", "template", "guidance"),
  text = texts, previous_context = "", next_context = ""
)
provision <- function(id, index, practice, treatment, authorization = "not_applicable",
                      trigger = "not_applicable", timing = "not_applicable",
                      timing_detail = "", backups = "not_stated", verification = "not_stated") {
  list(provision_id = id, evidence_id = evidence$evidence_id[index], quotation = texts[index],
       practice = practice, treatment = treatment,
       force = if (index == 2L) "recommendation" else "mandatory_wording",
       actor = "vendor", authorization = authorization, trigger = trigger,
       timing = timing, timing_detail = timing_detail, backups = backups,
       verification = verification, scope = "student data",
       conditions = if (index == 1L) "unless the district approves" else "", notes = "Fixture.",
       context_kind = "directive_or_guidance")
}
training <- list(
  category = "model_training", reviewer = "AI_assisted_targeted_review_not_independent_validation",
  assessments = list(list(evidence_id = "E1", disposition = "coded", notes = "")),
  provisions = list(provision("T001", 1, "model_training", "conditional", "district",
                             backups = "not_applicable", verification = "not_applicable"))
)
retention <- list(
  category = "retention_deletion", reviewer = "AI_assisted_targeted_review_not_independent_validation",
  assessments = lapply(2:5, function(i) list(evidence_id = paste0("E", i),
                                            disposition = if (i == 5L) "context_only" else "coded",
                                            notes = if (i == 5L) "Not a student-data mechanism." else "")),
  provisions = list(
    provision("R001", 2, "retention_deletion_transparency", "review_or_warning",
              timing = "numeric_deadline", timing_detail = "30 days"),
    provision("R002", 3, "deletion", "prohibits", trigger = "contract_end",
              timing = "numeric_deadline", timing_detail = "within 30 days of contract end",
              backups = "explicitly_included", verification = "explicit_confirmation"),
    provision("R003", 4, "deletion", "prohibits", trigger = "contract_end",
              timing = "event_based", timing_detail = "at contract end")
  )
)
save_reviews <- function(t = training, r = retention) {
  jsonlite::write_json(t, file.path(out, "review", "training_provisions.json"),
                       auto_unbox = TRUE, pretty = TRUE)
  jsonlite::write_json(r, file.path(out, "review", "retention_provisions.json"),
                       auto_unbox = TRUE, pretty = TRUE)
}
save_reviews()
result <- summarize_privacy_provisions(out, evidence, documents)
count <- function(id, field = "documents") result$counts[[field]][match(id, result$counts$feature)]
stopifnot(
  count("training_district") == 1L, count("training_restriction") == 0L,
  count("deletion_direction") == 1L, count("contract_end") == 1L,
  count("numeric_deadline") == 1L, count("retention_review") == 1L,
  count("backups") == 1L, count("confirmation") == 1L,
  count("numeric_deadline", "mandatory_wording_documents") == 1L,
  count("numeric_deadline", "documents_excluding_templates_curricula_resources") == 0L,
  nrow(result$assessments) == 5L, nrow(result$provisions) == 4L,
  result$profile_summary$review_only[2] == 1L,
  result$profile_summary$direction_only[2] == 1L,
  file.exists(file.path(out, "figures", "provision_mechanisms.pdf"))
)
illustrative <- retention
illustrative$provisions[[2]]$context_kind <- "scenario_or_exercise"
save_reviews(r = illustrative)
filtered <- summarize_privacy_provisions(out, evidence, documents)
numeric <- filtered$counts[filtered$counts$feature == "numeric_deadline", ]
stopifnot(numeric$documents == 0L,
          numeric$all_context_documents == 1L)
illustrative$provisions[[2]]$context_kind <- "proposed_or_model_clause"
save_reviews(r = illustrative)
filtered <- summarize_privacy_provisions(out, evidence, documents)
stopifnot(filtered$counts$documents[filtered$counts$feature == "numeric_deadline"] == 0L)
out_of_scope <- retention
out_of_scope$provisions[[2]]$comparison_exclusion_reason <- "Content takedown, not retained service data."
save_reviews(r = out_of_scope)
filtered <- summarize_privacy_provisions(out, evidence, documents)
stopifnot(filtered$counts$documents[filtered$counts$feature == "numeric_deadline"] == 0L,
          filtered$counts$all_context_documents[
            filtered$counts$feature == "numeric_deadline"] == 1L)
must_fail <- function(pattern) {
  message <- tryCatch({
    summarize_privacy_provisions(out, evidence, documents)
    ""
  }, error = conditionMessage)
  stopifnot(nzchar(message), grepl(pattern, message, fixed = TRUE))
}
bad <- training
bad$provisions[[1]]$quotation <- "Invented quote."
save_reviews(t = bad)
must_fail("Atomic quotation validation failed")
bad <- retention
bad$assessments <- bad$assessments[-1]
save_reviews(r = bad)
must_fail("assessment coverage")
bad <- training
bad$assessments[[1]]$disposition <- "context_only"
save_reviews(t = bad)
must_fail("disagree with assessment")
bad <- retention
bad$provisions[[2]]$timing_detail <- ""
save_reviews(r = bad)
must_fail("Missing provision timing")
bad <- training
bad$provisions[[1]]$authorization <- "guessed"
save_reviews(t = bad)
must_fail("Invalid provision enum")
save_reviews()
unlink(file.path(out, "review", "retention_provisions.json"))
must_fail("review incomplete")
unlink(out, recursive = TRUE)
cat("Passed atomic provision tests: conditional authorization, unique-document counts,\n",
    "review-vs-deadline separation, backup/confirmation scope, coverage and quote failures.\n")
