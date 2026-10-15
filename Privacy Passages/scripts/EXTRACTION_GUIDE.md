# Privacy-passage extraction guide

You are extracting **data and student privacy passages, verbatim**, from K-12 AI policy/guidance
documents. For each assigned row you write one JSON spec file; a script then renders it to PDF in a
fixed house style, and another script checks every passage against the source text.

## Inputs (per row NNN, zero-padded to 3 digits)
- `work/text/NNN.txt` — header (TITLE, STATE, DOC_URL, ACCESS) then the full text. PDF text is split
  with `=== PDF page N of M ===` markers. Web pages / Word docs / text have no page markers.
- If the header's ACCESS says PDF, the original PDF is at `work/originals/NNN.pdf` or
  `work/followed/NNN.pdf`. To see a page (layout, text inside images/graphics, tables, printed page
  numbers), render it with
  `python -I <scratchpad>/scripts/render_page.py <pdf path> <page>[,<page>...]` (1-based PDF pages;
  `<scratchpad>` is the parent of the `work` folder) and then Read the PNG path it prints. (Reading
  the PDF directly with `pages:` does not work on this machine.) Do this for pages
  listed as having no extractable text if they might hold privacy content, and whenever a privacy
  section looks like a graphic/table that the text extraction garbled.

## What counts as a privacy passage (be inclusive — match the examples)
Include every passage that substantively concerns: student/staff data privacy or security; PII;
FERPA, COPPA, PPRA, CIPA, HIPAA, IDEA/504 records, state student-privacy laws; data collection,
storage, retention, sharing, deletion, or use for model training; vendor/tool vetting, data privacy
agreements, terms of service, approved-tool lists *as a privacy safeguard*; parental consent / age
restrictions tied to data or accounts; confidentiality; surveillance/monitoring; cybersecurity,
credentials/accounts as data protection; deepfakes/image misuse **only** where framed as privacy;
reporting data exposure; teaching students about protecting their own data/digital footprint.
Also include **passing mentions** (e.g., a list of principles that includes "privacy", a resource
description that mentions data privacy), as the Massachusetts example does — use "(excerpt)" in the
heading and quote just the relevant sentence/bullet(s) plus minimal context.
Do not include: generic academic integrity, bias, or accuracy text with no privacy/data angle;
table-of-contents lines; headers/footers; bibliography entries that merely have "privacy" in a title
(include only if the document describes them with privacy-relevant text, like the MA resource lists).

When an entire section is about privacy, include the whole section. If the same text is repeated
(e.g., in an appendix checklist), include it once and say so in `notes`.

## Verbatim rules (checked automatically)
- Copy text exactly as it appears in the source. Fix only: PDF line-break hyphenation, line wraps
  (join lines into normal paragraphs), and bullet glyphs (drop "•", "●", "o", "-" etc. — use a
  `bullet` block instead). Keep original spelling, capitalization, punctuation.
- Omitted text inside a quoted passage → " … " (Unicode ellipsis). Never paraphrase.
- Text you transcribed from an image or a table you viewed as a rendered page → start the block with
  `[graphic] `. These are exempt from the automatic check, so be careful. A `[graphic]` block must be
  a word-for-word transcription of what is printed, never your description or summary of it (not
  "The table's columns are: …"). If a table's text is interleaved in the extraction, render the page
  and transcribe each cell/row in reading order instead of guessing from the jumbled text.
- Before writing a spec, make sure each non-[graphic] block's text appears in the text file once
  whitespace, punctuation and case are ignored (page headers/footers or bullet glyphs mixed into the
  middle of a passage break this — split the block or use " … " around the intrusion).
- Your own headings are free text (not checked). Use the document's own section heading where there
  is one, e.g. "Data Privacy & Security", "Guiding Principles: Safety and Privacy",
  "Response to Misuse for All Stakeholders (excerpt)".
- `**bold**` inside block text is allowed for run-in labels that are bold/labelled in the source
  (e.g. "**Privacy Violations** — Entering or sharing…"); the asterisks are stripped before checking.
  Only use it where the source has a label like that.

## Page citations
- PDFs: prefer the document's own printed page numbers when you can identify them reliably (check a
  couple of pages — printed numbers usually appear at the top/bottom of the page text); then
  `page_mode: "printed"`. Otherwise use PDF page numbers, `page_mode: "pdf"`. Be consistent within a
  document.
- Non-PDF (web page, Word, text): `page_mode: "none"`; set each section's `source` to something like
  "web page, section 'Data Privacy'" or "web page" (or "Word document" / "Google Doc").
- `source` strings look like "page 9", "pages 30–32", "PDF page 10 (table row)", "page 8 [graphic]".

## Output: write `work/specs/NNN.json` (UTF-8) with this shape
```json
{
  "row": 13,
  "file_stem": "Colorado_AI_Roadmap",
  "doc_title": "Colorado AI Roadmap",
  "source_citation": "Colorado Roadmap for AI in K-12 Education (Colorado Education Initiative, August 2024)",
  "page_mode": "printed",
  "notes": "Ellipses (…) mark omitted text.",
  "no_privacy": false,
  "sections": [
    {
      "heading": "Data Privacy & Security",
      "source": "page 8",
      "blocks": [
        {"type": "p", "text": "Ensuring the protection of staff and student’s data is essential …"},
        {"type": "subhead", "text": "Examples of Strictly Prohibited Information:"},
        {"type": "bullet", "text": "**Basic Identifiers:** Student names (first and last), Student ID numbers …"}
      ]
    }
  ],
  "issues": []
}
```
- `file_stem`: short, unique, filename-safe (letters, digits, underscores), in the style of the
  examples: district/agency abbreviation or short name + doc type, e.g. `FBISD_AI_Handbook`,
  `PSJA_AI_Guidebook`, `Massachusetts_AI_Guidance`, `LAUSD_AI_Policy_Bulletin`,
  `California_AI_Model_Policy`. Include the state name for state agencies. If one district has
  several rows, make the stems distinguishable (e.g. `Jeffco_AI_Student_Guidance`,
  `Jeffco_AI_Resource_Page`).
- `doc_title`: the PDF title prefix; PDF title will be "<doc_title>: Data and Student Privacy Passages".
- `source_citation`: the document's full name (+ issuing body, version/date if shown). Rendered in italics.
- `notes`: optional extra sentences for the subtitle (ellipses, [graphic] use, repeated material omitted,
  that the document is a landing page / web page, etc.). The renderer already writes the page-number
  sentence, so don't repeat it.
- Order sections in document order.
- `no_privacy: true` with empty `sections` if the document has nothing privacy-related at all.
  Use sparingly — a single meaningful sentence is enough to make a spec.
- `issues`: anything the user should know: text extraction problems, pages you couldn't read,
  document seems truncated / not actually an AI policy / a login wall / in another language,
  uncertainty about page numbers, the CSV row seems to point at the wrong document, etc.

## Method
1. Read the header and skim the start of the text file to learn the document's structure and page
   numbering.
2. Grep the text file (case-insensitive) for at least: privacy|private|personal|PII|identifiable|
   FERPA|COPPA|PPRA|CIPA|HIPAA|confidential|sensitive|data|security|secure|consent|terms of service|
   vendor|vetted|approved|surveil|monitor|record|password|credential|login|account|footprint|
   protect|safeguard|breach|retention|share|third.party. Then read each hit **in context** (the whole
   surrounding section), so headings and section boundaries are right.
3. For documents under ~60,000 characters, read the whole file. For longer ones, rely on grep plus
   reading every section that has hits.
4. Write the spec. Do not create or edit any other files.
