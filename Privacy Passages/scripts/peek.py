import csv, sys
csv.field_size_limit(10**9)
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8-sig")))
n = int(sys.argv[2])
for i in map(int, sys.argv[3].split(",")):
    r = rows[i]
    print(f"\n##### [{i}] {r['title']} ({r['char_count']} chars)\n{r['full_text'][:n]}")
