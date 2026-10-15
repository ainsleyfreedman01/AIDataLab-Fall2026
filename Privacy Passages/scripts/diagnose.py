"""For each mismatched block, show where the quote diverges from the source text."""
import json, re, sys, unicodedata
work, rows = sys.argv[1], [int(r) for r in sys.argv[2].split(",")]


def norm_map(s):
    """Normalized alnum string plus index map back into s."""
    out, idx = [], []
    for i, ch in enumerate(s):
        for c in unicodedata.normalize("NFKC", ch).lower():
            if c.isascii() and c.isalnum():
                out.append(c); idx.append(i)
    return "".join(out), idx


for row in rows:
    spec = json.load(open(f"{work}/specs/{row:03d}.json", encoding="utf-8"))
    src = open(f"{work}/text/{row:03d}.txt", encoding="utf-8").read()
    ns, idx = norm_map(src)
    for sec in spec["sections"]:
        for b in sec["blocks"]:
            t = b["text"].replace("**", "")
            if t.startswith("[graphic]") or b["type"] == "subhead":
                continue
            for frag in re.split(r"…|\.\.\.", t):
                nf, fidx = norm_map(frag)
                if len(nf) < 12 or nf in ns:
                    continue
                # longest matching prefix
                lo, hi = 12, len(nf)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if nf[:mid] in ns: lo = mid
                    else: hi = mid - 1
                pos = ns.find(nf[:lo])
                end = idx[pos + lo - 1] if pos >= 0 else 0
                print(f"\n[{row}] {sec['heading']}")
                print("  QUOTE continues:", repr(frag[fidx[min(lo, len(fidx)-1)] - 40:fidx[min(lo, len(fidx)-1)] + 80]))
                print("  SOURCE has     :", repr(src[end - 40:end + 120]))
