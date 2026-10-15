"""Download every source_url in the CSV; record linked docs on HTML pages."""
import csv, json, re, sys, os
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

CSV_PATH, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
csv.field_size_limit(10**9)
rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8-sig")))

DOC_LINK = re.compile(r"\.pdf|\.docx?|docs\.google\.com|drive\.google\.com|/download|sharepoint|canva\.com|flipsnack|issuu", re.I)


def kind(url, ctype, raw):
    if raw[:4] == b"%PDF":
        return "pdf"
    if raw[:2] == b"PK":
        return "docx"
    if "text/plain" in ctype:
        return "txt"
    return "html"


def fetch(i):
    url = rows[i]["source_url"]
    rec = {"i": i, "url": url}
    try:
        r = requests.get(url, headers=HEADERS, timeout=90)
        r.raise_for_status()
        k = kind(url, r.headers.get("Content-Type", ""), r.content)
        path = os.path.join(OUT, f"{i:03d}.{k}")
        open(path, "wb").write(r.content)
        rec.update(kind=k, path=path, status=r.status_code, size=len(r.content))
        if k == "html":
            soup = BeautifulSoup(r.content, "html.parser")
            links = []
            for a in soup.find_all(["a", "iframe", "embed", "object"]):
                href = a.get("href") or a.get("src") or a.get("data")
                if href and DOC_LINK.search(href):
                    links.append({"text": a.get_text(" ", strip=True)[:120], "href": urljoin(r.url, href)})
            rec["links"] = links
    except Exception as e:
        rec["error"] = repr(e)[:300]
    return rec


with ThreadPoolExecutor(12) as ex:
    manifest = list(ex.map(fetch, range(len(rows))))
json.dump(manifest, open(os.path.join(OUT, "..", "manifest.json"), "w"), indent=1)
print(sum("error" in m for m in manifest), "errors")
from collections import Counter
print(Counter(m.get("kind") for m in manifest))
