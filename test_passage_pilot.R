source("passage_pilot.R")

fixture <- c(
  paste(c("Editorial Title", "Excerpted verbatim introduction.", "",
          "Training clause", "Source: page 8", "",
          "Vendors must not use student information to train models.", "",
          "Staff clause", "Source: page 9", "",
          "Staff training is required."), collapse = "\n"),
  paste(c("Deletion clause", "Source: page 10", "",
          "Records are deleted after contract termination.", "",
          "Students should share ideas."), collapse = "\n")
)
p <- extract_blocks(fixture, "fixture.pdf")
stopifnot(nrow(p) == 4L, identical(p$pdf_page, c(1L, 1L, 2L, 2L)),
          !any(grepl("Editorial|Excerpted|Source:", p$text)),
          p$source_location[1L] == "Source: page 8",
          p$source_location[3L] == "Source: page 10",
          grepl("must not", p$text[1L], fixed = TRUE),
          !anyDuplicated(p$passage_id))
hits <- retrieve_candidates(p)
stopifnot(sum(hits$category == "model_training") == 2L,
          sum(hits$category == "retention_deletion") == 1L,
          sum(hits$category == "sharing_secondary_use") == 1L)
# Broad lexical retrieval deliberately includes staff training; review rejects it.
stopifnot(any(grepl("Staff training", hits$text, fixed = TRUE)))
stopifnot(normalize_search_text("third\u2011party") == "third-party",
          normalize_search_text("retain-\ning") == "retaining")
empty <- retrieve_candidates(transform(p, text = "No relevant words."))
stopifnot(nrow(empty) == 0L, all(c("category", "matched_terms") %in% names(empty)))
unlabeled <- extract_blocks("Readable but unfamiliar PDF layout.", "unknown.pdf")
stopifnot(unlabeled$extraction_status == "needs_format_review")
stopifnot(is.null(extract_blocks("", "empty.pdf")))
v2_fixture <- transform(p[rep(1L, 4L), ],
                        text = c("Data use is limited to educational purposes.",
                                 "Input may be made available to other users.",
                                 "Customize the AI System for district needs.",
                                 "Duration of data usage must be specified."))
v2_hits <- retrieve_candidates(v2_fixture, search_rules("v2"))
stopifnot(any(v2_hits$category == "model_training"),
          sum(v2_hits$category == "sharing_secondary_use") == 3L,
          any(v2_hits$category == "retention_deletion"))
stopifnot(inherits(tryCatch(search_rules("bad"), error = identity), "error"))
cat("Passed extraction, page/source provenance, negation preservation, lexical\n",
    "boundary, normalization, no-hit, unfamiliar-format, and revised-rule checks.\n")
