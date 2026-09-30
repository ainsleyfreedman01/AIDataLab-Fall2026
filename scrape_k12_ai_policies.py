"""
Scrapes official state- and school-district-level K-12 AI policy/guidance
documents (PDF or HTML) for California, Washington, Texas, New York,
Pennsylvania, Massachusetts, and Georgia, and writes the full extracted text
of each into a CSV for analysis.

Usage: python3 scrape_k12_ai_policies.py
Output: k12_ai_policies.csv (state, level, title, source_url, date_retrieved, full_text)
"""

import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import pdfplumber

# One real, publicly published state-level (or state-task-force) K-12 AI
# guidance document per state, plus one real district/individual-school-level
# AI policy per state, found via web search of each agency's official site.
SOURCES = [
    {
        "state": "California",
        "level": "state",
        "title": "Artificial Intelligence in Public Schools: Guidance (California Department of Education)",
        "url": "https://www.cde.ca.gov/ci/pl/documents/aiguidance.pdf",
    },
    {
        "state": "California",
        "level": "state",
        "title": "Model Policy: Artificial Intelligence in Education (California Department of Education; nonbinding template)",
        "url": "https://www.cde.ca.gov/ci/pl/documents/aimodelpolicy.docx",
    },
    {
        "state": "California",
        "level": "district",
        "title": "Guidelines for the Authorized Use of Artificial Intelligence for the District (Los Angeles Unified School District Policy Bulletin)",
        "url": "https://media.edlio.net/3476a301/6d998082/01503609/1dd0fae97a594f01aadad0a950d4ea11?_=BUL-151113_0_Guidelines_for_the_Authorized_Use_of_Artificial_Intelligence_for_District.pdf",
    },
    {
        "state": "Washington",
        "level": "state",
        "title": "Human-Centered AI Guidance for K-12 Public Schools (OSPI)",
        "url": "https://ospi.k12.wa.us/sites/default/files/2024-08/comprehensive-ai-guidance.pdf",
    },
    {
        "state": "Washington",
        "level": "district",
        "title": "Artificial Intelligence Handbook for Seattle Public Schools",
        "url": "https://www.seattleschools.org/wp-content/uploads/2025/02/AI-Handbook-ADA.pdf",
    },
    {
        "state": "Washington",
        "level": "district",
        "title": "Bellevue School District Artificial Intelligence Handbook",
        "url": "https://resources.finalsite.net/images/v1789071509/bsd405org/j5limaqb5svwn6mxyt27/BSD_AI_Handbook.pdf",
    },
    {
        "state": "Texas",
        "level": "state",
        "title": "Texas AI in Education Task Force Report / Whitepaper (TACC, UT Austin)",
        "url": "https://tacc.utexas.edu/media/filer_public/18/e5/18e507b4-4f78-4566-8261-d9e3bb1ae6dd/whitepaper-aiedu-061726.pdf",
    },
    {
        "state": "Texas",
        "level": "district",
        "title": "AI in Dallas ISD (Dallas Independent School District)",
        "url": "https://www.dallasisd.org/departments/library-media-services/ai-in-dallas-isd",
    },
    {
        "state": "Texas",
        "level": "district",
        "title": "Houston ISD AI Guidebook (Houston Independent School District)",
        "url": "https://resources.finalsite.net/images/v1777472784/houstonisdorg/ffvo6lng6pttnchgfzgh/25-26HISDAIGuidebook.pdf",
    },
    {
        "state": "New York",
        "level": "state",
        "title": "Artificial Intelligence (AI) and P-12 Education (NYS Board of Regents / NYSED)",
        "url": "https://www.regents.nysed.gov/sites/regents/files/P-12%20-%20Artificial%20Intelligence%20AI%20and%20P-12%20Education.pdf",
    },
    {
        "state": "New York",
        "level": "district",
        "title": "Guidance on Artificial Intelligence and Screen Time (New York City Public Schools)",
        "url": "https://www.schools.nyc.gov/about-us/policies/guidance-on-artificial-intelligence",
    },
    {
        "state": "Pennsylvania",
        "level": "state",
        "title": "Implementing AI in Schools (Pennsylvania Department of Education)",
        "url": "https://www.pa.gov/agencies/education/ai-digital-media-literacy/implementingaiinschools",
    },
    {
        "state": "Pennsylvania",
        "level": "district",
        "title": "Policy 815.1 - Use of Artificial Intelligence in Education (Allentown School District)",
        "url": "https://go.boarddocs.com/pa/alen/Board.nsf/files/DJSJBG4C61DC/$file/Policy%20815.1%20-%20Use%20of%20Artificial%20Intelligence%20in%20Education.pdf",
    },
    {
        "state": "Pennsylvania",
        "level": "district",
        "title": "AI Resources - PSTV (School District of Philadelphia)",
        "url": "https://www.philasd.org/pstv/ai-resources/",
    },
    {
        "state": "Massachusetts",
        "level": "state",
        "title": "Massachusetts Guidance for Artificial Intelligence in K-12 Education (DESE)",
        "url": "https://www.doe.mass.edu/edtech/ai/ai-guidance.pdf",
    },
    {
        "state": "Massachusetts",
        "level": "district",
        "title": "Boston Public Schools Artificial Intelligence (AI) Policy",
        "url": "https://resources.finalsite.net/images/v1781118968/bostonpublicschoolsorg/n10whyxn8axn0urvgidh/FINALAIPolicy.pdf",
    },
    {
        "state": "Georgia",
        "level": "state",
        "title": "Leveraging AI in the K-12 Setting (Georgia Department of Education)",
        "url": "https://gystc.org/wp-content/uploads/2025/04/Leveraging-AI-in-the-K-12-Setting.pdf",
    },
    {
        "state": "Georgia",
        "level": "district",
        "title": "Position Statement on the Use of Artificial Intelligence (AI) (Atlanta Public Schools)",
        "url": "https://resources.finalsite.net/images/v1773083346/atlantapublicschoolsus/urglvv8r7nym56wp0yn2/FINALPositionStatementontheUseofArtificialIntelligenceAI.pdf",
    },
    {
        "state": "Georgia",
        "level": "district",
        "title": "AI Use Policies for Educators and Students (Draft, Taliaferro County School District)",
        "url": "https://www.taliaferro.k12.ga.us/AIPOLICY",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def is_pdf(url: str, content_type: str) -> bool:
    return url.lower().endswith(".pdf") or "application/pdf" in content_type.lower()


def extract_pdf_text(raw: bytes) -> str:
    text_parts = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_docx_text(raw: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in document.findall(".//w:p", namespace):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
        if text.strip():
            paragraphs.append(text)
    return "\n".join(paragraphs)


def extract_html_text(raw: bytes) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    main = soup.find("main") or soup.body or soup
    text = main.get_text(separator="\n")
    return text


def clean_text(text: str) -> str:
    # Keep the document's real line breaks (readable multi-line cells).
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    joined = "\n".join(lines)
    # Some PDFs render stylized cover-page titles with one space between
    # every letter (e.g. "A I G u i d e b o o k"). A run of 3+ single
    # letters separated by single spaces is never real prose, so collapse
    # it back into a normal word.
    joined = re.sub(
        r"(?<![A-Za-z])(?:[A-Za-z] ){2,}[A-Za-z](?![A-Za-z])",
        lambda m: m.group(0).replace(" ", ""),
        joined,
    )
    # Some viewers/import flows split CSV on every comma without honoring
    # quotes, so no literal ASCII comma can survive inside a cell. A plain
    # ";" is itself a common CSV delimiter candidate, and since full_text
    # contains hundreds-to-thousands of them per row (vs. a constant 7
    # structural commas), delimiter auto-detectors can mistake ";" for the
    # real delimiter and mis-parse/miscolor rows. Use a fullwidth comma
    # instead: reads naturally but is never treated as a delimiter.
    joined = joined.replace(",", "\uff0c")
    # A literal double-quote inside a field forces the CSV writer to escape
    # it as "" (valid RFC4180), but naive/regex-based column highlighters
    # just count quote characters instead of properly parsing quoted
    # fields, so any escaped quote mid-field throws off their column
    # detection for the rest of the line. Use a curly quote instead so no
    # field ever needs internal escaping.
    return joined.replace('"', "\u201d")


def fetch_full_text(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")
    if is_pdf(url, content_type):
        raw_text = extract_pdf_text(resp.content)
    elif url.lower().endswith(".docx") or "wordprocessingml.document" in content_type.lower():
        raw_text = extract_docx_text(resp.content)
    else:
        raw_text = extract_html_text(resp.content)
    return clean_text(raw_text)


def main() -> None:
    rows = []
    for source in SOURCES:
        state = source["state"]
        level = source["level"]
        url = source["url"]
        print(f"Scraping {state} ({level}): {url}")
        try:
            full_text = fetch_full_text(url)
            status = "ok" if len(full_text) > 200 else "warning_short_text"
        except Exception as exc:
            full_text = ""
            status = f"error: {exc}"
            print(f"  FAILED: {exc}")

        rows.append(
            {
                "state": state,
                "level": level,
                "title": source["title"].replace(",", "\uff0c"),
                "source_url": url,
                "date_retrieved": date.today().isoformat(),
                "status": status,
                "char_count": len(full_text),
                "full_text": full_text,
            }
        )
        print(f"  -> {len(full_text)} characters extracted ({status})")

    out_path = "k12_ai_policies.csv"
    # utf-8-sig adds a BOM so Excel reliably detects UTF-8 + comma delimiter;
    # QUOTE_ALL wraps every field (including ones with commas) in quotes so
    # any RFC4180-compliant reader keeps commas inside full_text as text.
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "state",
                "level",
                "title",
                "source_url",
                "date_retrieved",
                "status",
                "char_count",
                "full_text",
            ],
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
