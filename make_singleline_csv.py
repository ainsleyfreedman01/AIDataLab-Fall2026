"""
Creates a single-line-per-record companion CSV from k12_ai_policies.csv.

Line-based CSV syntax highlighters/extensions (e.g. Rainbow CSV, and the
generic "Prettier"-style coloring VS Code applies to .csv) assume one record
= one physical line. They don't parse RFC4180 quoting, so a full_text field
with real embedded newlines (the multi-line version) breaks their column
detection and they fall back to plain string highlighting. This script
flattens full_text back to a single line so those extensions can render a
proper colored table again, without touching the original multi-line file.

Usage: python3 make_singleline_csv.py
Output: k12_ai_policies_singleline.csv
"""

import csv
import re
import sys

csv.field_size_limit(sys.maxsize)

SRC = "k12_ai_policies.csv"
DST = "k12_ai_policies_singleline.csv"


def main() -> None:
    with open(SRC, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    for row in rows:
        row["full_text"] = re.sub(r"\s+", " ", row["full_text"]).strip()

    with open(DST, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} single-line rows to {DST}")


if __name__ == "__main__":
    main()
