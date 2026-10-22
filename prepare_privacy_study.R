# Usage: Rscript prepare_privacy_study.R <PDF directory> <new output directory> [R library]
source("passage_pilot.R")
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2L) stop("Supply PDF and new output directories.")
if (length(args) >= 3L) .libPaths(c(args[3L], .libPaths()))
if (!requireNamespace("pdftools", quietly = TRUE)) stop("Missing pdftools.")
input <- normalizePath(args[1L], mustWork = TRUE)
out <- args[2L]
if (dir.exists(out) && length(list.files(out))) stop("Output must be new or empty.")
dir.create(out, recursive = TRUE, showWarnings = FALSE)
dir.create(file.path(out, "review"))
dir.create(file.path(out, "raw"))
write_table <- function(x, name) write.csv(x, file.path(out, name), row.names = FALSE, na = "")
rules <- search_rules("v2")
write_table(rules, "frozen_rules_v2.csv")
writeLines(unname(tools::md5sum(file.path(out, "frozen_rules_v2.csv"))),
           file.path(out, "rules_md5.txt"))
paths <- sort(list.files(input, pattern = "[.]pdf$", full.names = TRUE,
                         ignore.case = TRUE), method = "radix")
# Exclude both previously inspected pilots from the fresh quality sample.
set.seed(20261015)
old20 <- sample(paths, 20L)
set.seed(20261016)
old10 <- sample(paths, 10L)
set.seed(20261017)
fresh <- sample(setdiff(paths, union(old20, old10)), 6L)
inventory <- list()
blocks <- list()
raw_text <- list()
for (i in seq_along(paths)) {
  document <- basename(paths[i])
  pages <- pdftools::pdf_text(paths[i])
  if (!length(pages) || !nzchar(trimws(paste(pages, collapse = "")))) {
    stop("Unreadable PDF; explicit OCR review required: ", document)
  }
  b <- extract_blocks(pages, document)
  if (is.null(b) || any(b$extraction_status != "source_labeled")) {
    stop("Unrecognized excerpt format: ", document)
  }
  b$doc_id <- sprintf("D%03d", i)
  b$block <- seq_len(nrow(b))
  b$evidence_id <- paste0(b$doc_id, "-B", sprintf("%03d", b$block))
  blocks[[i]] <- b
  raw_text[[i]] <- paste(pages, collapse = "\n")
  writeLines(unlist(lapply(seq_along(pages), function(p) {
    c(paste("PDF EXCERPT PAGE", p), pages[p])
  })), file.path(out, "raw", paste0(b$doc_id[1L], ".txt")))
  inventory[[i]] <- data.frame(
    doc_id = b$doc_id[1L], document = document, path = paths[i],
    md5 = unname(tools::md5sum(paths[i])), pages = length(pages),
    body_characters = sum(nchar(b$text)), paragraphs = nrow(b),
    fresh_quality_sample = paths[i] %in% fresh,
    metadata_excerpt = substr(gsub("[[:space:]]+", " ", pages[1L]), 1L, 1700L),
    stringsAsFactors = FALSE
  )
}
inventory <- do.call(rbind, inventory)
passages <- do.call(rbind, blocks)
passages$previous_context <- ""
passages$next_context <- ""
for (id in inventory$doc_id) {
  ix <- which(passages$doc_id == id)
  if (length(ix) > 1L) {
    passages$previous_context[ix[-1L]] <- passages$text[head(ix, -1L)]
    passages$next_context[head(ix, -1L)] <- passages$text[ix[-1L]]
  }
}
candidates <- retrieve_candidates(passages, rules)
write_table(inventory, "inventory.csv")
write_table(passages, "passages.csv")
write_table(candidates, "retrieval_candidates.csv")
saveRDS(list(inventory = inventory, passages = passages, candidates = candidates,
             raw_text = raw_text), file.path(out, "corpus.rds"))
remaining <- inventory[!inventory$fresh_quality_sample, ]
# Balance text volume, without using themes or search hits.
loads <- rep(0L, 3L)
assignment <- integer(nrow(remaining))
for (i in order(remaining$body_characters, decreasing = TRUE)) {
  batch <- which.min(loads)
  assignment[i] <- batch
  loads[batch] <- loads[batch] + remaining$body_characters[i]
}
inventory$batch <- "fresh"
inventory$batch[!inventory$fresh_quality_sample] <- paste0("batch", assignment)
write_table(inventory, "inventory.csv")
for (batch in unique(inventory$batch)) {
  docs <- inventory[inventory$batch == batch, ]
  text <- unlist(lapply(seq_len(nrow(docs)), function(i) {
    d <- docs[i, ]
    b <- passages[passages$doc_id == d$doc_id, ]
    c(paste0("\n===== ", d$doc_id, " | ", d$document, " ====="),
      paste0("COMPILATION INTRO: ", d$metadata_excerpt),
      unlist(lapply(seq_len(nrow(b)), function(j) {
        c(paste0("\n", b$evidence_id[j], " | excerpt PDF page ", b$pdf_page[j],
                 " | ", b$source_location[j], " | ", b$section[j]), b$text[j])
      })))
  }))
  writeLines(text, file.path(out, "review", paste0(batch, ".txt")))
  write_table(docs, paste0("review/", batch, "_documents.csv"))
}
capture.output(sessionInfo(), file = file.path(out, "session_info.txt"))
print(aggregate(body_characters ~ batch, inventory, sum))
cat("Documents:", nrow(inventory), "paragraphs:", nrow(passages),
    "candidate pairs:", nrow(candidates), "\n")
