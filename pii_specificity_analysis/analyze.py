"""Exploratory district-level comparison of PII specificity and AI data practices.

Run from anywhere:
  python pii_specificity_analysis/analyze.py
  python pii_specificity_analysis/analyze.py --root /path/to/AIDataLab-Fall2026

Does not edit upstream datasets. Writes only inside this analysis directory.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

GROUPS = ["0 types", "1-3 types", "4+ types"]
TOPICS = {
    "model_training": "Model training / improvement",
    "sharing_secondary_use": "Sharing / secondary use",
    "retention_deletion": "Retention / deletion",
}
BASE_SHA = "90bc32d737af8d8a9abdb11d78ca6257dc46c8f2"


def read_input(root: Path, relative: str, required: list[str]) -> pd.DataFrame:
    path = root / relative
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {relative}. Run from within the cloned AIDataLab-Fall2026 "
            "repository, or supply --root /path/to/repository."
        )
    data = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    missing = set(required) - set(data.columns)
    if missing:
        raise ValueError(f"{relative}: missing columns {sorted(missing)}")
    return data


def bool_col(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper().isin(["TRUE", "1", "YES"])


def group_label(n: int) -> str:
    if n == 0:
        return GROUPS[0]
    if n <= 3:
        return GROUPS[1]
    return GROUPS[2]


def build_district_data(root: Path):
    pii_docs = read_input(
        root, "PII and AI Tools/pii_and_tools_by_document.csv",
        ["level", "organization", "pdf_file", "doc_type", "pii_item_count"],
    )
    spectrum = read_input(
        root, "PII and AI Tools/pii_spectrum_by_organization.csv",
        ["organization", "level", "state", "pii_item_count"],
    )
    documents = read_input(
        root, "privacy_study/reviewed_documents.csv",
        ["doc_id", "document", "body_characters", "source_function"],
    )
    profiles = read_input(
        root, "privacy_study/provision_document_profiles.csv",
        ["doc_id", "category", "profile"],
    )
    categories = read_input(
        root, "privacy_study/document_category_matrix.csv",
        ["doc_id", "category", "explicit_content_found"],
    )

    if documents["document"].duplicated().any():
        raise ValueError("Duplicate PDF names in reviewed_documents: cannot safely match.")
    if spectrum.loc[spectrum["level"] == "district", "organization"].duplicated().any():
        raise ValueError("Duplicate organizations in district spectrum.")

    eligible_pii = pii_docs.loc[
        (pii_docs["level"] == "district") & pii_docs["pdf_file"].notna()
        & pii_docs["pdf_file"].astype(str).str.strip().ne("")
    ].copy()
    linked = eligible_pii.merge(
        documents[["doc_id", "document", "body_characters", "source_function"]],
        left_on="pdf_file", right_on="document", how="inner", validate="many_to_one"
    )
    if linked.empty:
        raise ValueError("Zero matching district PDFs. Check source file naming.")
    missing_matches = len(eligible_pii) - len(linked)

    # A profile appears only for a document that has already been positively
    # reviewed for the topic; absence is coded 'not located in supplied excerpt'.
    profiles = profiles.loc[profiles["category"].isin(
        ["model_training", "retention_deletion"]
    )].copy()
    profiles["has_direction"] = profiles["profile"].isin(["direction_only", "both"])
    pwide = (profiles.groupby(["doc_id", "category"])["has_direction"]
             .max().unstack(fill_value=False)
             .reindex(columns=["model_training", "retention_deletion"], fill_value=False)
             .rename(columns={
                 "model_training": "training_direction",
                 "retention_deletion": "retention_direction",
             }))
    linked = linked.join(pwide, on="doc_id")
    for key in ["training_direction", "retention_direction"]:
        linked[key] = linked[key].astype("boolean").fillna(False).astype(bool)

    categories = categories.loc[categories["category"].isin(TOPICS)].copy()
    categories["explicit"] = bool_col(categories["explicit_content_found"])
    cwide = (categories.groupby(["doc_id", "category"])["explicit"]
             .max().unstack(fill_value=False)
             .reindex(columns=list(TOPICS), fill_value=False)
             .rename(columns={topic: f"discusses_{topic}" for topic in TOPICS}))
    linked = linked.join(cwide, on="doc_id")
    for topic in TOPICS:
        key = f"discusses_{topic}"
        linked[key] = linked[key].astype("boolean").fillna(False).astype(bool)
    linked["body_characters"] = pd.to_numeric(
        linked["body_characters"], errors="coerce"
    ).fillna(0).astype(int)

    # Each school district counts once, even when it has multiple documents.
    district_docs = (linked.groupby("organization", as_index=False)
        .agg(document_count=("doc_id", "nunique"),
             max_excerpt_characters=("body_characters", "max"),
             training_direction=("training_direction", "any"),
             retention_direction=("retention_direction", "any"),
             discusses_model_training=("discusses_model_training", "any"),
             discusses_sharing_secondary_use=("discusses_sharing_secondary_use", "any"),
             discusses_retention_deletion=("discusses_retention_deletion", "any")))

    district_pii = spectrum.loc[
        spectrum["level"] == "district",
        ["organization", "state", "pii_item_count"]
    ].copy()
    district_pii["pii_item_count"] = pd.to_numeric(
        district_pii["pii_item_count"], errors="raise"
    ).astype(int)
    district = district_pii.merge(district_docs, on="organization", how="inner",
                                  validate="one_to_one")
    district["pii_group"] = pd.Categorical(
        district["pii_item_count"].map(group_label), categories=GROUPS, ordered=True
    )
    district["any_direction"] = (
        district["training_direction"] | district["retention_direction"]
    )
    district["excerpt_at_least_1000_chars"] = district["max_excerpt_characters"] >= 1000

    diagnostics = {
        "district_records_in_input": int((pii_docs["level"] == "district").sum()),
        "district_organizations_in_spectrum": len(district_pii),
        "district_documents_with_matching_excerpts": len(linked),
        "district_documents_unmatched_to_excerpts": missing_matches,
        "districts_in_final_analysis": len(district),
        "districts_with_1000_char_excerpt": int(district["excerpt_at_least_1000_chars"].sum()),
    }
    return district, linked, diagnostics


def summarize(district: pd.DataFrame) -> pd.DataFrame:
    grouped = (district.groupby("pii_group", observed=False)
        .agg(districts=("organization", "size"),
             with_any_direction=("any_direction", "sum"),
             with_training_direction=("training_direction", "sum"),
             with_retention_direction=("retention_direction", "sum"),
             discusses_training=("discusses_model_training", "sum"),
             discusses_sharing=("discusses_sharing_secondary_use", "sum"),
             discusses_retention=("discusses_retention_deletion", "sum"),
             n_with_long_excerpt=("excerpt_at_least_1000_chars", "sum"))
        .reset_index())
    for name in ["any_direction", "training_direction", "retention_direction"]:
        grouped[f"{name}_pct"] = (
            grouped[f"with_{name}"] / grouped["districts"].replace(0, np.nan) * 100
        ).round(1)
    for name in ["training", "sharing", "retention"]:
        grouped[f"discusses_{name}_pct"] = (
            grouped[f"discusses_{name}"] / grouped["districts"].replace(0, np.nan) * 100
        ).round(1)
    return grouped


def draw_direction_chart(summary: pd.DataFrame, destination: Path):
    rows = summary.set_index("pii_group").reindex(GROUPS)
    y = np.arange(len(GROUPS))
    fig, ax = plt.subplots(figsize=(9, 4.8))
    bars = ax.barh(y, rows["any_direction_pct"].fillna(0), height=.55)
    for i, (bar, (_, row)) in enumerate(zip(bars, rows.iterrows())):
        ax.text(bar.get_width() + .65, i,
                f"{row['any_direction_pct']:.1f}%   ({int(row['with_any_direction'])}/{int(row['districts'])})",
                va="center", fontsize=10)
    ax.set_yticks(y, ["No named PII types", "1–3 named types", "4+ named types"])
    ax.invert_yaxis()
    ax.set_xlim(0, max(32, float(rows["any_direction_pct"].max()) + 10))
    ax.set_xlabel("Share of districts with training or retention/deletion direction (%)")
    ax.set_title("PII specificity and downstream data-use guidance", fontsize=13, pad=15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", alpha=.15)
    ax.set_axisbelow(True)
    fig.text(.09, .015,
             "Exploratory excerpt coding; a direction may be nonbinding. Not a measure of privacy compliance.",
             fontsize=8)
    fig.tight_layout(rect=[0, .065, 1, 1])
    fig.savefig(destination, dpi=180)
    plt.close(fig)


def draw_topics_chart(summary: pd.DataFrame, destination: Path):
    rows = summary.set_index("pii_group").reindex(GROUPS)
    x = np.arange(len(GROUPS))
    fig, ax = plt.subplots(figsize=(9.4, 5.2))
    width = .23
    for i, (column, name) in enumerate([
        ("discusses_training_pct", "Model training"),
        ("discusses_sharing_pct", "Sharing / secondary use"),
        ("discusses_retention_pct", "Retention / deletion"),
    ]):
        ax.bar(x + (i-1)*width, rows[column].fillna(0), width, label=name)
    ax.set_xticks(x, ["0 named types", "1–3 named types", "4+ named types"])
    ax.set_ylabel("Districts with explicit discussion in supplied excerpts (%)")
    ax.set_title("Which downstream privacy topics are discussed?", fontsize=13, pad=13)
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.12), ncol=3, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(0, max(65, float(rows[[
        "discusses_training_pct", "discusses_sharing_pct", "discusses_retention_pct"
    ]].max().max()) + 8))
    ax.grid(axis="y", alpha=.15)
    ax.set_axisbelow(True)
    fig.text(.09, .01, "Discussion includes review questions and warnings, not necessarily enforceable rules.",
             fontsize=8)
    fig.tight_layout(rect=[0, .06, 1, 1])
    fig.savefig(destination, dpi=180, bbox_inches="tight")
    plt.close(fig)



def draw_length_sensitivity_chart(summary: pd.DataFrame, long_summary: pd.DataFrame,
                                  destination: Path):
    full = summary.set_index("pii_group").reindex(GROUPS)
    longer = long_summary.set_index("pii_group").reindex(GROUPS)
    x = np.arange(len(GROUPS))
    width = .34
    fig, ax = plt.subplots(figsize=(9, 5.3))
    bars_full = ax.bar(x - width / 2, full["any_direction_pct"], width,
                       label="All matching excerpts")
    bars_long = ax.bar(x + width / 2, longer["any_direction_pct"], width,
                       label="At least one 1,000+ character excerpt")
    for bars, frame in [(bars_full, full), (bars_long, longer)]:
        for bar, (_, row) in zip(bars, frame.iterrows()):
            if not pd.isna(row["any_direction_pct"]):
                ax.annotate(f"{row['any_direction_pct']:.1f}%",
                            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                            xytext=(0, 4), textcoords="offset points",
                            ha="center", fontsize=9)
    ax.set_xticks(x, ["0 named types", "1–3 named types", "4+ named types"])
    ax.set_ylabel("Districts with training or retention/deletion direction (%)")
    ax.set_ylim(0, max(35, float(pd.concat([full["any_direction_pct"],
                                            longer["any_direction_pct"]]).max()) + 7))
    ax.set_title("Does the PII-specificity pattern persist in longer excerpts?", fontsize=12)
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.12), ncol=2, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=.15)
    ax.set_axisbelow(True)
    fig.text(.07, .015, "Exploratory length-based sensitivity check, not a causal adjustment. Different group denominators.",
             fontsize=8)
    fig.tight_layout(rect=[0, .06, 1, 1])
    fig.savefig(destination, dpi=180, bbox_inches="tight")
    plt.close(fig)

def make_audit_queue(root: Path, district: pd.DataFrame,
                     linked: pd.DataFrame, output: Path):
    # Select original quotations for manual review; do NOT label them verified.
    atomic_path = root / "privacy_study/atomic_provisions.csv"
    if not atomic_path.exists():
        return 0
    atomic = pd.read_csv(atomic_path, encoding="utf-8-sig", low_memory=False)
    required = {"doc_id", "category", "quotation", "source_location",
                "provision_id", "included_in_primary_comparison"}
    if not required.issubset(atomic.columns):
        return 0
    evidence = atomic.loc[
        bool_col(atomic["included_in_primary_comparison"])
    ].copy()
    mapping = linked[["doc_id", "organization"]].drop_duplicates()
    evidence = evidence.merge(mapping, on="doc_id", how="inner")
    evidence = evidence.merge(
        district[["organization", "pii_group"]], on="organization", how="inner"
    )
    if evidence.empty:
        return 0
    # Repeatable, stratified sample, at most five provisions from each group.
    evidence = evidence.sample(frac=1, random_state=42)
    evidence = (evidence.groupby("pii_group", observed=True, group_keys=False)
                .head(5).sort_values(["pii_group", "organization", "provision_id"]))
    keep = ["pii_group", "organization", "doc_id", "provision_id", "category",
            "source_location", "quotation"]
    result = evidence[keep].copy()
    result["human_verified_against_original_source"] = ""
    result["coding_accurate"] = ""
    result["reviewer_notes"] = ""
    result.to_csv(output, index=False, encoding="utf-8-sig")
    return len(result)


def report(summary: pd.DataFrame, diagnostics: dict, long_summary: pd.DataFrame,
           audit_rows: int, path: Path):
    lines = [
        "# Exploratory Findings — PII Specificity and Downstream Guidance", "",
        f"Source repo revision: `{BASE_SHA}` (baseline from 2026-10-29).", "",
        "## Research question", "",
        "Are districts that identify more categories of personal information in AI privacy excerpts",
        "also more likely to include directions about AI model training or data retention/deletion?", "",
        "## Comparison", "",
        "| PII categories named | Districts | Any direction | Training direction | Retention/deletion direction |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, r in summary.iterrows():
        lines.append(f"| {r['pii_group']} | {int(r['districts'])} | "
                     f"{int(r['with_any_direction'])}/{int(r['districts'])} "
                     f"({r['any_direction_pct']:.1f}%) | "
                     f"{int(r['with_training_direction'])} | "
                     f"{int(r['with_retention_direction'])} |")
    total = summary[["districts", "with_any_direction"]].sum()
    lines += [
        "", f"Matched {diagnostics['districts_in_final_analysis']} districts across "
            f"{diagnostics['district_documents_with_matching_excerpts']} district privacy excerpts.",
        f"The organization-level PII spectrum contains {diagnostics['district_organizations_in_spectrum']} "
        "districts with coded privacy excerpts; document-level source data also include",
        "districts without matching excerpts, which cannot be included in this comparison.",
        "", "## Interpretation", "",
        "Compare the group rates as exploratory descriptive summaries; do not assume that a",
        "larger number of named PII categories implies more effective privacy safeguards.",
        "The analysis does not establish statistical significance, causality, implemented",
        "protections, or legal quality.",
        "The relationship may reflect excerpt length, source type, selection, and coding differences.",
        "", "## Excerpt-length sensitivity", "",
        "A district is included below if at least one matching privacy excerpt contains 1,000+",
        "body-text characters. PII specificity still comes from the district-level summary of its",
        "available documents; this is a descriptive coverage check, not a causal adjustment.", "",
        "| PII categories named | Districts with longer excerpt | Any direction |",
        "|---|---:|---:|",
    ]
    for _, r in long_summary.iterrows():
        lines.append(f"| {r['pii_group']} | {int(r['districts'])} | "
                     f"{int(r['with_any_direction'])}/{int(r['districts'])} "
                     f"({r['any_direction_pct']:.1f}%) |")
    full_rates = summary.set_index("pii_group")["any_direction_pct"].dropna()
    long_rates = long_summary.loc[
        long_summary["districts"] > 0
    ].set_index("pii_group")["any_direction_pct"].dropna()
    if len(full_rates) == len(GROUPS) and len(long_rates) == len(GROUPS):
        full_spread = float(full_rates.max() - full_rates.min())
        long_spread = float(long_rates.max() - long_rates.min())
        lines += [
            "", f"Across PII groups, the range of observed rates is {full_spread:.1f} percentage points",
            f"in the full matched sample and {long_spread:.1f} points in the longer-excerpt subset.",
            "This is a **sensitivity check**, not proof that length causes the pattern to change.",
        ]
    lines += [
        "", "## Recommended independent validation", "",
        f"An audit sample of {audit_rows} included atomic provisions was exported to",
        "`results/manual_review_queue.csv`. Open the original sources, check quotation and context,",
        "then record your decision in the empty reviewer columns. This has **not** been done yet.",
        "", "## Definitions and limitations", "",
        "- Unit of analysis is **distinct district**; state guidance is excluded.",
        "- PII specificity = count of named PII categories in the existing organization summary,",
        "  grouped into 0, 1–3, or 4+ categories. This is not privacy quality.",
        "- `direction` means the existing atomic-provision profile is `direction_only` or `both`",
        "  for **model_training** or **retention_deletion**. It may be recommended, not mandatory.",
        "- The three 'discusses' outcomes use `explicit_content_found` for training, sharing,",
        "  and retention. They are **topic mentions**, not implemented protections.",
        "- Missing profile/topic content means not located in the *reviewed excerpt*, not absent",
        "  from the full policy or actual district practice.",
        "- Some districts have multiple documents; aggregation uses `any` per district.",
        "- AI-assisted upstream coding lacks independent human reliability checks, and excerpt",
        "  authenticity, currency, completeness, and policy adoption have not been verified.",
        "- Avoid causal claims, significance claims, policy-strength rankings, or national generalizations.",
        "", "## Files", "",
        "- `results/district_level.csv`: one row per included district.",
        "- `results/group_summary.csv`: one row per PII group; counts and percentages.",
        "- `results/long_excerpt_summary.csv`: length-based sensitivity check.",
        "- `results/manual_review_queue.csv`: quotations requiring original-source validation.",
        "- `figures/pii_vs_directions.png`: main visualization.",
        "- `figures/pii_vs_topics.png`: explicit discussion by topic.",
        "- `figures/pii_vs_excerpt_length.png`: full-sample vs. longer-excerpt sensitivity.",
        "", "## Data and provenance", "",
        "Data from the `AIDataLab-Fall2026` repository, with no scraping or changes to upstream",
        "sources in this folder. Do not treat this exploratory output as an independent policy audit.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="Path to AIDataLab-Fall2026 repo (default: parent of script directory)")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    out = Path(__file__).resolve().parent
    result_folder = out / "results"
    figure_folder = out / "figures"
    result_folder.mkdir(exist_ok=True)
    figure_folder.mkdir(exist_ok=True)
    district, linked, diagnostics = build_district_data(root)
    group_summary = summarize(district)
    long_summary = summarize(district.loc[district["excerpt_at_least_1000_chars"]])
    district.sort_values(["pii_group", "organization"]).to_csv(
        result_folder / "district_level.csv", index=False, encoding="utf-8-sig"
    )
    group_summary.to_csv(result_folder / "group_summary.csv", index=False)
    long_summary.to_csv(result_folder / "long_excerpt_summary.csv", index=False)
    audit_rows = make_audit_queue(root, district, linked,
                                 result_folder / "manual_review_queue.csv")
    draw_direction_chart(group_summary, figure_folder / "pii_vs_directions.png")
    draw_topics_chart(group_summary, figure_folder / "pii_vs_topics.png")
    draw_length_sensitivity_chart(group_summary, long_summary,
                                  figure_folder / "pii_vs_excerpt_length.png")
    report(group_summary, diagnostics, long_summary, audit_rows, out / "FINDINGS.md")
    print("Data coverage:", diagnostics)
    print("\n" + group_summary.to_string(index=False))
    print(f"\nGenerated files in {out}")


if __name__ == "__main__":
    main()
