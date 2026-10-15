import csv, json, sys
csv.field_size_limit(10**9)
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8-sig")))
man = json.load(open(sys.argv[2]))
for m in man:
    r = rows[m["i"]]
    if "error" in m:
        print(f"[{m['i']}] ERROR {r['title']} | {m['url']} | {m['error']}")
for m in man:
    if m.get("kind") != "html":
        continue
    r = rows[m["i"]]
    print(f"\n[{m['i']}] {r['state']} | {r['doc_type']} | chars={r['char_count']} | {r['title']}")
    seen = set()
    for l in m.get("links", []):
        if l["href"] in seen:
            continue
        seen.add(l["href"])
        print(f"    - {l['text'][:70]!r} -> {l['href'][:150]}")
