# Usage: Rscript topic_model_pilot.R <PDF directory> <output directory> [R library]
args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2L) {
  stop("Supply a PDF directory and an output directory; optionally supply an R library.")
}
if (length(args) >= 3L) .libPaths(c(args[3L], .libPaths()))
for (package in c("pdftools", "quanteda", "topicmodels")) {
  if (!requireNamespace(package, quietly = TRUE)) {
    stop("Missing R package: ", package)
  }
}

input <- normalizePath(args[1L], mustWork = TRUE)
output <- args[2L]
dir.create(output, recursive = TRUE, showWarnings = FALSE)
if (!dir.exists(output)) stop("Cannot create output directory.")
write_table <- function(x, name) {
  write.csv(x, file.path(output, name), row.names = FALSE, na = "")
}

paths <- sort(list.files(input, pattern = "[.]pdf$", full.names = TRUE,
                         ignore.case = TRUE), method = "radix")
if (length(paths) < 20L) stop("The pilot requires at least 20 PDFs.")
set.seed(20261015)
paths <- sort(sample(paths, 20L), method = "radix")
ids <- basename(paths)
pages <- lapply(paths, pdftools::pdf_text)
raw_text <- vapply(pages, paste, character(1), collapse = "\n")

# These excerpt PDFs include editorial introductions and source-location labels.
# Retain the original extraction separately so cleaning can be audited.
clean_excerpt <- function(text) {
  lines <- strsplit(text, "\n", fixed = TRUE)[[1L]]
  source_lines <- grep("^\\s*Source:", lines)
  if (!length(source_lines)) stop("No source labels found; inspect PDF format.")
  remove <- seq_len(source_lines[1L])
  for (i in source_lines) {
    remove <- c(remove, i)
    if (i > source_lines[1L]) {
      j <- i - 1L
      while (j > 0L && nzchar(trimws(lines[j]))) {
        remove <- c(remove, j)
        j <- j - 1L
      }
    }
  }
  text <- paste(lines[-unique(remove)], collapse = "\n")
  text <- gsub("[[]graphic[]]", "", text)
  if (!nzchar(trimws(text))) stop("Cleaning left an empty excerpt.")
  text
}
cleaned <- vapply(raw_text, clean_excerpt, character(1))
names(cleaned) <- ids
for (i in seq_along(ids)) {
  writeLines(raw_text[i], file.path(output, paste0(ids[i], ".raw.txt")))
  writeLines(cleaned[i], file.path(output, paste0(ids[i], ".clean.txt")))
}

tokens <- quanteda::tokens(cleaned, remove_punct = TRUE, remove_numbers = TRUE,
                           remove_symbols = TRUE, remove_url = TRUE,
                           split_hyphens = TRUE)
tokens <- quanteda::tokens_tolower(tokens)
tokens <- quanteda::tokens_remove(tokens, quanteda::stopwords("en"))
tokens <- quanteda::tokens_select(tokens, pattern = "^[a-z]{3,}$",
                                  valuetype = "regex", selection = "keep")
counts <- quanteda::dfm(tokens)
# Keep words appearing in at least two sampled documents, without stemming.
counts <- quanteda::dfm_trim(counts, min_docfreq = 2L, docfreq_type = "count")
if (any(quanteda::ntoken(counts) < 10L)) {
  stop("A sampled PDF has fewer than 10 retained tokens; inspect extraction and trimming.")
}
if (quanteda::nfeat(counts) < 30L) stop("Too few shared terms for a useful pilot.")
dtm <- quanteda::convert(counts, to = "topicmodels")
manifest <- data.frame(
  document = ids, path = paths, pages = lengths(pages),
  raw_characters = nchar(raw_text), clean_characters = nchar(cleaned),
  tokens_before_frequency_filter = quanteda::ntoken(quanteda::dfm(tokens)),
  retained_tokens = quanteda::ntoken(counts),
  md5 = unname(tools::md5sum(paths))
)
write_table(manifest, "sample_manifest.csv")
write_table(data.frame(term = quanteda::featnames(counts),
                       count = quanteda::featfreq(counts),
                       document_frequency = quanteda::docfreq(counts)),
            "vocabulary.csv")

permutations <- function(x) {
  if (length(x) == 1L) return(matrix(x, nrow = 1L))
  do.call(rbind, lapply(seq_along(x), function(i) {
    cbind(x[i], permutations(x[-i]))
  }))
}
topic_overlap <- function(a, b) {
  k <- ncol(a)
  similarities <- matrix(0, k, k)
  for (i in seq_len(k)) for (j in seq_len(k)) {
    similarities[i, j] <- length(intersect(a[, i], b[, j])) /
      length(union(a[, i], b[, j]))
  }
  assignments <- permutations(seq_len(k))
  max(apply(assignments, 1L, function(p) {
    mean(similarities[cbind(seq_len(k), p)])
  }))
}

metrics <- list()
top_rows <- list()
representatives <- list()
seeds <- c(20261015L, 20261016L, 20261017L)
for (k in 2:4) {
  fits <- lapply(seeds, function(seed) {
    topicmodels::LDA(dtm, k = k, method = "Gibbs",
                     control = list(seed = seed, burnin = 500L,
                                    iter = 1500L, thin = 50L))
  })
  top_sets <- lapply(fits, topicmodels::terms, k = 10L)
  pairs <- combn(seq_along(seeds), 2L)
  overlaps <- apply(pairs, 2L, function(pair) {
    topic_overlap(top_sets[[pair[1L]]], top_sets[[pair[2L]]])
  })
  metrics[[length(metrics) + 1L]] <- data.frame(
    topics = k, mean_aligned_top10_jaccard = mean(overlaps),
    min_aligned_top10_jaccard = min(overlaps),
    training_perplexity_first_seed = topicmodels::perplexity(fits[[1L]], dtm)
  )
  for (run in seq_along(fits)) {
    fit <- fits[[run]]
    posterior <- topicmodels::posterior(fit)
    for (topic in seq_len(k)) {
      indexes <- order(posterior$terms[topic, ], decreasing = TRUE)[1:12]
      top_rows[[length(top_rows) + 1L]] <- data.frame(
        topics = k, seed = seeds[run], topic = topic, rank = 1:12,
        term = colnames(posterior$terms)[indexes],
        probability = posterior$terms[topic, indexes]
      )
    }
  }
  # Use the first seed consistently for figures, not the most attractive run.
  posterior <- topicmodels::posterior(fits[[1L]])
  proportions <- posterior$topics
  write_table(data.frame(document = rownames(proportions), proportions),
              paste0("document_topics_k", k, ".csv"))
  saveRDS(fits, file.path(output, paste0("models_k", k, ".rds")))
  for (topic in seq_len(k)) {
    indexes <- order(proportions[, topic], decreasing = TRUE)[1:3]
    representatives[[length(representatives) + 1L]] <- data.frame(
      topics = k, topic = topic, rank = 1:3, document = ids[indexes],
      topic_proportion = proportions[indexes, topic],
      cleaned_excerpt = unname(cleaned[indexes])
    )
  }
  labels <- sub("_Privacy_Passages[.]pdf$", "", ids)
  labels <- gsub("_", " ", labels, fixed = TRUE)
  png(file.path(output, paste0("topic_proportions_k", k, ".png")),
      width = 1800, height = 1200, res = 150)
  par(mar = c(5, 24, 4, 2))
  barplot(t(proportions), horiz = TRUE, names.arg = labels, las = 1,
          col = c("#4477AA", "#EE6677", "#228833", "#CCBB44")[seq_len(k)],
          border = NA, cex.names = 0.65, xlab = "Model-estimated topic proportion",
          main = paste("Exploratory PDF pilot:", k, "topics"),
          legend.text = paste("Topic", seq_len(k)),
          args.legend = list(x = "bottomright", cex = 0.7))
  dev.off()
}
write_table(do.call(rbind, metrics), "model_diagnostics.csv")
write_table(do.call(rbind, top_rows), "topic_terms_all_runs.csv")
write_table(do.call(rbind, representatives), "representative_excerpts.csv")
capture.output(sessionInfo(), file = file.path(output, "session_info.txt"))
writeLines(c(
  "Exploratory pilot only: 20 sampled PDF files; no CSV policy text used.",
  "Sampling seed: 20261015; model seeds: 20261015, 20261016, 20261017.",
  "One PDF = one modeling document. PDF format does not imply binding policy.",
  "Editorial introductions, source labels, and associated section headings removed.",
  "Lowercase alphabetic tokens >=3 characters; English stopwords removed.",
  "Terms must occur in >=2 pilot documents. No stemming or custom topical stopwords.",
  "Gibbs LDA: k=2,3,4; burnin=500; iter=1500; thin=50.",
  "Figures and representative documents always use the first seed.",
  "Stability: mean top-10 Jaccard after optimal one-to-one topic alignment.",
  "Perplexity is in-sample, not held-out validation or a policy-quality measure.",
  "Topic labels require human interpretation; document representatives are not sentence attributions.",
  "Inspect short documents, template overlap, names, and legal boilerplate before scaling.",
  "A full-corpus refit may change topics; pilot labels are not fixed categories."
), file.path(output, "method.txt"))
stopifnot(nrow(manifest) == 20L, all(file.exists(paths)),
          all(abs(rowSums(proportions) - 1) < 1e-8))
print(do.call(rbind, metrics))
cat("\nPilot outputs:", normalizePath(output), "\n")
