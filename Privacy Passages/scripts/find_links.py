import sys, re
from bs4 import BeautifulSoup
path, pattern = sys.argv[1], re.compile(sys.argv[2], re.I)
soup = BeautifulSoup(open(path, "rb").read(), "html.parser")
for a in soup.find_all(["a", "iframe"]):
    t = a.get_text(" ", strip=True)
    h = a.get("href") or a.get("src") or ""
    if pattern.search(t) or pattern.search(h):
        print(repr(t[:80]), "->", h[:250])
