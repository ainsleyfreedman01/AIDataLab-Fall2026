"""Merge split specs, verify passages are verbatim, render PDFs, write the access log.

Usage: python finalize.py WORK CSV OUT_DIR [--check-only]
"""
import csv, glob, html, json, os, re, shutil, sys, unicodedata
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

WORK, CSV_PATH, OUT = sys.argv[1:4]
CHECK_ONLY = "--check-only" in sys.argv
SPECS = os.path.join(WORK, "specs")
csv.field_size_limit(10**9)
rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8-sig")))
access = {int(k): v for k, v in json.load(open(os.path.join(WORK, "access.json"), encoding="utf-8")).items()}

# ---------- fonts / styles (matches the user's example PDFs) ----------
FONT_DIR = r"C:\Windows\Fonts"
for name, fn in [("Arial", "arial.ttf"), ("Arial-Bold", "arialbd.ttf"), ("Arial-Italic", "ariali.ttf"), ("Arial-BoldItalic", "arialbi.ttf")]:
    pdfmetrics.registerFont(TTFont(name, os.path.join(FONT_DIR, fn)))
pdfmetrics.registerFontFamily("Arial", normal="Arial", bold="Arial-Bold", italic="Arial-Italic", boldItalic="Arial-BoldItalic")
ARIAL = pdfmetrics.getFont("Arial").face
ACCENT, GRAY = HexColor("#7A1F1F"), HexColor("#8A8A8A")
S = {
    "title": ParagraphStyle("title", fontName="Arial-Bold", fontSize=20, leading=25, alignment=TA_CENTER, spaceAfter=10),
    "sub": ParagraphStyle("sub", fontName="Arial", fontSize=8.5, leading=11, textColor=GRAY, spaceAfter=8),
    "h": ParagraphStyle("h", fontName="Arial-Bold", fontSize=14, leading=18, textColor=ACCENT, spaceBefore=10, spaceAfter=3),
    "src": ParagraphStyle("src", fontName="Arial", fontSize=7.5, leading=10, textColor=GRAY, spaceAfter=6),
    "p": ParagraphStyle("p", fontName="Arial", fontSize=10.5, leading=14.5, spaceAfter=7),
    "subhead": ParagraphStyle("subhead", fontName="Arial-Bold", fontSize=10.5, leading=14.5, spaceAfter=5),
    "li": ParagraphStyle("li", fontName="Arial", fontSize=10.5, leading=14.5, spaceAfter=4),
}
PAGE_SENTENCE = {
    "printed": "Page numbers match the document's own page numbering.",
    "pdf": "Page numbers refer to the PDF pages of the source file.",
    "none": "The source has no page numbers; locations are given by section.",
}


def supported(text):
    return "".join(c for c in text if ord(c) in ARIAL.charToGlyph or c in "\n\t")


def markup(text):
    text = html.escape(supported(text), quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def render(spec, path):
    story = [Paragraph(markup(f"{spec['doc_title']}: Data and Student Privacy Passages"), S["title"])]
    sub = (f"Excerpted verbatim from <i>{markup(spec['source_citation'])}</i>. "
           f"{PAGE_SENTENCE.get(spec.get('page_mode'), '')} {markup(spec.get('notes') or '')}")
    story.append(Paragraph(sub.strip(), S["sub"]))
    for sec in spec["sections"]:
        head = [Paragraph(markup(sec["heading"]), S["h"]), Paragraph(markup("Source: " + sec.get("source", "")), S["src"])]
        body, bullets = [], []

        def flush():
            if bullets:
                body.append(ListFlowable([ListItem(b, leftIndent=14, value="•") for b in bullets],
                                         bulletType="bullet", start="•", leftIndent=14, bulletFontName="Arial", bulletFontSize=10.5))
                bullets.clear()
        for b in sec["blocks"]:
            if b["type"] == "bullet":
                bullets.append(Paragraph(markup(b["text"]), S["li"]))
            else:
                flush()
                body.append(Paragraph(markup(b["text"]), S["subhead" if b["type"] == "subhead" else "p"]))
        flush()
        # keep heading with the first block
        story.append(KeepTogether(head + body[:1]))
        story.extend(body[1:])
    doc = SimpleDocTemplate(path, pagesize=letter, leftMargin=0.95 * inch, rightMargin=0.95 * inch,
                            topMargin=0.85 * inch, bottomMargin=0.85 * inch,
                            title=f"{spec['doc_title']}: Data and Student Privacy Passages", author="AIDataLab")
    doc.build(story)


# ---------- verbatim check ----------
def norm(s):
    s = unicodedata.normalize("NFKC", s).lower()
    return re.sub(r"[^a-z0-9]", "", s)


def check(spec, source_norm):
    problems = []
    for sec in spec["sections"]:
        for b in sec["blocks"]:
            t = b["text"].strip()
            # Subheads are labels the extractor may write itself, like section headings.
            if t.startswith("[graphic]") or b["type"] == "subhead":
                continue
            t = t.replace("**", "")
            for frag in re.split(r"…|\.\.\.", t):
                n = norm(frag)
                if len(n) >= 12 and n not in source_norm:
                    problems.append({"heading": sec["heading"], "fragment": frag.strip()[:160]})
    return problems


def merge_split(row):
    parts = sorted(glob.glob(os.path.join(SPECS, f"{row:03d}_p*.json")))
    if not parts:
        return None
    specs = [json.load(open(p, encoding="utf-8")) for p in parts]
    merged = dict(specs[0])
    # Part 1's citation names its own page range; the merged spec covers the whole document.
    merged["source_citation"] = re.sub(r",?\s*PDF pages [\d–-]+ of \d+\s*\(part \d of \d\)", "", merged["source_citation"])
    merged["notes"] = re.sub(r"from a rendered table\.", "from rendered tables or graphics.", merged.get("notes") or "")
    merged["sections"] = [s for sp in specs for s in sp["sections"]]
    merged["issues"] = [i for sp in specs for i in sp.get("issues", [])]
    modes = {sp.get("page_mode") for sp in specs}
    if len(modes) > 1:
        merged["issues"].append(f"Split-document parts used different page conventions: {sorted(modes)}")
    merged["no_privacy"] = not merged["sections"]
    json.dump(merged, open(os.path.join(SPECS, f"{row:03d}.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return merged


EXISTING = {46: "Massachusetts_AI_Guidance_Privacy_Passages.pdf",
            75: "FBISD_AI_Handbook_Privacy_Passages.pdf",
            78: "PSJA_AI_Guidebook_Privacy_Passages.pdf"}
EXISTING_SRC = {46: r"C:\Users\sukhr\Downloads\Massachusetts_AI_Guidance_Privacy_Passages.pdf",
                75: r"C:\Users\sukhr\OneDrive\Documents\AI_Data_Lab_Readings\FBISD_AI_Handbook_Privacy_Passages.pdf",
                78: r"C:\Users\sukhr\OneDrive\Documents\AI_Data_Lab_Readings\PSJA_AI_Guidebook_Privacy_Passages.pdf"}
EXISTING_NOTE = {
    46: "User-made PDF copied in as-is",
    75: "User-made PDF copied in as-is; source page links FBISDAIHandbook_6-11-25.pdf, which the passages quote (PDF page numbers)",
    78: "User-made PDF copied in as-is (guidebook's own page numbering)",
}

# Specs written by agents that hit the usage limit before finishing their batch.
INTERRUPTED = set()
# Verbatim-check mismatches I inspected by hand: the quote is correct and the extracted text has
# something interleaved in the middle of the passage.
REVIEWED = {
    84: "the policy's printed margin line numbers, which were left out",
    96: "sidebar student quotes interleaved in the extracted text",
    122: "a page footer between lines",
    141: "a page break",
    197: "page footers and footnote reference numbers",
}
merge_split(100)
report, stems, log_rows = {}, {}, []
os.makedirs(OUT, exist_ok=True)
for i, r in enumerate(rows):
    a = access[i]
    entry = {"row": i, "state": r["state"], "level": r["level"], "doc_type": r["doc_type"], "title": r["title"],
             "source_url": r["source_url"], "document_used": a.get("doc_url", ""), "access_method": a.get("method", ""),
             "page_citation": "", "output_pdf": "", "privacy_sections": "", "status": "", "issues": list(a.get("issues", []))}
    if i in EXISTING:
        entry.update(output_pdf=EXISTING[i], status="privacy passages (user-provided PDF)", page_citation="see PDF",
                     document_used="see PDF header" if i != 75 else "https://resources.finalsite.net/images/v1782138957/fortbendisdcom/uvoytk9q7wgmbbendgen/FBISDAIHandbook_6-11-25.pdf")
        entry["issues"].append(EXISTING_NOTE[i])
        if not CHECK_ONLY:
            shutil.copy2(EXISTING_SRC[i], os.path.join(OUT, EXISTING[i]))
        log_rows.append(entry)
        continue
    spec_path = os.path.join(SPECS, f"{i:03d}.json")
    if not os.path.exists(spec_path):
        entry["status"] = "not yet processed"
        report[i] = {"missing": True}
        log_rows.append(entry)
        continue
    spec = json.load(open(spec_path, encoding="utf-8"))
    entry["issues"] += spec.get("issues", [])
    entry["page_citation"] = {"printed": "document's printed page numbers", "pdf": "PDF page numbers",
                              "none": "no page numbers (section names)"}.get(spec.get("page_mode"), spec.get("page_mode", ""))
    if spec.get("no_privacy") or not spec.get("sections"):
        entry["status"] = "no privacy passages found"
        log_rows.append(entry)
        continue
    src = open(os.path.join(WORK, "text", f"{i:03d}.txt"), encoding="utf-8").read()
    problems = check(spec, norm(src))
    if problems:
        report[i] = {"stem": spec["file_stem"], "problems": problems}
        if i in REVIEWED:
            entry["issues"].append(f"{len(problems)} passage(s) differ from the extracted text only by {REVIEWED[i]} (checked manually)")
        else:
            entry["issues"].append(f"{len(problems)} passage fragment(s) did not match the extracted source text exactly; needs review")
    graphic = sum(b["text"].lstrip().startswith("[graphic]") for s in spec["sections"] for b in s["blocks"])
    if graphic:
        entry["issues"].append(f"{graphic} [graphic] block(s) reconstructed from tables/images; not auto-verified, spot-check against source")
    stem = re.sub(r"[^A-Za-z0-9_]+", "_", spec["file_stem"]).strip("_")
    if stem in stems:
        stem = f"{stem}_{i}"
    stems[stem] = i
    fname = f"{stem}_Privacy_Passages.pdf"
    entry.update(output_pdf=fname, privacy_sections=len(spec["sections"]),
                 status="DRAFT: agent interrupted, to be redone" if i in INTERRUPTED else "privacy passages")
    if not CHECK_ONLY:
        render(spec, os.path.join(OUT, fname))
    log_rows.append(entry)

json.dump(report, open(os.path.join(WORK, "verify_report.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("rows with verbatim problems:", {k: len(v["problems"]) for k, v in report.items() if v.get("problems")})
print("rows missing specs:", [k for k, v in report.items() if v.get("missing")])

if not CHECK_ONLY:
    cols = ["csv_row", "state", "level", "doc_type", "title", "source_url", "document_used", "access_method",
            "page_citation", "status", "privacy_sections", "output_pdf", "issues"]
    with open(os.path.join(OUT, "Privacy_Passages_Log.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for e in log_rows:
            e = dict(e, csv_row=e.pop("row") + 1, issues=" | ".join(dict.fromkeys(e["issues"])))
            w.writerow(e)
    from collections import Counter
    print(Counter(e["status"] for e in log_rows))
