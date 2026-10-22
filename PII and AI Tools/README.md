# PII and AI Tools

What each K-12 AI policy document counts as **personally identifiable information (PII)**, and
which **AI tools** it approves, restricts, or blocks. Built from the PDFs in
[`Privacy Passages`](../Privacy%20Passages/) (one per row of `k12_ai_policies_singleline.csv`).

## Files

| File | One row per | Use it for |
|---|---|---|
| `pii_and_tools_by_document.csv` | document (all 205 rows) | PII items and tools for each PDF, plus a 0/1 column per PII item |
| `pii_spectrum_by_organization.csv` | district, or state (state-level docs) | The spectrum: each district's documents merged, sorted by how many PII items it names |
| `pii_category_summary.csv` | PII item | How many districts / states name each item, and which ones |
| `ai_tool_summary.csv` | AI tool | How many districts / states approve, restrict, block, or only mention each tool |
| `evidence.csv` | coded item | The quote behind every PII item and tool status, with its page/section and how it was decided |
| `pii_rejected_matches.csv` | rejected match | Every pattern match that was *not* counted, with the reason and the rejected text |
| `pii_term_spectrum.csv` / `.png` / `.html` | district | Districts ranked by how many PII terms they name |
| `pii_district_matrix.csv` / `.png` / `.html` | district | Which terms each district names. In the CSV a cell holds the PDF and page/section (blank = not named); in the HTML, click a cell for the quote |
| `build_pii_tools.py` | | Rebuilds the data from the PDFs (`python build_pii_tools.py`) |
| `make_pii_spectrum.py`, `make_pii_matrix.py` | | Rebuild the charts (run after `build_pii_tools.py`) |

## How it was coded

**PII items (29 categories).** Patterns for each item (names, SSN, IEP/504, health, biometrics…) were
searched only in text near PII, confidential-data, or "do not enter/share" language, so a word like
"grades" elsewhere in a policy doesn't count. Every match was then read by hand. 41 false matches were
removed: for example "address" used as a verb, "grades 6–12," "disciplinary action," and policy
cross-reference titles. Two were added by hand. Both lists are in the script (`PII_EXCLUDE`, `PII_ADD`).

`pii_definition_level` places each document on the spectrum:

| Level | Meaning |
|---|---|
| detailed list (8+ items) | spells out a long PII definition |
| moderate list (4–7) / brief list (1–3) | names some specific items |
| general mention only | says "don't enter PII / personal information" but never says what that includes |
| privacy passages, but no personal-data language | privacy content is about laws, vendors, etc. only |
| no PDF | no privacy passages were found (21 rows) |

**AI tools.** Every passage naming a tool was read and coded by hand (`TOOLS` in the script):

| Status | Meaning |
|---|---|
| approved | approved, adopted, licensed, provided, or recommended by the district |
| conditional | allowed with limits (e.g. "staff may use if no PII," personal premium accounts) |
| not_approved | blocked, not approved, or called "not secure" for district data |
| mentioned | named only as an example (age limits, how chatbots work) |

The same tool can have two statuses in one document when versions differ. For example, Houston
approves ChatGPT Edu but not consumer ChatGPT. The `scope / notes` text in each cell says which version.

## Caveats

- **Tool counts are an undercount.** These PDFs contain only the *privacy* passages, so approved-tool
  lists not framed around privacy were never excerpted. For example, Dallas points to a list on p.9 of
  its handbook, and Fort Bend to its Appendix A. In the full source text, MagicSchool appears in 31
  documents but in only 9 sets of privacy passages, and ChatGPT appears in 65 vs. 21.
- **"PII" here means anything a document treats as personal data that must be protected.** That
  includes lists labelled "confidential" or "sensitive," not only lists under the heading "PII." The
  `uses_term_PII` column says whether the document uses the term itself.
- **Law descriptions count.** If a document says FERPA protects education records, or that a state
  law protects employee evaluation data, the item is counted for that document.
- **Some definitions live elsewhere.** Houston (Board Policy FL) and Minneapolis (a Best Practices
  guide) point to external PII definitions, so they appear as "general mention only."
- **State-level rows** include state guidance and model policies. Illinois's "approved" tools are its
  sample tool review, not an actual approval. Maryland's are for its own agency staff.
