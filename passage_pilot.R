# Usage: Rscript passage_pilot.R <PDF directory> <output directory> [R library]
normalize_search_text <- function(text) {
  text <- tolower(text)
  text <- gsub("\u00ad", "", text, fixed = TRUE)
  text <- gsub("([[:alpha:]])-[ \t]*\n[ \t]*([[:alpha:]])", "\\1\\2", text)
  text <- gsub("[\u2010-\u2015]", "-", text)
  gsub("[[:space:]]+", " ", text)
}

search_rules <- function(version = "v1") {
  if (!version %in% c("v1", "v2")) stop("Unknown search rule version: ", version)
  rules <- data.frame(
    category = c("model_training", "sharing_secondary_use", "retention_deletion"),
    pattern = c(
      "\\b(train[a-z]*|fine[- ]?tun[a-z]*|improv[a-z]*.{0,60}(model|service|system)|learn[a-z]* from|model development)\\b",
      "\\b(shar[a-z]*|disclos[a-z]*|third[- ]part[a-z]*|sell[a-z]*|sold|sale|advertis[a-z]*|market[a-z]*|commercial[a-z]*|secondary|repurpos[a-z]*|re[- ]?us[a-z]*|other purposes|beyond.{0,35}purpose|profil[a-z]*)\\b",
      "\\b(retain[a-z]*|retention|delet[a-z]*|destroy[a-z]*|destruction|eras[a-z]*|purg[a-z]*|dispos[a-z]*|expir[a-z]*|terminat[a-z]*|stor[a-z]*|keep|kept)\\b"
    ),
    stringsAsFactors = FALSE
  )
  if (version == "v2") {
    rules$pattern[1L] <- paste0(
      rules$pattern[1L],
      "|\\b(customiz[a-z]*|develop[a-z]*).{0,65}\\b(ai system|model)\\b"
    )
    rules$pattern[2L] <- paste0(
      rules$pattern[2L],
      "|\\b(purpose[a-z]*|made available|make it accessible|release this information)\\b",
      "|\\b(used|use).{0,35}\\b(compan[a-z]*|provider[a-z]*|vendor[a-z]*)\\b",
      "|\\b(use of the data|data use|data usage)\\b"
    )
    rules$pattern[3L] <- paste0(
      "\\b(retain[a-z]*|retention|delet[a-z]*|destroy[a-z]*|destruction|",
      "eras[a-z]*|purg[a-z]*|dispos[a-z]*|expir[a-z]*)\\b",
      "|\\b(duration|how long|no longer needed|stored for|kept for)\\b"
    )
  }
  rules
}

extract_blocks <- function(pages, document) {
  rows <- list()
  source <- ""
  section <- ""
  found_source <- FALSE
  for (page in seq_along(pages)) {
    lines <- strsplit(pages[page], "\n", fixed = TRUE)[[1L]]
    source_lines <- grep("^\\s*Source:", lines)
    excluded <- integer()
    if (length(source_lines)) {
      if (!found_source) excluded <- seq_len(source_lines[1L])
      for (i in source_lines) {
        excluded <- c(excluded, i)
        j <- i - 1L
        while (j > 0L && nzchar(trimws(lines[j]))) {
          excluded <- c(excluded, j)
          j <- j - 1L
        }
      }
    }
    buffer <- integer()
    flush <- function() {
      if (!length(buffer)) return(NULL)
      text <- paste(lines[buffer], collapse = "\n")
      if (!nzchar(trimws(text))) return(NULL)
      data.frame(document = document, pdf_page = page,
                 line_start = min(buffer), line_end = max(buffer),
                 source_location = source, section = section,
                 extraction_status = if (found_source) "source_labeled" else "needs_format_review",
                 text = text, stringsAsFactors = FALSE)
    }
    for (i in seq_along(lines)) {
      if (i %in% source_lines) {
        row <- flush()
        if (!is.null(row)) rows[[length(rows) + 1L]] <- row
        buffer <- integer()
        source <- trimws(lines[i])
        j <- i - 1L
        heading <- character()
        while (j > 0L && nzchar(trimws(lines[j]))) {
          heading <- c(trimws(lines[j]), heading)
          j <- j - 1L
        }
        section <- paste(heading, collapse = " ")
        found_source <- TRUE
      } else if (i %in% excluded || !nzchar(trimws(lines[i]))) {
        row <- flush()
        if (!is.null(row)) rows[[length(rows) + 1L]] <- row
        buffer <- integer()
      } else {
        buffer <- c(buffer, i)
      }
    }
    row <- flush()
    if (!is.null(row)) rows[[length(rows) + 1L]] <- row
  }
  if (!length(rows)) return(NULL)
  result <- do.call(rbind, rows)
  result$passage_id <- sprintf("%s::p%02d::b%03d", document, result$pdf_page,
                              seq_len(nrow(result)))
  result
}

retrieve_candidates <- function(passages, rules = search_rules()) {
  rows <- list()
  normalized <- normalize_search_text(passages$text)
  for (i in seq_len(nrow(rules))) {
    hits <- which(grepl(rules$pattern[i], normalized, perl = TRUE))
    if (!length(hits)) next
    result <- passages[hits, , drop = FALSE]
    result$category <- rules$category[i]
    result$matched_terms <- vapply(hits, function(j) {
      matches <- gregexpr(rules$pattern[i], normalized[j], perl = TRUE)
      paste(unique(regmatches(normalized[j], matches)[[1L]]), collapse = " | ")
    }, character(1))
    rows[[length(rows) + 1L]] <- result
  }
  if (!length(rows)) {
    result <- passages[FALSE, , drop = FALSE]
    result$category <- character()
    result$matched_terms <- character()
    return(result)
  }
  do.call(rbind, rows)
}

run_pilot <- function(args) {
  if (length(args) < 2L) stop("Supply PDF and output directories.")
  if (length(args) >= 3L) .libPaths(c(args[3L], .libPaths()))
  if (!requireNamespace("pdftools", quietly = TRUE)) stop("Missing package: pdftools")
  input <- normalizePath(args[1L], mustWork = TRUE)
  output <- args[2L]
  if (dir.exists(output) && length(list.files(output))) {
    stop("Output directory must be new or empty to avoid overwriting review work.")
  }
  dir.create(output, recursive = TRUE, showWarnings = FALSE)
  if (!dir.exists(output)) stop("Cannot create output directory.")
  write_table <- function(x, name) write.csv(x, file.path(output, name),
                                             row.names = FALSE, na = "")
  paths <- sort(list.files(input, pattern = "[.]pdf$", full.names = TRUE,
                           ignore.case = TRUE), method = "radix")
  if (length(paths) < 10L) stop("At least ten PDFs required.")
  set.seed(20261016)
  sampled <- sample(paths, 10L)
  rules <- search_rules()
  write_table(rules, "frozen_search_rules.csv")
  writeLines(unname(tools::md5sum(file.path(output, "frozen_search_rules.csv"))),
             file.path(output, "rules_md5.txt"))
  all_blocks <- list()
  inventory <- list()
  extracted_fingerprints <- character(length(paths))
  dir.create(file.path(output, "raw_pages"))
  for (i in seq_along(paths)) {
    path <- paths[i]
    document <- basename(path)
    error <- ""
    pages <- tryCatch(pdftools::pdf_text(path), error = function(e) {
      error <<- conditionMessage(e)
      warning("PDF extraction failed for ", document, ": ", error)
      character()
    })
    blocks <- extract_blocks(pages, document)
    text <- paste(pages, collapse = "\n")
    extracted_fingerprints[i] <- normalize_search_text(text)
    sampled_index <- match(path, sampled)
    split <- if (is.na(sampled_index)) "inventory_only" else
      if (sampled_index <= 5L) "development" else "validation"
    status <- if (nzchar(error)) "extraction_error" else
      if (!nzchar(trimws(text))) "empty_text_needs_ocr" else
        if (is.null(blocks) || any(blocks$extraction_status != "source_labeled"))
          "needs_format_review" else "extracted_needs_visual_check"
    if (status != "extracted_needs_visual_check") {
      warning(document, ": ", status)
    }
    inventory[[i]] <- data.frame(
      document = document, path = path, md5 = unname(tools::md5sum(path)),
      pages = length(pages), raw_characters = nchar(text), status = status,
      extraction_error = error, split = split,
      metadata_excerpt = substr(gsub("[[:space:]]+", " ", text), 1L, 1500L),
      jurisdiction = "", government_level = "", source_type = "",
      authority_status = "not_verified", source_date = "", source_url = "",
      stringsAsFactors = FALSE
    )
    if (!is.na(sampled_index)) {
      for (p in seq_along(pages)) {
        writeLines(pages[p], file.path(output, "raw_pages",
                                      paste0(document, ".page", p, ".txt")))
      }
      if (!is.null(blocks)) {
        blocks$split <- split
        all_blocks[[length(all_blocks) + 1L]] <- blocks
      }
    }
  }
  inventory <- do.call(rbind, inventory)
  group <- match(extracted_fingerprints, unique(extracted_fingerprints))
  group_size <- tabulate(group)[group]
  inventory$exact_extracted_text_duplicate_group <- ifelse(
    group_size > 1L & nzchar(trimws(extracted_fingerprints)), as.character(group), ""
  )
  inventory$duplicate_check_scope <- "exact_normalized_text_only_not_near_templates"
  write_table(inventory, "document_inventory.csv")
  if (!length(all_blocks)) stop("No pilot passages extracted; inspect inventory.")
  passages <- do.call(rbind, all_blocks)
  passages$normalized <- normalize_search_text(passages$text)
  passages$exact_text_group <- match(passages$normalized, unique(passages$normalized))
  passages$exact_repeat_count <- tabulate(passages$exact_text_group)[passages$exact_text_group]
  passages$previous_context <- ""
  passages$next_context <- ""
  for (d in unique(passages$document)) {
    index <- which(passages$document == d)
    if (length(index) > 1L) {
      passages$previous_context[index[-1L]] <- passages$text[head(index, -1L)]
      passages$next_context[head(index, -1L)] <- passages$text[index[-1L]]
    }
  }
  candidates <- retrieve_candidates(passages, rules)
  candidates$review_relevance <- ""
  candidates$review_treatment <- ""
  candidates$review_force <- ""
  candidates$review_conditions <- ""
  candidates$review_actor <- ""
  candidates$review_notes <- ""
  write_table(passages, "pilot_passages.csv")
  write_table(candidates, "candidate_evidence.csv")
  write_table(inventory[inventory$split != "inventory_only", ], "pilot_sample.csv")
  review <- passages[, c("passage_id", "document", "split", "pdf_page",
                         "source_location", "section", "text")]
  for (category in rules$category) review[[category]] <- ""
  review$review_notes <- ""
  write_table(review, "full_read_review_template.csv")
  for (split in c("development", "validation")) {
    rows <- passages[passages$split == split, ]
    blocks <- vapply(seq_len(nrow(rows)), function(i) {
      paste0("\n", rows$passage_id[i], "\n", rows$source_location[i], "\n",
             rows$section[i], "\n", rows$text[i], "\n")
    }, character(1))
    writeLines(blocks, file.path(output, paste0(split, "_full_read.txt")))
  }
  # A category-level no-hit is a review status, never a claim of no protection.
  coverage <- expand.grid(document = inventory$document[inventory$split != "inventory_only"],
                          category = rules$category, stringsAsFactors = FALSE)
  coverage$candidate_count <- mapply(function(d, c) {
    sum(candidates$document == d & candidates$category == c)
  }, coverage$document, coverage$category)
  coverage$status <- ifelse(coverage$candidate_count > 0,
                            "candidate_requires_review", "no_hit_requires_audit")
  write_table(coverage, "retrieval_coverage.csv")
  capture.output(sessionInfo(), file = file.path(output, "session_info.txt"))
  cat("Inventoried", nrow(inventory), "PDFs; sampled", length(sampled),
      "; extracted", nrow(passages), "pilot passages;",
      nrow(candidates), "passage-category candidates.\n")
}

if (sys.nframe() == 0L) run_pilot(commandArgs(trailingOnly = TRUE))
