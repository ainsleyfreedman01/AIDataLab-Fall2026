# Privacy Passages

This folder holds the **data and student privacy passages** from every K-12 AI policy document in
[`k12_ai_policies_singleline.csv`](../k12_ai_policies_singleline.csv) (205 rows, `source_url` column).
Each passage is quoted verbatim from the source document, with its location, and saved as one PDF per
document.

## What's in the folder

| File | What it is |
|---|---|
| `*_Privacy_Passages.pdf` (184 files) | One PDF per document that has privacy content |
| `Privacy_Passages_Log.csv` | One row per CSV row (all 205): how each document was accessed, what was produced, and any issues |
| `README.md` | This file |
| `scripts/` | The scripts and agent guide that produced all of the above |

### Totals

| Outcome | Docs | State | District |
|---|---|---|---|
| PDF of privacy passages | 181 | 57 | 124 |
| Hand-made PDFs copied in as-is (Fort Bend ISD, PSJA ISD, Massachusetts DESE) | 3 | 1 | 2 |
| No privacy passages found (no PDF; listed in the log) | 21 | 4 | 17 |
| **Total** | **205** | 62 | 143 |

## PDF format

Every PDF follows the three hand-made examples:

- **Title:** `<Document>: Data and Student Privacy Passages`.
- **Subtitle:** names the source document and says how pages are cited.
- **Sections:** each one has the document's own heading (marked "(excerpt)" when only part of the section is quoted), a `Source:` line, and then the verbatim text.

**What counts as a privacy passage.** I was inclusive, matching the Massachusetts example. A passage
counts if it covers any of these:
- student or staff data privacy and security, or personally identifiable information (PII)
- privacy laws: FERPA, COPPA, PPRA, CIPA, HIPAA, and state student-privacy laws
- data collection, retention, sharing, or use of data to train models
- vetting tools or vendors, data privacy agreements, terms of service, and approved-tool lists when they are framed as a privacy safeguard
- parental consent and age limits tied to data
- confidentiality, surveillance, cybersecurity and credentials, or reporting a data breach
- teaching students to protect their own data

Brief passing mentions are included too, such as a list of principles that includes "privacy".

**Markers used in the PDFs**

| Marker | Meaning |
|---|---|
| `…` | Text omitted from the middle of a quote |
| `[graphic]` | Text transcribed from an image, infographic, or table that I viewed as a rendered page |

**How pages are cited.** The `page_citation` column in the log says which style each PDF uses:
- the document's own printed page numbers (56 docs)
- PDF page numbers, when printed numbers are missing or unreliable (61 docs)
- section names, for web pages, Word documents and Google Docs, which have no pages (85 docs)

## How each document was accessed

| Method | Docs |
|---|---|
| Direct PDF download | 110 |
| Text of the web page | 78 |
| Followed a landing page to the document it links to (see below) | 9 |
| Direct Word (.docx) or Google Docs text export | 4 |
| Text cached in the CSV, because the source is no longer online | 1 |
| Your hand-made PDF | 3 |

**Following landing pages.** When a CSV URL was a thin landing page that mostly pointed to one main AI
document, I used that document instead, as in the Fort Bend example. The log's `document_used` column
shows the URL actually read. This applied to:
- Palo Alto USD (Google Doc)
- Dinuba USD
- ABC USD (published Google Doc)
- Newton (Google Doc)
- Philadelphia (Google Doc)
- Dallas ISD (AI Handbook on Drive)
- Michigan DOE (the Comprehensive Guide for Districts; the shorter Starter Guide is not covered)
- Ann Arbor (Google Doc)
- Indiana DOE (Drive file)

## Issues to know about

The full detail is in the log's `issues` column. These are the main ones.

### Access problems

| Document | What happened |
|---|---|
| Boston Public Schools | The full guidelines (a Google Doc) are restricted to BPS accounts, so I used the landing page. It had no privacy content. |
| Christina School District | The guidance file on Google Drive requires sign-in, so I used the landing page. |
| Fairfax County (FCPS) | The page now returns HTTP 410 (gone), so I used the text cached in the CSV. It has no page numbers. |
| NYS Board of Regents | The site's SSL certificate failed verification. I downloaded the file with verification turned off. |
| Charlotte-Mecklenburg landing page | The guidance PDF it links to is already its own row in the CSV, so I used the landing page to avoid duplicating it. |
| Academy District 20, DeKalb County | These pages only link to internal SharePoint behind a login. |

### Landing pages with no privacy text, where the linked documents likely have some

These rows are logged as "no privacy passages found". Their landing pages weren't thin enough to follow
under the rule above, so the documents they link to were not read:

| Row | Document not read |
|---|---|
| Beaverton SD | Guidelines sub-pages |
| Central Bucks SD | AI Handbook v3.0 |
| Canyons SD | AI Guidelines and Student AI Use Guidelines |
| Lincoln Public Schools | The AI Protocol; the CSV row is the 2-page board policy |
| NC DPI "AI Resources" page | NC AI Guidelines |
| Northwest ISD | Sub-pages |
| Douglas County SD | District policies AC, GBEE and JICJ |
| Virginia Beach | Acceptable Use and Digital Literacy policies |
| Boston Public Schools | Guidelines doc (login-restricted) |

Two other landing pages link to documents that are already their own rows: Ohio's "AI in Ohio's
Education" (its model policy is a separate row) and Academy District 20 (its Quick Start Guide is a
separate row).

### Accuracy checks

- **Automatic word-for-word check.** Every quoted passage, except `[graphic]` text and short labels, was checked automatically against the source text. All passed. In 5 documents, flagged passages differed only because something else sat in the middle of the passage in the extracted text. That happened with:
  - Loudoun County: the policy's margin line numbers
  - Arizona: sidebar quotes
  - Charlotte-Mecklenburg and Baldwin County: a page footer or page break
  - Vermont: page footers and footnote numbers

  I checked each of these by hand.
- **`[graphic]` passages are not auto-checked.** There are 514 of these blocks across 36 documents, transcribed from tables and infographics. They are the most likely place for a transcription slip, so spot-check them against the source PDF before quoting them.
- **Judgment calls.** Agents noted borderline inclusions and exclusions in the `issues` column. For example, deepfake passages were included only where they were framed as privacy.
- **Content flagged in the source itself.** Some documents are marked draft, proposed, or placeholder. Examples are New Hampshire ("FINAL-DRAFT, not legally binding"), Broward ("sample answers… pending legal review"), and the Collier and Highlands proposed policies. These are noted in the log.
- **Unusual CSV rows.** A few rows point to something other than an AI policy: Iowa's PD program summary, the Connecticut technology-policy recommendations, and the South Carolina learning-standards framework. They are noted in the log.

## How this was produced

1. **Downloaded** every `source_url` (October 14–15, 2026), plus the followed links listed above. Text was extracted page by page with pdfplumber, with page markers kept.
2. **Extracted** the privacy passages with parallel AI agents (Claude). They worked from a shared written guide and used the three hand-made PDFs as the reference for scope and style. Each agent wrote a structured file per document. Illinois's 408-page guidance was split across three agents.
3. **Verified** each passage against the source text automatically, and reviewed mismatches by hand.
4. **Rendered** the PDFs with reportlab, in the same layout as the examples.

The scripts and the agents' extraction guide are in [`scripts/`](scripts/). The intermediate files
were kept in a temporary working folder and are not part of this repo. Those are the downloads, the
extracted text, and the per-document passage files.
