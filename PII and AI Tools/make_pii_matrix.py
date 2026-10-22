"""District x PII-term grid: which terms each district's AI policy names, with the evidence.

Reads the outputs of build_pii_tools.py and writes:
  pii_district_matrix.csv   one row per district, one column per term; a cell holds the page/section
                            where the term appears (blank = not named)
  pii_district_matrix.html  interactive grid; click any cell for the quote, PDF, location and how it
                            was decided. Also lists districts with no terms and every rejected match.
  pii_district_matrix.png   static grid
"""
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

import plotly.graph_objects as go

from build_pii_tools import CATS, PATTERNS

HERE = Path(__file__).parent
LABEL_KEY = {label: k for k, (label, _) in CATS.items()}


def read(name):
    return list(csv.DictReader(open(HERE / name, encoding="utf-8-sig")))


def mark_term(quote, label):
    """HTML-escape the quote and highlight the words that matched the term's pattern."""
    m = PATTERNS[LABEL_KEY[label]].search(quote)
    if not m:
        return html.escape(quote)
    a, b = m.span()
    return html.escape(quote[:a]) + "<mark>" + html.escape(quote[a:b]) + "</mark>" + html.escape(quote[b:])


def main():
    orgs = [r for r in read("pii_spectrum_by_organization.csv") if r["level"] == "district"]
    docs = read("pii_and_tools_by_document.csv")
    evidence = [e for e in read("evidence.csv") if e["type"] == "PII item" and e["level"] == "district"]
    rejected = read("pii_rejected_matches.csv")

    # cell -> every document that supports it (a district can have several)
    cells = defaultdict(list)
    for e in evidence:
        cells[(e["organization"], e["item"])].append({
            "pdf": e["pdf_file"], "location": e["location"], "how": e["how_decided"],
            "quote": mark_term(e["quote"], e["item"])})

    named = sorted((o for o in orgs if int(o["pii_item_count"]) > 0),
                   key=lambda o: (-int(o["pii_item_count"]), o["organization"]))
    none = sorted((o for o in orgs if int(o["pii_item_count"]) == 0), key=lambda o: o["organization"])
    term_n = {label: sum((o["organization"], label) in cells for o in named) for label, _ in CATS.values()}
    terms = sorted(term_n, key=lambda t: (-term_n[t], list(LABEL_KEY).index(t)))

    # Why each zero-term district has no terms: its documents' definition level
    level_by_org = defaultdict(set)
    for d in docs:
        if d["level"] == "district" and d["pdf_file"]:
            level_by_org[d["organization"]].add(d["pii_definition_level"])
    no_pdf = sorted({d["organization"] for d in docs if d["level"] == "district"} - {o["organization"] for o in orgs})

    # ---- CSV: cells hold the location so every 1 is traceable
    with open(HERE / "pii_district_matrix.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["district", "state", "pii_terms"] + terms)
        for o in named + none:
            w.writerow([o["organization"], o["state"], o["pii_item_count"]] +
                        [" || ".join(f'{c["pdf"]}: {c["location"]}' for c in cells.get((o["organization"], t), []))
                         for t in terms])

    # ---- HTML
    data = {
        "terms": terms, "termN": [term_n[t] for t in terms],
        "rows": [{"name": o["organization"], "state": o["state"], "n": int(o["pii_item_count"]),
                  "docs": int(o["documents"])} for o in named],
        "cells": {f"{org}||{t}": v for (org, t), v in cells.items()},
    }
    none_rows = "".join(
        f"<tr><td>{html.escape(o['organization'])}</td><td>{html.escape(o['state'])}</td>"
        f"<td>{html.escape('; '.join(sorted(level_by_org[o['organization']])))}</td></tr>" for o in none)
    rej_rows = "".join(
        f"<tr><td>{html.escape(r['organization'])}</td><td>{html.escape(r['pii_item'])}</td>"
        f"<td>{html.escape(r['reason_rejected'])}</td><td class='q'>{mark_term(r['rejected_quote'], r['pii_item'])}"
        f"<div class='src'>{html.escape(r['pdf_file'])} · {html.escape(r['location'])}</div></td></tr>"
        for r in sorted(rejected, key=lambda r: (r["pii_item"], r["organization"])))
    n_auto = sum(1 for e in evidence if e["how_decided"].startswith("pattern"))
    n_hand = sum(1 for e in evidence if e["how_decided"].startswith("added"))
    page = (TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__NAMED__", str(len(named))).replace("__TOTAL__", str(len(orgs)))
            .replace("__NONE__", str(len(none))).replace("__NOPDF__", str(len(no_pdf)))
            .replace("__NOPDFLIST__", html.escape(", ".join(no_pdf)))
            .replace("__NAUTO__", str(n_auto)).replace("__NHAND__", str(n_hand))
            .replace("__NREJ__", str(len(rejected))).replace("__NONEROWS__", none_rows)
            .replace("__REJROWS__", rej_rows))
    (HERE / "pii_district_matrix.html").write_text(page, encoding="utf-8")

    # ---- PNG
    z = [[1 if (o["organization"], t) in cells else 0 for t in terms] for o in named]
    ylab = [f"{o['organization']} ({o['pii_item_count']})" for o in named]
    xlab = [f"{t} ({term_n[t]})" for t in terms]
    fig = go.Figure(go.Heatmap(z=z, x=xlab, y=ylab, colorscale=[[0, "#efeee9"], [1, "#2a78d6"]],
                               showscale=False, xgap=2, ygap=2, hoverinfo="skip"))
    fig.update_layout(
        title=dict(text=(f"Which PII terms does each district's AI policy name?<br><sup>{len(named)} of "
                         f"{len(orgs)} districts name at least one term (blue = named). Counts in parentheses. "
                         f"The {len(none)} districts naming no terms are not shown.</sup>"),
                   x=0.01, y=0.975, yref="container", yanchor="top", font=dict(size=18, color="#0b0b0b")),
        xaxis=dict(side="top", tickangle=-55, tickfont=dict(size=11, color="#0b0b0b")),
        yaxis=dict(autorange="reversed", tickfont=dict(size=11, color="#0b0b0b")),
        plot_bgcolor="#fcfcfb", paper_bgcolor="#fcfcfb", width=1250, height=19 * len(named) + 480,
        margin=dict(l=10, r=20, t=400, b=20), font=dict(family="Segoe UI, Arial, sans-serif"))
    fig.write_image(HERE / "pii_district_matrix.png", scale=2)
    print(f"{len(named)} districts with terms, {len(none)} with none, {len(no_pdf)} without a privacy PDF; "
          f"{len(evidence)} evidence cells, {len(rejected)} rejected matches")


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>District PII Terms</title>
<style>
:root{--surface:#fcfcfb;--panel:#f4f3ef;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;--line:#e2e1dc;
 --on:#2a78d6;--off:#efeee9;--mark:#fde9a8;--focus:#0b0b0b}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--surface:#1a1a19;--panel:#242422;--ink:#f0efec;
 --ink2:#c3c2b7;--muted:#8f8e86;--line:#383835;--on:#3987e5;--off:#2c2c2a;--mark:#6b5a1e;--focus:#f0efec}}
:root[data-theme="dark"]{--surface:#1a1a19;--panel:#242422;--ink:#f0efec;--ink2:#c3c2b7;--muted:#8f8e86;
 --line:#383835;--on:#3987e5;--off:#2c2c2a;--mark:#6b5a1e;--focus:#f0efec}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--ink);font:14px/1.5 "Segoe UI",system-ui,sans-serif}
main{max-width:1400px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:40px 0 8px}
p,li{color:var(--ink2);max-width:880px}
.method{background:var(--panel);border-radius:8px;padding:12px 16px;margin:16px 0}
.method li{margin:2px 0}
.wrap{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap}
.gridbox{overflow:auto;max-height:80vh;border:1px solid var(--line);border-radius:8px;flex:1 1 640px}
table.grid{border-collapse:separate;border-spacing:0}
.grid th{position:sticky;background:var(--surface);font-weight:500;color:var(--ink);z-index:1}
.grid thead th{top:0;height:210px;vertical-align:bottom;padding:0 0 6px;min-width:22px;max-width:22px}
.grid thead th div{writing-mode:vertical-rl;transform:rotate(180deg);white-space:nowrap;font-size:12px;margin:0 auto}
.grid thead th .n{color:var(--muted)}
.grid th.row{left:0;text-align:right;padding:0 10px 0 8px;white-space:nowrap;font-size:12.5px;z-index:2}
.grid thead th.corner{left:0;z-index:3}
.grid td{padding:1px}
.grid td.cnt{color:var(--ink2);font-size:12px;padding:0 8px;text-align:right;font-variant-numeric:tabular-nums}
.cell{width:20px;height:18px;border-radius:3px;background:var(--off);border:0;padding:0;display:block}
.cell.on{background:var(--on);cursor:pointer}
.cell.on:hover,.cell.on:focus-visible{outline:2px solid var(--focus);outline-offset:1px}
.cell.sel{outline:2px solid var(--focus);outline-offset:1px}
tr:hover th.row{color:var(--on)}
aside{flex:0 1 380px;position:sticky;top:12px;background:var(--panel);border-radius:8px;padding:14px 16px;min-height:160px}
aside h3{margin:0 0 2px;font-size:15px}aside .sub{color:var(--ink2);margin-bottom:10px}
.ev{border-top:1px solid var(--line);padding:10px 0}
.q{font-family:Georgia,serif;color:var(--ink)}
mark{background:var(--mark);color:inherit;padding:0 1px;border-radius:2px}
.src{color:var(--muted);font:12px/1.4 "Segoe UI",system-ui,sans-serif;margin-top:4px}
.how{display:inline-block;font-size:11.5px;color:var(--ink2);border:1px solid var(--line);border-radius:10px;padding:0 8px;margin-top:4px}
.key{display:flex;gap:16px;align-items:center;color:var(--ink2);margin:8px 0}
.key span{display:inline-flex;align-items:center;gap:6px}
.key i{width:14px;height:12px;border-radius:3px;display:inline-block}
table.list{border-collapse:collapse;width:100%;max-width:1200px}
.list th,.list td{text-align:left;border-bottom:1px solid var(--line);padding:6px 8px;vertical-align:top}
.list th{color:var(--ink2);font-weight:600}
details summary{cursor:pointer;color:var(--ink);font-weight:600;margin:6px 0}
@media (max-width:700px){aside{position:static;flex-basis:100%}}
</style></head><body><main>
<h1>Which PII terms does each district's AI policy name?</h1>
<p>__NAMED__ of __TOTAL__ districts with privacy passages name at least one specific kind of personal
information. Rows are districts, ordered by how many terms they name; columns are terms, ordered by how many
districts name them. <strong>Click any blue cell</strong> to see the exact words in the policy, and where they are.</p>

<div class="method"><strong>How each cell was decided</strong>
<ul>
<li>Source text: the privacy passages in <code>Privacy Passages/*.pdf</code>, quoted from each district's own documents.
 A district with several documents is one row; a term counts if any of its documents names it.</li>
<li>A term is searched for only in text near PII, confidential-data, or "do not enter/share" language, so a
 word used for another reason elsewhere in a policy doesn't count.</li>
<li>Every match was read. __NAUTO__ cells come from pattern matches confirmed by reading; __NHAND__ were added by hand
 because the wording had no pattern. __NREJ__ matches (district and state documents) were rejected; each is listed
 below with its reason.</li>
<li>"Named" means the policy lists it as personal or confidential data to protect, including lists labelled
 "confidential" or "sensitive" and descriptions of laws (e.g. FERPA protecting education records).</li>
</ul></div>

<div class="key"><span><i style="background:var(--on)"></i>names this term</span>
<span><i style="background:var(--off)"></i>does not name it</span></div>

<div class="wrap">
<div class="gridbox"><table class="grid" id="grid"></table></div>
<aside id="detail" aria-live="polite"><h3>Click a blue cell</h3>
<div class="sub">The quote, PDF, page/section, and how it was decided will appear here.</div></aside>
</div>

<h2>Districts that name no specific terms (__NONE__)</h2>
<p>These have privacy passages but never say what counts as personal information. "General mention only" means
they say something like "don't enter PII" without listing anything.
__NOPDF__ more districts had no privacy passages at all: __NOPDFLIST__.</p>
<details><summary>Show the list</summary>
<table class="list"><thead><tr><th>District</th><th>State</th><th>What their privacy passages contain</th></tr></thead>
<tbody>__NONEROWS__</tbody></table></details>

<h2>Rejected matches (__NREJ__)</h2>
<p>Places where a term's pattern matched but reading the passage showed it was not naming personal data.
These are <em>not</em> counted in the grid.</p>
<details><summary>Show all rejected matches</summary>
<table class="list"><thead><tr><th>Organization</th><th>Term</th><th>Why rejected</th><th>Rejected text</th></tr></thead>
<tbody>__REJROWS__</tbody></table></details>
</main>
<script>
const D = __DATA__;
const esc = s => s.replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const g = document.getElementById("grid"), det = document.getElementById("detail");
let head = '<thead><tr><th class="corner row"></th>' +
  D.terms.map((t,i) => `<th scope="col"><div>${esc(t)} <span class="n">(${D.termN[i]})</span></div></th>`).join("") +
  '<th></th></tr></thead><tbody>';
g.innerHTML = head + D.rows.map((r,ri) => `<tr><th class="row" scope="row">${esc(r.name)}</th>` +
  D.terms.map((t,ti) => {
    const on = D.cells[r.name + "||" + t];
    return on ? `<td><button class="cell on" data-r="${ri}" data-t="${ti}" aria-label="${esc(r.name)} names ${esc(t)}"></button></td>`
              : `<td><span class="cell" title="${esc(r.name)} does not name ${esc(t)}"></span></td>`;
  }).join("") + `<td class="cnt">${r.n}</td></tr>`).join("") + "</tbody>";
let sel = null;
g.addEventListener("click", e => {
  const b = e.target.closest(".cell.on"); if (!b) return;
  if (sel) sel.classList.remove("sel"); sel = b; b.classList.add("sel");
  const r = D.rows[+b.dataset.r], t = D.terms[+b.dataset.t], ev = D.cells[r.name + "||" + t];
  det.innerHTML = `<h3>${esc(r.name)}</h3><div class="sub">${esc(r.state)} · names <strong>${esc(t)}</strong>` +
    ` · ${r.n} terms in total</div>` + ev.map(c => `<div class="ev"><div class="q">${c.quote}</div>` +
    `<div class="src">${esc(c.pdf)}<br>${esc(c.location)}</div><span class="how">${esc(c.how)}</span></div>`).join("");
});
g.addEventListener("mouseover", e => {
  const b = e.target.closest(".cell.on"); if (b) b.title = D.rows[+b.dataset.r].name + " — " + D.terms[+b.dataset.t] + " (click for the quote)";
});
</script></body></html>
"""

if __name__ == "__main__":
    main()
