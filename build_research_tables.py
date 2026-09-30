"""
Builds research companion tables for comparing K-12 AI policy in states with
prominent AI development ecosystems.

Inputs:
  - k12_ai_policies.csv

Outputs:
  - ai_ecosystem_metadata.csv
  - state_comparison_matrix.csv
  - policy_coding_template.csv
"""

import csv
import re
import sys
from collections import Counter, defaultdict

csv.field_size_limit(sys.maxsize)

POLICY_INPUT = "k12_ai_policies.csv"
ECOSYSTEM_OUTPUT = "ai_ecosystem_metadata.csv"
STATE_MATRIX_OUTPUT = "state_comparison_matrix.csv"
CODING_TEMPLATE_OUTPUT = "policy_coding_template.csv"

ECOSYSTEM_ROWS = [
    {
        "state": "California",
        "ai_development_tier": "highest",
        "major_ai_hubs": "San Francisco Bay Area; Silicon Valley; Los Angeles; San Diego",
        "major_institutions": "Stanford; UC Berkeley; UCLA; UC San Diego; Caltech",
        "major_companies_or_labs": "OpenAI; Anthropic; Google DeepMind; Meta; NVIDIA; Apple; Scale AI; Perplexity",
        "ecosystem_rationale": "California is the strongest US AI production hub, with leading frontier labs, compute firms, venture capital, and university research concentrated in the Bay Area and Southern California.",
        "comparison_role": "Benchmark for a mature AI industry state with formal state-level K-12 guidance and district implementation pressure.",
    },
    {
        "state": "Washington",
        "ai_development_tier": "highest",
        "major_ai_hubs": "Seattle; Bellevue; Redmond",
        "major_institutions": "University of Washington; Allen Institute for AI",
        "major_companies_or_labs": "Microsoft; Amazon; AI2; Google Seattle; Meta Seattle",
        "ecosystem_rationale": "Washington has a dense cloud and AI platform ecosystem anchored by Microsoft, Amazon, and AI2, plus unusually strong state education guidance through OSPI.",
        "comparison_role": "Cloud/platform AI state with comparatively advanced statewide K-12 AI guidance and multiple district handbooks.",
    },
    {
        "state": "Texas",
        "ai_development_tier": "high",
        "major_ai_hubs": "Austin; Dallas-Fort Worth; Houston; San Antonio",
        "major_institutions": "University of Texas at Austin; Texas A&M; Rice; UT Dallas; TACC",
        "major_companies_or_labs": "Tesla; Oracle Austin; Dell; IBM Austin; NVIDIA Austin; many defense, energy, and enterprise AI firms",
        "ecosystem_rationale": "Texas combines fast-growing tech hubs, high-performance computing at TACC, AI task-force activity, and large urban school systems beginning to publish AI guidance.",
        "comparison_role": "Fast-growth AI ecosystem with policy experimentation at task-force and district levels.",
    },
    {
        "state": "New York",
        "ai_development_tier": "high",
        "major_ai_hubs": "New York City; Albany; Rochester; Buffalo",
        "major_institutions": "NYU; Columbia; Cornell Tech; RPI; University at Buffalo; Rochester Institute of Technology",
        "major_companies_or_labs": "IBM Research; Google NYC; Meta NYC; Bloomberg AI; Hugging Face NYC; many finance and media AI firms",
        "ecosystem_rationale": "New York is a major applied AI hub in finance, media, enterprise software, and research, with NYC Public Schools offering a large urban K-12 comparator.",
        "comparison_role": "Large applied-AI economy and large urban school district policy response.",
    },
    {
        "state": "Massachusetts",
        "ai_development_tier": "high",
        "major_ai_hubs": "Boston; Cambridge; Route 128 corridor",
        "major_institutions": "MIT; Harvard; Northeastern; Boston University; UMass Amherst; WPI",
        "major_companies_or_labs": "IBM Research Cambridge; Google Cambridge; Microsoft Research New England; Boston Dynamics; many biotech and robotics AI firms",
        "ecosystem_rationale": "Massachusetts is one of the country's strongest AI research ecosystems, with elite universities, robotics, healthcare AI, and edtech activity.",
        "comparison_role": "Research-intensive AI state with detailed state education guidance and district policy from Boston.",
    },
    {
        "state": "Georgia",
        "ai_development_tier": "emerging-high",
        "major_ai_hubs": "Atlanta; Midtown Atlanta; Technology Square; Alpharetta",
        "major_institutions": "Georgia Tech; Emory; Georgia State; University of Georgia; Morehouse; Spelman",
        "major_companies_or_labs": "Google Atlanta; Microsoft Atlanta; NCR Voyix; Home Depot tech; Mailchimp; Cox; fintech, logistics, and health AI firms",
        "ecosystem_rationale": "Georgia is an emerging AI hub anchored by Atlanta, Georgia Tech, corporate technology operations, fintech, logistics, and health systems, but with a less mature public K-12 AI policy ecosystem than California or Washington.",
        "comparison_role": "Primary focal case: emerging AI hub with state guidance and early district-level positioning.",
    },
    {
        "state": "Pennsylvania",
        "ai_development_tier": "high-specialized",
        "major_ai_hubs": "Pittsburgh; Philadelphia; State College",
        "major_institutions": "Carnegie Mellon; University of Pennsylvania; Penn State; University of Pittsburgh; Drexel",
        "major_companies_or_labs": "Duolingo; Aurora; Google Pittsburgh; robotics and autonomous systems firms; healthcare AI firms",
        "ecosystem_rationale": "Pennsylvania is especially strong in robotics, autonomy, and AI research through CMU and related Pittsburgh/Philadelphia ecosystems, while K-12 policy guidance remains more fragmented.",
        "comparison_role": "AI research/autonomy state with mixed state and district policy signals.",
    },
]

CODING_FIELDS = [
    "policy_id",
    "state",
    "level",
    "title",
    "source_url",
    "char_count",
    "policy_type",
    "policy_maturity",
    "student_use_position",
    "teacher_staff_use_position",
    "privacy_data_rules",
    "academic_integrity_rules",
    "equity_access_language",
    "procurement_vendor_review",
    "ai_detection_position",
    "professional_learning_support",
    "implementation_specificity",
    "evidence_quote",
    "analytic_notes",
]


def infer_policy_type(row: dict[str, str]) -> str:
    title = row["title"].lower()
    if "guidebook" in title or "handbook" in title:
        return "guidebook_or_handbook"
    if "policy" in title:
        return "policy"
    if "guidance" in title or "guidelines" in title:
        return "guidance"
    if "resources" in title:
        return "resource_page"
    if "position statement" in title:
        return "position_statement"
    if "task force" in title or "report" in title or "whitepaper" in title:
        return "task_force_or_report"
    return "other"


def infer_policy_maturity(row: dict[str, str]) -> str:
    level = row["level"]
    policy_type = infer_policy_type(row)
    if "model policy" in row["title"].lower():
        return "model_policy_nonbinding"
    if policy_type == "policy":
        return "adopted_or_formal_policy"
    if policy_type == "guidebook_or_handbook":
        return "implementation_handbook"
    if level == "state" and policy_type == "guidance":
        return "state_guidance"
    if policy_type == "position_statement":
        return "position_statement"
    if policy_type == "resource_page":
        return "resource_or_support_page"
    if policy_type == "task_force_or_report":
        return "research_or_recommendation_report"
    return "needs_review"


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def extract_evidence(text: str, terms: list[str], max_len: int = 280) -> str:
    lowered = text.lower()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    if not positions:
        return ""
    pos = min(positions)
    start = max(0, pos - 90)
    end = min(len(text), pos + max_len - 90)
    snippet = re.sub(r"\s+", " ", text[start:end]).strip()
    return snippet


def code_student_use(text: str) -> str:
    lower = text.lower()
    if has_any(lower, ["student use", "students may", "students can", "learners", "student learning", "assignments"]):
        if has_any(lower, ["with teacher permission", "teacher permission", "authorized", "appropriate use", "responsible use", "human-centered", "guardrails"]):
            return "allowed_with_guardrails"
        return "discusses_student_use"
    if has_any(lower, ["prohibit", "ban", "not permitted"]):
        return "restrictive_or_prohibitive"
    return "not_clearly_addressed"


def code_staff_use(text: str) -> str:
    lower = text.lower()
    if has_any(lower, ["educators", "teachers", "staff", "school leaders", "administrators"]):
        if has_any(lower, ["professional", "lesson", "planning", "draft", "feedback", "administrative"]):
            return "staff_use_supported_with_guidance"
        return "staff_use_discussed"
    return "not_clearly_addressed"


def code_presence(text: str, terms: list[str]) -> str:
    return "present" if has_any(text.lower(), terms) else "not_clearly_addressed"


def code_ai_detection(text: str) -> str:
    lower = text.lower()
    if has_any(lower, ["ai detection", "detection tools", "detector", "detect ai", "turnitin"]):
        if has_any(lower, ["limitations", "unreliable", "not solely", "caution", "false positive"]):
            return "cautions_against_overreliance"
        return "discusses_detection_tools"
    return "not_clearly_addressed"


def code_implementation_specificity(row: dict[str, str], text: str) -> str:
    lower = text.lower()
    score = 0
    for terms in [
        ["policy", "procedure", "guideline"],
        ["professional learning", "training", "development"],
        ["privacy", "data", "confidential"],
        ["academic integrity", "plagiarism", "citation"],
        ["procurement", "vendor", "approved tool"],
    ]:
        if has_any(lower, terms):
            score += 1
    maturity = infer_policy_maturity(row)
    if maturity in {"implementation_handbook", "adopted_or_formal_policy"} and score >= 4:
        return "high"
    if score >= 3:
        return "moderate"
    if score >= 1:
        return "low"
    return "minimal"


def code_policy_row(row: dict[str, str]) -> dict[str, str]:
    text = row.get("full_text", "")
    lower = text.lower()
    evidence_terms = [
        "student", "teacher", "privacy", "data", "academic integrity",
        "equity", "procurement", "vendor", "ai detection", "professional learning",
    ]
    return {
        "student_use_position": code_student_use(text),
        "teacher_staff_use_position": code_staff_use(text),
        "privacy_data_rules": code_presence(text, ["privacy", "confidential", "data", "personally identifiable", "ferpa", "student information"]),
        "academic_integrity_rules": code_presence(text, ["academic integrity", "plagiarism", "cheating", "citation", "authorship", "student work"]),
        "equity_access_language": code_presence(text, ["equity", "equitable", "access", "inclusive", "bias", "disability", "multilingual"]),
        "procurement_vendor_review": code_presence(text, ["procurement", "vendor", "approved tool", "approved ai", "contract", "terms of service", "security review"]),
        "ai_detection_position": code_ai_detection(text),
        "professional_learning_support": code_presence(text, ["professional learning", "professional development", "training", "educator learning", "staff training"]),
        "implementation_specificity": code_implementation_specificity(row, text),
        "evidence_quote": extract_evidence(text, evidence_terms),
        "analytic_notes": "First-pass keyword code; review evidence_quote and full_text before publication.",
    }


def write_csv(path: str, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    with open(POLICY_INPUT, newline="", encoding="utf-8-sig") as f:
        policies = list(csv.DictReader(f))

    write_csv(ECOSYSTEM_OUTPUT, ECOSYSTEM_ROWS, list(ECOSYSTEM_ROWS[0].keys()))

    counts_by_state = Counter(row["state"] for row in policies)
    district_counts = Counter(row["state"] for row in policies if row["level"] == "district")
    state_guidance_count = Counter(row["state"] for row in policies if row["level"] == "state")
    policy_types = defaultdict(Counter)
    maturities = defaultdict(Counter)
    for row in policies:
        policy_types[row["state"]][infer_policy_type(row)] += 1
        maturities[row["state"]][infer_policy_maturity(row)] += 1

    matrix_rows = []
    ecosystem_by_state = {row["state"]: row for row in ECOSYSTEM_ROWS}
    for state in [row["state"] for row in ECOSYSTEM_ROWS]:
        matrix_rows.append(
            {
                "state": state,
                "ai_development_tier": ecosystem_by_state[state]["ai_development_tier"],
                "total_policy_rows": str(counts_by_state[state]),
                "state_level_rows": str(state_guidance_count[state]),
                "district_level_rows": str(district_counts[state]),
                "policy_type_mix": "; ".join(f"{k}: {v}" for k, v in sorted(policy_types[state].items())),
                "maturity_mix": "; ".join(f"{k}: {v}" for k, v in sorted(maturities[state].items())),
                "comparison_role": ecosystem_by_state[state]["comparison_role"],
            }
        )
    write_csv(STATE_MATRIX_OUTPUT, matrix_rows, list(matrix_rows[0].keys()))

    coding_rows = []
    for idx, row in enumerate(policies, start=1):
        coded = code_policy_row(row)
        coding_rows.append(
            {
                "policy_id": f"POL-{idx:03d}",
                "state": row["state"],
                "level": row["level"],
                "title": row["title"],
                "source_url": row["source_url"],
                "char_count": row["char_count"],
                "policy_type": infer_policy_type(row),
                "policy_maturity": infer_policy_maturity(row),
                **coded,
            }
        )
    write_csv(CODING_TEMPLATE_OUTPUT, coding_rows, CODING_FIELDS)

    print(f"Wrote {len(ECOSYSTEM_ROWS)} rows to {ECOSYSTEM_OUTPUT}")
    print(f"Wrote {len(matrix_rows)} rows to {STATE_MATRIX_OUTPUT}")
    print(f"Wrote {len(coding_rows)} rows to {CODING_TEMPLATE_OUTPUT}")


if __name__ == "__main__":
    main()
