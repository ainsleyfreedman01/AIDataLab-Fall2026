"""
Builds analysis-ready text datasets from k12_ai_policies.csv.

Outputs:
  - policy_analysis_ready.csv: one row per policy with normalized text and corpus stats
  - policy_text_chunks.csv: one row per text chunk for sentiment/topic modeling
  - state_policy_summary.csv: state-level corpus summary metrics
  - policy_sentiment_lexicon_scores.csv: transparent first-pass lexicon scores

The goal is not to replace close reading. It is to remove PDF extraction noise,
make long documents manageable, and provide stable IDs/metadata for downstream
sentiment or text analysis.
"""

import csv
import math
import re
import sys
from collections import Counter, defaultdict

csv.field_size_limit(sys.maxsize)

POLICY_INPUT = "k12_ai_policies.csv"
ANALYSIS_OUTPUT = "policy_analysis_ready.csv"
CHUNKS_OUTPUT = "policy_text_chunks.csv"
STATE_SUMMARY_OUTPUT = "state_policy_summary.csv"
SENTIMENT_OUTPUT = "policy_sentiment_lexicon_scores.csv"

CHUNK_TARGET_WORDS = 750
CHUNK_OVERLAP_WORDS = 75

POSITIVE_TERMS = {
    "accessible", "accountable", "benefit", "benefits", "collaborate", "collaboration",
    "creative", "creativity", "effective", "efficient", "empower", "empowering", "enhance",
    "enhanced", "equitable", "equity", "ethical", "fair", "inclusive", "innovation",
    "innovative", "opportunity", "opportunities", "responsible", "safely", "safe", "support",
    "supported", "transparent", "trust", "trusted", "valuable",
}

NEGATIVE_TERMS = {
    "bias", "biased", "cheating", "concern", "concerns", "confidential", "discrimination",
    "error", "errors", "false", "harm", "harmful", "inaccurate", "misinformation",
    "plagiarism", "privacy", "prohibited", "risk", "risks", "unsafe", "violation",
    "violations", "warning", "wrong",
}

AI_TERMS = {
    "ai", "artificial", "intelligence", "generative", "genai", "chatgpt", "algorithm",
    "machine", "learning", "large", "language", "model", "models", "tool", "tools",
}

POLICY_TERMS = {
    "policy", "guidance", "guidelines", "guardrails", "privacy", "data", "integrity",
    "equity", "bias", "teacher", "student", "staff", "vendor", "procurement", "training",
}


def read_rows(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: str, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def normalize_text(text: str) -> str:
    text = text.replace("\ufeff", " ")
    text = text.replace("\u00a0", " ")
    text = text.replace("\uff0c", ",")
    text = text.replace("\u201d", '"')
    text = text.replace("\u201c", '"')
    text = text.replace("\u2019", "'")
    text = text.replace("\u2018", "'")
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "-")
    text = re.sub(r"https?://\S+", " URL ", text)
    text = re.sub(r"\b[\w.%-]+@[\w.-]+\.[A-Za-z]{2,}\b", " EMAIL ", text)
    text = re.sub(r"\.\s*\.\s*\.\s*\.+", " ", text)
    text = re.sub(r"(?m)^\s*\d+\s*$", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def analysis_text(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'\-]*", text.lower())


def sentence_count(text: str) -> int:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return len([s for s in sentences if len(s.strip()) > 10])


def lexicon_sentiment(tokens: list[str]) -> dict[str, str]:
    counts = Counter(tokens)
    positive = sum(counts[t] for t in POSITIVE_TERMS)
    negative = sum(counts[t] for t in NEGATIVE_TERMS)
    total = max(len(tokens), 1)
    score = (positive - negative) / math.sqrt(total)
    if score >= 0.75:
        label = "positive_policy_tone"
    elif score <= -0.75:
        label = "risk_or_constraint_heavy_tone"
    else:
        label = "mixed_or_neutral_policy_tone"
    return {
        "positive_term_count": str(positive),
        "negative_term_count": str(negative),
        "lexicon_sentiment_score": f"{score:.4f}",
        "lexicon_sentiment_label": label,
    }


def make_chunks(words: list[str], target_words: int, overlap_words: int) -> list[list[str]]:
    if not words:
        return []
    chunks = []
    step = max(1, target_words - overlap_words)
    for start in range(0, len(words), step):
        chunk = words[start:start + target_words]
        if chunk:
            chunks.append(chunk)
        if start + target_words >= len(words):
            break
    return chunks


def top_terms(tokens: list[str], vocabulary: set[str]) -> str:
    counts = Counter(t for t in tokens if t in vocabulary)
    return "; ".join(f"{term}:{count}" for term, count in counts.most_common(12))


def main() -> None:
    source_rows = read_rows(POLICY_INPUT)
    analysis_rows = []
    chunk_rows = []
    sentiment_rows = []

    for idx, row in enumerate(source_rows, start=1):
        policy_id = f"POL-{idx:03d}"
        normalized = normalize_text(row["full_text"])
        flat_text = analysis_text(row["full_text"])
        tokens = tokenize(flat_text)
        token_total = len(tokens)
        unique_total = len(set(tokens))
        sent_total = sentence_count(flat_text)
        ai_density = sum(1 for token in tokens if token in AI_TERMS) / max(token_total, 1)
        policy_density = sum(1 for token in tokens if token in POLICY_TERMS) / max(token_total, 1)
        sentiment = lexicon_sentiment(tokens)

        analysis_rows.append(
            {
                "policy_id": policy_id,
                "state": row["state"],
                "level": row["level"],
                "title": row["title"],
                "source_url": row["source_url"],
                "date_retrieved": row["date_retrieved"],
                "status": row["status"],
                "original_char_count": row["char_count"],
                "analysis_char_count": str(len(flat_text)),
                "word_count": str(token_total),
                "unique_word_count": str(unique_total),
                "sentence_count": str(sent_total),
                "ai_term_density": f"{ai_density:.5f}",
                "policy_term_density": f"{policy_density:.5f}",
                "top_ai_policy_terms": top_terms(tokens, AI_TERMS | POLICY_TERMS),
                "normalized_text": normalized,
                "analysis_text": flat_text,
            }
        )

        sentiment_rows.append(
            {
                "policy_id": policy_id,
                "state": row["state"],
                "level": row["level"],
                "title": row["title"],
                "word_count": str(token_total),
                **sentiment,
            }
        )

        words_for_chunks = flat_text.split()
        for chunk_idx, chunk in enumerate(make_chunks(words_for_chunks, CHUNK_TARGET_WORDS, CHUNK_OVERLAP_WORDS), start=1):
            chunk_text = " ".join(chunk)
            chunk_tokens = tokenize(chunk_text)
            chunk_sentiment = lexicon_sentiment(chunk_tokens)
            chunk_rows.append(
                {
                    "chunk_id": f"{policy_id}_CH{chunk_idx:03d}",
                    "policy_id": policy_id,
                    "chunk_index": str(chunk_idx),
                    "state": row["state"],
                    "level": row["level"],
                    "title": row["title"],
                    "chunk_word_count": str(len(chunk_tokens)),
                    "chunk_char_count": str(len(chunk_text)),
                    **chunk_sentiment,
                    "chunk_text": chunk_text,
                }
            )

    write_csv(
        ANALYSIS_OUTPUT,
        analysis_rows,
        [
            "policy_id", "state", "level", "title", "source_url", "date_retrieved", "status",
            "original_char_count", "analysis_char_count", "word_count", "unique_word_count",
            "sentence_count", "ai_term_density", "policy_term_density", "top_ai_policy_terms",
            "normalized_text", "analysis_text",
        ],
    )
    write_csv(
        CHUNKS_OUTPUT,
        chunk_rows,
        [
            "chunk_id", "policy_id", "chunk_index", "state", "level", "title",
            "chunk_word_count", "chunk_char_count", "positive_term_count",
            "negative_term_count", "lexicon_sentiment_score", "lexicon_sentiment_label",
            "chunk_text",
        ],
    )
    write_csv(
        SENTIMENT_OUTPUT,
        sentiment_rows,
        [
            "policy_id", "state", "level", "title", "word_count", "positive_term_count",
            "negative_term_count", "lexicon_sentiment_score", "lexicon_sentiment_label",
        ],
    )

    summary_by_state = defaultdict(lambda: Counter())
    sentiment_by_state = defaultdict(list)
    for row in analysis_rows:
        state = row["state"]
        summary_by_state[state]["policy_rows"] += 1
        summary_by_state[state]["district_rows"] += int(row["level"] == "district")
        summary_by_state[state]["state_rows"] += int(row["level"] == "state")
        summary_by_state[state]["word_count"] += int(row["word_count"])
    for row in sentiment_rows:
        sentiment_by_state[row["state"]].append(float(row["lexicon_sentiment_score"]))

    summary_rows = []
    for state in sorted(summary_by_state):
        values = summary_by_state[state]
        scores = sentiment_by_state[state]
        summary_rows.append(
            {
                "state": state,
                "policy_rows": str(values["policy_rows"]),
                "state_rows": str(values["state_rows"]),
                "district_rows": str(values["district_rows"]),
                "total_word_count": str(values["word_count"]),
                "avg_lexicon_sentiment_score": f"{(sum(scores) / len(scores)):.4f}" if scores else "0.0000",
            }
        )
    write_csv(
        STATE_SUMMARY_OUTPUT,
        summary_rows,
        ["state", "policy_rows", "state_rows", "district_rows", "total_word_count", "avg_lexicon_sentiment_score"],
    )

    print(f"Wrote {len(analysis_rows)} rows to {ANALYSIS_OUTPUT}")
    print(f"Wrote {len(chunk_rows)} rows to {CHUNKS_OUTPUT}")
    print(f"Wrote {len(sentiment_rows)} rows to {SENTIMENT_OUTPUT}")
    print(f"Wrote {len(summary_rows)} rows to {STATE_SUMMARY_OUTPUT}")


if __name__ == "__main__":
    main()
