"""Group rows into agent batches of roughly equal text size (big docs alone)."""
import json, os, sys
work = sys.argv[1]
target = int(sys.argv[2]) if len(sys.argv) > 2 else 250_000
sizes = sorted(((os.path.getsize(os.path.join(work, "text", f)), int(f[:3]))
                for f in os.listdir(os.path.join(work, "text")) if int(f[:3]) != 100), reverse=True)
batches = []
for size, row in sizes:
    for b in batches:
        if b["size"] + size <= target and len(b["rows"]) < 8:
            b["rows"].append(row); b["size"] += size
            break
    else:
        batches.append({"rows": [row], "size": size})
for b in batches:
    b["rows"].sort()
print(json.dumps([b["rows"] for b in batches]))
print(len(batches), [b["size"] for b in batches], file=sys.stderr)
