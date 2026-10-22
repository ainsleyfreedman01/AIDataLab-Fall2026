summarize_privacy_provisions <- function(out, evidence, documents) {
  categories <- c("model_training", "retention_deletion")
  paths <- file.path(out, "review", c("training_provisions.json", "retention_provisions.json"))
  if (!all(file.exists(paths))) {
    stop("Targeted provision review incomplete: ", paste(paths[!file.exists(paths)], collapse = ", "))
  }
  fields <- c("provision_id", "evidence_id", "quotation", "practice", "treatment",
              "force", "actor", "authorization", "trigger", "timing", "timing_detail",
              "backups", "verification", "scope", "conditions", "notes", "context_kind",
              "comparison_exclusion_reason")
  enums <- list(
    treatment = c("prohibits", "conditional", "permits", "review_or_warning", "describes", "unclear"),
    force = c("mandatory_wording", "recommendation", "descriptive", "unclear"),
    authorization = c("district", "parent_guardian", "student", "consent_unspecified",
                      "authorization_unspecified", "not_stated", "not_applicable"),
    trigger = c("contract_end", "purpose_end", "account_closure", "request",
                "scheduled", "unspecified", "not_applicable"),
    timing = c("numeric_deadline", "event_based", "unspecified", "not_applicable"),
    backups = c("explicitly_included", "explicitly_excluded", "not_stated", "not_applicable"),
    verification = c("explicit_confirmation", "not_stated", "not_applicable"),
    context_kind = c("directive_or_guidance", "reported_commitment",
                     "proposed_or_model_clause", "scenario_or_exercise", "review_question", "unclear")
  )
  normalize <- function(x) gsub("[[:space:]]+", " ", trimws(x))
  all_provisions <- all_assessments <- list()
  for (i in seq_along(paths)) {
    review <- jsonlite::fromJSON(paths[i], simplifyVector = FALSE)
    if (!identical(review$category, categories[i]) ||
        !identical(review$reviewer, "AI_assisted_targeted_review_not_independent_validation")) {
      stop("Invalid targeted review metadata: ", paths[i])
    }
    expected <- evidence[evidence$category == categories[i] & evidence$relevance == "yes", ]
    assessments <- do.call(rbind, lapply(review$assessments, function(a) {
      if (!setequal(names(a), c("evidence_id", "disposition", "notes")) ||
          !all(vapply(a, function(x) is.character(x) && length(x) == 1L && !is.na(x),
                      logical(1)))) stop("Invalid provision assessment.")
      as.data.frame(a, stringsAsFactors = FALSE)
    }))
    if (is.null(assessments) || anyDuplicated(assessments$evidence_id) ||
        !setequal(assessments$evidence_id, expected$evidence_id) ||
        !all(assessments$disposition %in% c("coded", "context_only", "uncertain"))) {
      stop("Incomplete or duplicate targeted assessment coverage: ", categories[i])
    }
    p <- do.call(rbind, lapply(review$provisions, function(p) {
      if (!"comparison_exclusion_reason" %in% names(p)) p$comparison_exclusion_reason <- ""
      if (!setequal(names(p), fields) ||
          !all(vapply(p, function(x) is.character(x) && length(x) == 1L && !is.na(x),
                      logical(1)))) stop("Invalid atomic provision fields.")
      as.data.frame(p[fields], stringsAsFactors = FALSE)
    }))
    if (is.null(p)) stop("Targeted review contains no provisions: ", categories[i])
    if (anyDuplicated(p$provision_id) || any(!nzchar(trimws(p$provision_id))) ||
        any(!nzchar(trimws(p$scope))) || any(!p$evidence_id %in% expected$evidence_id)) {
      stop("Invalid atomic provision identifiers or scope.")
    }
    for (field in names(enums)) {
      if (!all(p[[field]] %in% enums[[field]])) stop("Invalid provision enum: ", field)
    }
    practices <- if (i == 1L) c("model_training", "service_improvement") else
      c("retention_duration", "deletion", "deletion_request", "retention_deletion_transparency")
    if (!all(p$practice %in% practices)) stop("Invalid provision practice.")
    if (!setequal(assessments$evidence_id[assessments$disposition == "coded"], p$evidence_id)) {
      stop("Provision records disagree with assessment dispositions.")
    }
    ix <- match(p$evidence_id, expected$evidence_id)
    quote_ok <- vapply(seq_len(nrow(p)), function(j) {
      nzchar(trimws(p$quotation[j])) &&
        grepl(normalize(p$quotation[j]), normalize(expected$text[ix[j]]), fixed = TRUE)
    }, logical(1))
    if (!all(quote_ok)) {
      stop("Atomic quotation validation failed: ", paste(p$provision_id[!quote_ok], collapse = ", "))
    }
    if (any(p$timing %in% c("numeric_deadline", "event_based") &
            !nzchar(trimws(p$timing_detail)))) stop("Missing provision timing detail.")
    if (i == 1L && any(p$trigger != "not_applicable" | p$timing != "not_applicable" |
                       p$backups != "not_applicable" | p$verification != "not_applicable")) {
      stop("Retention fields applied to training provisions.")
    }
    if (i == 2L && any(p$authorization != "not_applicable")) {
      stop("Training authorization field applied to retention provisions.")
    }
    p$category <- assessments$category <- categories[i]
    p <- cbind(p, expected[ix, c("doc_id", "document", "pdf_page", "source_location",
                                "source_function", "text", "previous_context", "next_context")])
    all_provisions[[i]] <- p
    all_assessments[[i]] <- assessments
  }
  provisions <- do.call(rbind, all_provisions)
  assessments <- do.call(rbind, all_assessments)
  if (anyDuplicated(provisions$provision_id)) stop("Duplicate provision identifiers across reviews.")
  provisions$review_provenance <- "targeted_AI_recoding_not_independent_human_validation"
  provisions$included_in_primary_comparison <- provisions$context_kind %in%
    c("directive_or_guidance", "reported_commitment", "review_question") &
    !nzchar(trimws(provisions$comparison_exclusion_reason))
  write.csv(provisions, file.path(out, "atomic_provisions.csv"), row.names = FALSE, na = "")
  write.csv(assessments, file.path(out, "provision_assessments.csv"), row.names = FALSE, na = "")
  context_counts <- aggregate(provision_id ~ category + context_kind, provisions, length)
  names(context_counts)[3] <- "provisions"
  write.csv(context_counts, file.path(out, "provision_context_counts.csv"), row.names = FALSE)

  features <- list()
  add <- function(id, category, label, selected, kind) {
    all <- provisions[selected & provisions$category == category, ]
    p <- all[all$included_in_primary_comparison, ]
    reviewed <- unique(evidence$doc_id[evidence$category == category & evidence$relevance == "yes"])
    features[[length(features) + 1L]] <<- list(
      summary = data.frame(feature = id, category = category, label = label, kind = kind,
                           documents = length(unique(p$doc_id)),
                           mandatory_wording_documents = length(unique(p$doc_id[p$force == "mandatory_wording"])),
                           all_context_documents = length(unique(all$doc_id)),
                           reviewed_topic_documents = length(reviewed),
                           corpus_documents = nrow(documents)),
      matches = data.frame(feature = rep(id, nrow(all)), provision_id = all$provision_id,
                           doc_id = all$doc_id,
                           included_in_primary_comparison = all$included_in_primary_comparison,
                           stringsAsFactors = FALSE)
    )
  }
  p <- provisions
  action <- p$treatment %in% c("prohibits", "conditional", "permits")
  limit <- p$treatment %in% c("prohibits", "conditional")
  add("training_restriction", categories[1], "Restriction; no exception in quoted clause",
      p$treatment == "prohibits", "direction")
  for (a in c("district", "parent_guardian", "student", "consent_unspecified", "authorization_unspecified")) {
    label <- c(district = "Exception: district authorization", parent_guardian = "Exception: parent/guardian consent",
               student = "Exception: student consent", consent_unspecified = "Exception: consent, actor unspecified",
               authorization_unspecified = "Exception: authorization, actor unspecified")
    add(paste0("training_", a), categories[1], label[a],
        p$treatment == "conditional" & p$authorization == a, "direction")
  }
  add("training_other_condition", categories[1], "Other conditional use",
      p$treatment == "conditional" & p$authorization %in% c("not_stated", "not_applicable"), "direction")
  add("training_permission", categories[1], "Permission without consent condition",
      p$treatment == "permits", "direction")
  add("training_review", categories[1], "Review instruction or warning",
      p$treatment == "review_or_warning", "review")
  add("retention_limit", categories[2], "Actual retention limit stated",
      limit & p$practice == "retention_duration", "direction")
  add("deletion_direction", categories[2], "Deletion/return direction stated",
      action & p$practice == "deletion", "direction")
  add("deletion_request", categories[2], "Deletion-request mechanism stated",
      action & p$practice == "deletion_request", "direction")
  add("purpose_end", categories[2], "Deletion tied to end of purpose/use",
      action & p$practice == "deletion" & p$trigger == "purpose_end", "direction")
  add("contract_end", categories[2], "Deletion/return tied to contract end",
      action & p$practice == "deletion" & p$trigger == "contract_end", "direction")
  add("numeric_deadline", categories[2], "Numerical retention/deletion time limit",
      (action & p$practice %in% c("deletion", "deletion_request") &
         p$timing == "numeric_deadline") |
        (limit & p$practice == "retention_duration" & p$timing == "numeric_deadline"), "direction")
  add("backups", categories[2], "Deletion explicitly includes backups",
      action & p$practice %in% c("deletion", "deletion_request") & p$backups == "explicitly_included", "direction")
  add("confirmation", categories[2], "Explicit deletion confirmation",
      action & p$practice %in% c("deletion", "deletion_request") &
        p$verification == "explicit_confirmation", "direction")
  add("retention_review", categories[2], "Review/transparency rather than deletion rule",
      p$treatment == "review_or_warning" | p$practice == "retention_deletion_transparency", "review")
  counts <- do.call(rbind, lapply(features, `[[`, "summary"))
  matches <- do.call(rbind, lapply(features, `[[`, "matches"))
  excluded <- documents$doc_id[documents$source_function %in% c("template", "curriculum", "resource_summary")]
  counts$documents_excluding_templates_curricula_resources <- vapply(features, function(f) {
    length(setdiff(unique(f$matches$doc_id[f$matches$included_in_primary_comparison]), excluded))
  }, integer(1))
  counts$reviewed_topic_documents_excluding_templates_curricula_resources <- vapply(counts$category, function(c) {
    length(setdiff(unique(evidence$doc_id[evidence$category == c & evidence$relevance == "yes"]), excluded))
  }, integer(1))
  write.csv(counts, file.path(out, "provision_feature_counts.csv"), row.names = FALSE)
  write.csv(matches, file.path(out, "provision_feature_evidence.csv"), row.names = FALSE)
  profiles <- do.call(rbind, lapply(categories, function(c) {
    ids <- unique(evidence$doc_id[evidence$category == c & evidence$relevance == "yes"])
    data.frame(
      doc_id = ids, category = c,
      direction_found = ids %in% p$doc_id[action & p$included_in_primary_comparison & p$category == c &
                                           p$practice != "retention_deletion_transparency"],
      review_found = ids %in% p$doc_id[p$category == c & p$included_in_primary_comparison &
                                       (p$treatment == "review_or_warning" |
                                          p$practice == "retention_deletion_transparency")]
    )
  }))
  profiles$profile <- ifelse(profiles$direction_found,
                             ifelse(profiles$review_found, "both", "direction_only"),
                             ifelse(profiles$review_found, "review_only", "description_unclear_or_context"))
  write.csv(profiles, file.path(out, "provision_document_profiles.csv"), row.names = FALSE)
  profile_summary <- do.call(rbind, lapply(categories, function(c) {
    g <- profiles[profiles$category == c, ]
    data.frame(category = c, reviewed = nrow(g), direction_only = sum(g$profile == "direction_only"),
               both = sum(g$profile == "both"), review_only = sum(g$profile == "review_only"),
               other = sum(g$profile == "description_unclear_or_context"))
  }))
  stopifnot(
    all(rowSums(profile_summary[c("direction_only", "both", "review_only", "other")]) ==
          profile_summary$reviewed),
    all(counts$mandatory_wording_documents <= counts$documents),
    all(counts$documents <= counts$reviewed_topic_documents),
    all(counts$documents_excluding_templates_curricula_resources <=
          counts$reviewed_topic_documents_excluding_templates_curricula_resources)
  )
  dir.create(file.path(out, "figures"), showWarnings = FALSE)
  draw <- function() {
    par(mfrow = c(1, 2), mar = c(7, 0.5, 4, 0.5), oma = c(2, 0, 2, 0))
    xmax <- max(5, counts$documents) * 1.3
    for (category in categories) {
      f <- counts[counts$category == category, ]
      f <- f[rev(seq_len(nrow(f))), ]
      n <- unique(f$reviewed_topic_documents)
      positions <- barplot(f$documents, horiz = TRUE, axes = FALSE, axisnames = FALSE,
                          xlim = c(-xmax * 1.7, xmax), col = ifelse(f$kind == "review", "#C88935", "#33658A"),
                          border = NA,
                          main = sprintf("%s\n%d topic-positive excerpts re-examined",
                                         if (category == categories[1]) "Training / improvement" else "Retention / deletion", n),
                          cex.main = 0.9)
      text(-xmax * 0.05, positions, f$label, adj = 1, cex = 0.70)
      text(f$documents, positions, labels = f$documents, pos = 4, cex = 0.8)
      axis(1, at = pretty(c(0, xmax), n = 4))
      mtext("Documents with at least one qualifying provision", side = 1, line = 2.5, cex = 0.7)
    }
    mtext("From topic coverage to specific mechanisms", outer = TRUE, side = 3, line = 0.4, font = 2)
    mtext("Counts overlap. Blue: stated direction, including recommendations; amber: review/warning/transparency.",
          outer = TRUE, side = 1, line = 0, cex = 0.7)
    mtext("Illustrative/model clauses and content-takedown deadlines excluded. Zero is not proof of policy absence.",
          outer = TRUE, side = 1, line = 1, cex = 0.7)
  }
  png(file.path(out, "figures", "provision_mechanisms.png"), width = 2600, height = 1300, res = 160)
  tryCatch(draw(), finally = dev.off())
  pdf(file.path(out, "figures", "provision_mechanisms.pdf"), width = 16.25, height = 8.125)
  tryCatch(draw(), finally = dev.off())
  draw_profiles <- function() {
    par(mar = c(8, 13, 4, 3))
    values <- t(as.matrix(profile_summary[c("direction_only", "both", "review_only", "other")]))
    positions <- barplot(values, horiz = TRUE, names.arg = c("Training / improvement", "Retention / deletion"),
                         las = 1, col = c("#33658A", "#43856B", "#C88935", "#AAAAAA"),
                         border = NA, xlim = c(0, max(profile_summary$reviewed) * 1.08),
                         main = "Mentioning privacy is not the same as specifying a mechanism",
                         xlab = "Topic-positive excerpt documents")
    for (i in seq_len(ncol(values))) {
      centers <- cumsum(values[, i]) - values[, i] / 2
      keep <- values[, i] > 0
      text(centers[keep], positions[i], values[keep, i], col = "white", font = 2, cex = 1)
    }
    legend("bottom", inset = c(0, -0.31), xpd = NA, ncol = 2,
           legend = c("Direction only", "Direction and review", "Review/transparency only", "Other/excluded context"),
           fill = c("#33658A", "#43856B", "#C88935", "#AAAAAA"), bty = "n", cex = 0.75)
    mtext("Mutually exclusive profiles. Directions may be recommendations; wording is not enforceability.",
          side = 1, line = 6.5, cex = 0.65)
  }
  png(file.path(out, "figures", "provision_profiles.png"), width = 1800, height = 1050, res = 160)
  tryCatch(draw_profiles(), finally = dev.off())
  pdf(file.path(out, "figures", "provision_profiles.pdf"), width = 11.25, height = 6.56)
  tryCatch(draw_profiles(), finally = dev.off())
  count <- function(id) counts$documents[match(id, counts$feature)]
  markdown <- c(
    "## Targeted provision-level comparison",
    "",
    sprintf("A second AI-assisted pass assessed **%d previously positive paragraph-category pairs** and recorded **%d atomic provisions**.",
            nrow(assessments), nrow(provisions)),
    "This pass revisited training/improvement and retention/deletion only. It split",
    "mixed paragraphs into separately quoted directions, preserving data/tool scope,",
    "exceptions, authorizing actor, triggers, timing, backup scope, and confirmation.",
    "Paragraphs that only supplied context or remained uncertain were logged rather",
    "than forced into a provision. The original broad coding was preserved.",
    "Primary comparisons exclude hypothetical exercises, proposed/model clauses,",
    "unclear-status language, and separately identified out-of-scope content takedowns.",
    "These remain in the evidence table with explicit",
    "context labels. Recommended guidance and reported commitments are included;",
    "inclusion still does not establish adoption or enforceability.",
    sprintf("Of %d recorded provisions, %d enter primary comparisons; %d are retained",
            nrow(provisions), sum(provisions$included_in_primary_comparison),
            sum(!provisions$included_in_primary_comparison)),
    "only as illustrative/proposed/unclear or out-of-scope context. This is a record count, not",
    "a document count. See [context counts](provision_context_counts.csv).",
    "",
    "### Directions versus review questions",
    "",
    "See [direction-versus-review profiles](figures/provision_profiles.png) for a",
    "simpler poster-ready view of the distinction.",
    "The following document profiles are mutually exclusive within each topic.",
    "A 'direction' can be recommended or mandatory; it does not imply adoption",
    "or enforceability. A document can combine a direction with review questions.",
    "",
    "| Topic | Direction only | Both direction and review | Review/transparency only | Other or excluded context | Total |",
    "|---|---:|---:|---:|---:|---:|",
    vapply(seq_len(nrow(profile_summary)), function(i) {
      r <- profile_summary[i, ]
      sprintf("| %s | %d | %d | %d | %d | %d |",
              if (r$category == categories[1]) "Training / improvement" else "Retention / deletion",
              r$direction_only, r$both, r$review_only, r$other, r$reviewed)
    }, character(1)),
    "",
    "### Specific mechanisms",
    "",
    "**[Provision mechanisms](figures/provision_mechanisms.png) is the recommended",
    "main comparison figure.** Counts below use unique documents, not mentions.",
    "Features overlap. The second column counts any qualifying wording, including",
    "recommendations and descriptions; the third identifies the subset with mandatory",
    "wording for that exact feature. Neither establishes legal authority.",
    "",
    "| Explicit feature in targeted evidence | Documents | With mandatory wording | Reviewed topic documents |",
    "|---|---:|---:|---:|",
    vapply(seq_len(nrow(counts)), function(i) {
      f <- counts[i, ]
      sprintf("| %s: %s | %d | %d | %d |",
              if (f$category == categories[1]) "Training" else "Retention",
              f$label, f$documents, f$mandatory_wording_documents, f$reviewed_topic_documents)
    }, character(1)),
    "",
    sprintf("The targeted evidence contains numerical retention/deletion limits in **%d documents**, explicit backup inclusion in **%d**, and deletion confirmation in **%d**.",
            count("numeric_deadline"), count("backups"), count("confirmation")),
    "These counts exclude questions merely asking a vendor to specify a period or",
    "deletion practice, hypothetical exercises, and proposed/model clauses.",
    "Intimate-image content takedown deadlines are also excluded: removal of",
    "content is not the same mechanism as deletion of retained student service data.",
    "Numerical limits on unrelated records are not counted as",
    "student-data deletion deadlines.",
    "",
    "**Interpretation:** In the primary comparison, the excerpts more often",
    "tell readers to inspect or understand vendor practices than spell out",
    "specific deletion mechanisms. Training clauses also differ in who authorizes",
    "exceptions. These are textual differences, not evidence of comparative",
    "legal strength, compliance, or actual student outcomes.",
    "",
    "### How to audit the finer findings",
    "",
    "- [Atomic provisions](atomic_provisions.csv): exact quotation, treatment, force,",
    "  actor, exception, timing, scope, source, and neighboring context for each record.",
    "- [Feature-to-evidence map](provision_feature_evidence.csv): every chart bar",
    "  linked to provisions, with an inclusion flag distinguishing illustrative,",
    "  proposed/model, unclear-status, and out-of-scope records excluded from primary counts.",
    "- [Feature counts](provision_feature_counts.csv): document counts and explicit",
    "  denominators, including mandatory-wording subsets and sensitivity counts",
    "  excluding template/curriculum/resource-summary documents; an all-context",
    "  count separately shows how including illustrative/proposed language changes counts.",
    "- [Assessment log](provision_assessments.csv): every originally positive",
    "  paragraph-category pair accounted for, including exclusions and ambiguity.",
    "- [Document profiles](provision_document_profiles.csv): mutually exclusive",
    "  direction/review profiles behind the table above.",
    "",
    "### Boundaries of this refinement",
    "",
    "This is targeted re-coding of previously positive evidence, not an independent",
    "human validation or a new full-corpus search. It cannot recover provisions",
    "missed by the original review, including uncertain-only paragraphs. A zero is",
    "not proof of absence from an excerpt, original policy, or jurisdiction.",
    "The training 'no exception' bar describes the quoted clause, not an absolute",
    "document-wide ban; other clauses or external law may qualify it. Authorizers",
    "were recorded only where named, not inferred from passive 'authorization'.",
    "The source-function caveats apply equally to these provisions: a proposed",
    "contract or template can contain mandatory wording without being adopted.",
    "Sharing/sale/advertising remain paragraph-level; no per-practice ban counts",
    "are claimed for those topics. Written-consent requirements were not separately coded.",
    ""
  )
  list(markdown = markdown, provisions = provisions, counts = counts,
       assessments = assessments, profiles = profiles, profile_summary = profile_summary)
}
