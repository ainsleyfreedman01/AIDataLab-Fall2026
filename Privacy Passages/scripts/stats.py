import csv, collections, sys
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8-sig")))
C = collections.Counter
print("status", C(r["status"] for r in rows))
print("level x status", C((r["level"], r["status"]) for r in rows))
print("method", C(r["access_method"].split(":")[0].split("(")[0].strip() for r in rows))
print("page", C(r["page_citation"] for r in rows))
import re
g = [int(m) for r in rows for m in re.findall(r"(\d+) \[graphic\] block", r["issues"])]
print("graphic rows", len(g), sum(g))
for r in rows:
    if r["output_pdf"].startswith("Illinois"):
        print("IL", r["output_pdf"], r["privacy_sections"], r["page_citation"], r["issues"][:400])
print("states", len({r["state"] for r in rows}))
