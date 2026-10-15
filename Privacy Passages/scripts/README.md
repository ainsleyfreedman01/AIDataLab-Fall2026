# Scripts

These are the scripts that produced the PDFs and `Privacy_Passages_Log.csv` in the parent folder.
They were run from a temporary working folder, so paths are passed as arguments.

Every script expects a working folder, written `WORK` below.

## Pipeline, in run order

| Step | Script | What it does |
|---|---|---|
| 1 | `download.py CSV WORK/originals` | Downloads every `source_url` into `WORK/originals/NNN.<ext>` (NNN = 0-based CSV row). Records any document links found on web pages in `WORK/manifest.json`. |
| 2 | `build_texts.py CSV WORK` | Picks the document to read for each row. Writes page-marked text to `WORK/text/NNN.txt` and the access record to `WORK/access.json`. |
| 3 | `batches.py WORK [chars]` | Groups the rows into agent batches of roughly equal text size. |
| 4 | `extract_workflow.js` | Claude Code workflow. One agent per batch reads `EXTRACTION_GUIDE.md` and writes `WORK/specs/NNN.json`, the verbatim passages for one document. Illinois (row 100) is split across 3 agents. |
| 5 | `finalize.py WORK CSV OUT_DIR [--check-only]` | Checks every passage against the source text and writes `WORK/verify_report.json`. Then renders the PDFs and writes the log into `OUT_DIR`. Use `--check-only` to skip rendering. |

The decisions behind the outputs are hard-coded in two scripts:

| Script | Hard-coded |
|---|---|
| `build_texts.py` | `FOLLOW` (landing pages swapped for their main linked document), `NOTES` (per-row access notes), `EXISTING` (rows covered by the hand-made PDFs) |
| `finalize.py` | `EXISTING_SRC` (where the hand-made PDFs are copied from), `REVIEWED` (verbatim-check mismatches confirmed by hand) |

## Helpers

| Script | Use |
|---|---|
| `render_page.py PDF PAGE[,PAGE]` | Renders PDF pages to PNG so agents can read graphics and tables. |
| `diagnose.py WORK ROWS` | Shows where a flagged quote diverges from the source text. |
| `stats.py LOG_CSV` | Summary counts from the log. These were used to write the README. |
| `show_html.py`, `find_links.py`, `peek.py` | Used while deciding which landing pages to follow. |

## Requirements

- Python 3, with `requests`, `beautifulsoup4`, `pdfplumber`, `pypdf`, `pypdfium2` and `reportlab` installed.
- `finalize.py` uses the Arial fonts from `C:\Windows\Fonts`.
