"""Resolve the document to read for each CSV row and write page-marked text.

Writes work/text/NNN.txt and work/access.json (how each doc was obtained).
"""
import csv, io, json, os, re, sys, zipfile
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
import requests, urllib3
import pdfplumber
from bs4 import BeautifulSoup

CSV_PATH, WORK = sys.argv[1], sys.argv[2]
ORIG, TEXT, FOLLOWED = (os.path.join(WORK, d) for d in ("originals", "text", "followed"))
os.makedirs(TEXT, exist_ok=True); os.makedirs(FOLLOWED, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
csv.field_size_limit(10**9)
rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8-sig")))
manifest = {m["i"]: m for m in json.load(open(os.path.join(WORK, "manifest.json")))}

# The user already made these three by hand.
EXISTING = {46: "Massachusetts_AI_Guidance_Privacy_Passages.pdf",
            75: "FBISD_AI_Handbook_Privacy_Passages.pdf",
            78: "PSJA_AI_Guidebook_Privacy_Passages.pdf"}


def gdoc(doc_id):
    return f"https://docs.google.com/document/d/{doc_id}/export?format=pdf"


def gdrive(file_id):
    return f"https://drive.google.com/uc?export=download&id={file_id}"


# Thin landing pages -> the one main AI document they point to.
FOLLOW = {
    5: (gdoc("1Td5ToCqonnaFjTkac-L5yQ40DLSqNZo-6cL6Le55-dQ"), "Google Doc 'PAUSD Generative AI Guidance' linked from page; exported as PDF"),
    6: (urljoin(rows[6]["source_url"], "/fs/resource-manager/view/e036c959-8628-4043-bf02-d006de9e1ea2"), "'This document' guidelines file linked from page"),
    8: ("https://docs.google.com/document/d/e/2PACX-1vRQ7rsVRYixrJ-vwXA7uNgOSUjoXGBYZ9iVFzXH1XLRPqDdXsSh1qyg0lRVo_bSvM4mivmxbcPOE7o_/pub", "Published Google Doc 'A Guide to Ethical and Responsible AI Use' embedded in page"),
    49: (gdoc("1iNVk3Bnj22H955J4eRnIRH_hDhE0tUcQp_zJrK-hPxw"), "Google Doc 'District AI Guidelines' linked from page; exported as PDF"),
    64: (gdoc("1olLZ_RIo5x1E2EdQ823GjOuA5yorj_BVMpoMdmKYDgo"), "Google Doc 'District's AI guidance' linked from page; exported as PDF"),
    70: (gdrive("1NDuI_dwfULq61qxA6vdO9hxeZmS_M0XN"), "Google Drive file 'AI Handbook' linked from page"),
    105: ("https://www.michigan.gov/mde/-/media/Project/Websites/mde/Educational-Technology/Artificial-Intelligence-AI-Comprehensive-Guide-for-Districts.pdf?rev=cd98ea19401941889b1fcd1ff1dd340c&hash=4CECA03966C7ED8AB76333398FF8D12D", "'AI Comprehensive Guide for Districts' PDF linked from page (page also links a shorter Starter Guide)"),
    107: (gdoc("1TYkNpFg97CODPkPE8r6wcyEKmmh2N3iDo9rqfVsh5mE"), "Google Doc 'AI Bill of Rights' linked from page ('View Resource'); exported as PDF"),
    154: (gdrive("155XYqyFR_YnHE6veanG7ZpM1NBPB2N44"), "Google Drive file 'Artificial Intelligence (AI) Guidance' linked from page"),
}


NOTES = {
    25: "Page links its main guidance as a Google Drive file that requires a Google sign-in; used the landing page itself",
    52: "Main guidelines (page -> BPS AI Hub Google Site -> 'V3 Guidelines' Google Doc) are restricted to BPS accounts (HTTP 401); used the landing page itself",
    124: "Page links its Generative AI Guidance PDF, but that PDF is already CSV row 122; used the landing page itself to avoid duplication",
    22: "Thin page; its only linked resource (AI Toolbox) is on internal SharePoint requiring login",
    41: "Thin page; its linked resources are on internal SharePoint requiring login",
    105: "Landing page lists several MDE guides; used the Comprehensive Guide as the main document (Starter Guide not covered)",
}


def looks_unspaced(text):
    words = text.split()
    return len(words) >= 20 and sum(len(w) > 25 for w in words) / len(words) > 0.03


def pdf_pages(raw):
    pages = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if looks_unspaced(t):
                t = page.extract_text(x_tolerance=1.5) or t
            pages.append(t)
    return pages


def docx_text(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        doc = ET.fromstring(z.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paras = ["".join(n.text or "" for n in p.findall(".//w:t", ns)) for p in doc.findall(".//w:p", ns)]
    return "\n".join(p for p in paras if p.strip())


BOILER = re.compile(r"(?:^|[-_\s])(?:nav|navbar|header|footer|menu|breadcrumbs?|sidebar|alert|skip)(?:$|[-_\s])", re.I)


def html_text(raw):
    try:
        raw = raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside"]):
        tag.decompose()
    for tag in [t for t in soup.find_all(True) if t.name not in ("html", "body", "main", "article")
                and BOILER.search(" ".join([t.get("id") or ""] + list(t.get("class") or [])))]:
        if not tag.decomposed:
            tag.decompose()
    main = soup.find("main") or soup.body or soup
    lines = [l.strip() for l in main.get_text("\n").splitlines()]
    return "\n".join(l for l in lines if l)


def get(url, verify=True):
    r = requests.get(url, headers=HEADERS, timeout=120, verify=verify)
    r.raise_for_status()
    return r


def to_text(raw, ctype=""):
    """Return (kind, page-marked text)."""
    if raw[:4] == b"%PDF":
        pages = pdf_pages(raw)
        return "pdf", "\n".join(f"\n=== PDF page {n} of {len(pages)} ===\n{t}" for n, t in enumerate(pages, 1))
    if raw[:2] == b"PK":
        return "docx", "=== Word document (no page numbers) ===\n" + docx_text(raw)
    if "text/plain" in ctype:
        return "txt", "=== Plain text (no page numbers) ===\n" + raw.decode("utf-8-sig", "replace")
    return "html", "=== Web page (no page numbers) ===\n" + html_text(raw)


access = {}
for i, r in enumerate(rows):
    rec = {"i": i, "state": r["state"], "level": r["level"], "title": r["title"], "source_url": r["source_url"],
           "issues": [NOTES[i]] if i in NOTES else []}
    m = manifest[i]
    text = None
    try:
        if i in EXISTING:
            rec.update(method="user-provided PDF (copied in as-is)", doc_url="see user's PDF", existing=EXISTING[i])
        elif i in FOLLOW:
            url, note = FOLLOW[i]
            resp = get(url)
            raw = resp.content
            ext = "pdf" if raw[:4] == b"%PDF" else "bin"
            open(os.path.join(FOLLOWED, f"{i:03d}.{ext}"), "wb").write(raw)
            kind, text = to_text(raw, resp.headers.get("Content-Type", ""))
            rec.update(method=f"followed link from landing page: {note}", doc_url=url, kind=kind,
                       pdf_path=os.path.join(FOLLOWED, f"{i:03d}.{ext}") if ext == "pdf" else None)
        elif "error" in m and i == 53:
            resp = get(r["source_url"], verify=False)
            kind, text = to_text(resp.content, resp.headers.get("Content-Type", ""))
            rec.update(method="direct download (SSL certificate verification failed on the site; downloaded with verification disabled)", doc_url=r["source_url"], kind=kind)
            rec["issues"].append("Site's SSL certificate failed verification")
        elif "error" in m:
            kind, text = "csv", "=== Text from CSV full_text (source no longer online; no page numbers) ===\n" + r["full_text"].replace("，", ",").replace("”", '"')
            rec.update(method="CSV full_text (cached from earlier retrieval)", doc_url=r["source_url"], kind=kind)
            rec["issues"].append(f"Source URL failed now ({m['error'][:80]}); used text cached in CSV")
        else:
            raw = open(m["path"], "rb").read()
            kind, text = to_text(raw, "text/plain" if m["kind"] == "txt" else "")
            rec.update(method={"pdf": "direct PDF download", "docx": "direct Word (.docx) download",
                               "txt": "direct plain-text download (Google Docs txt export)",
                               "html": "web page text"}[kind], doc_url=r["source_url"], kind=kind,
                       pdf_path=m["path"] if kind == "pdf" else None)
        if text is not None:
            rec["chars"] = len(text)
            if len(text) < 800:
                rec["issues"].append(f"Very little text extracted ({len(text)} chars)")
            if kind == "pdf":
                blank = re.findall(r"=== PDF page (\d+) of \d+ ===\n\s*(?==== |\Z)", text + "\n")
                if blank:
                    rec["blank_pages"] = [int(p) for p in blank]
                    rec["issues"].append(f"PDF pages with no extractable text (images/scans): {', '.join(blank)}")
            header = f"ROW {i}\nTITLE: {r['title']}\nSTATE: {r['state']} ({r['level']})\nDOC_URL: {rec['doc_url']}\nACCESS: {rec['method']}\n"
            open(os.path.join(TEXT, f"{i:03d}.txt"), "w", encoding="utf-8").write(header + text)
    except Exception as e:
        rec["issues"].append(f"FAILED: {e!r}"[:300])
    access[i] = rec

json.dump(access, open(os.path.join(WORK, "access.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
for rec in access.values():
    if rec["issues"]:
        print(rec["i"], rec["title"][:60], "|", "; ".join(rec["issues"]))
