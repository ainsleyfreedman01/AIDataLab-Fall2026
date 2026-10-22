"""Rank districts by how many PII terms their policies list, and chart it.

Reads pii_spectrum_by_organization.csv (from build_pii_tools.py) and writes:
  pii_term_spectrum.csv    every district, ranked by number of PII terms
  pii_term_spectrum.html   interactive chart (hover a bar to see its terms)
  pii_term_spectrum.png    static chart
"""
import csv
from pathlib import Path

import plotly.graph_objects as go

HERE = Path(__file__).parent
BLUE, INK, INK_2, GRID, SURFACE = "#2a78d6", "#0b0b0b", "#52514e", "#e8e7e3", "#fcfcfb"
ABBR = {"Alabama": "AL", "Arkansas": "AR", "California": "CA", "Colorado": "CO", "Delaware": "DE", "Florida": "FL",
        "Georgia": "GA", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY",
        "Louisiana": "LA", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
        "Missouri": "MO", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
        "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
        "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
        "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Virginia": "VA", "Washington": "WA",
        "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"}


def main():
    rows = [r for r in csv.DictReader(open(HERE / "pii_spectrum_by_organization.csv", encoding="utf-8-sig"))
            if r["level"] == "district"]
    for r in rows:
        r["n"] = int(r["pii_item_count"])
    rows.sort(key=lambda r: (-r["n"], r["organization"]))

    # Ranked CSV (ties share a rank)
    out, rank = [], 0
    for i, r in enumerate(rows):
        if i == 0 or r["n"] != rows[i - 1]["n"]:
            rank = i + 1
        out.append({"rank": rank, "district": r["organization"], "state": r["state"],
                    "pii_terms": r["n"], "uses_term_PII": r["uses_term_PII"], "terms": r["pii_items"]})
    with open(HERE / "pii_term_spectrum.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    listed = [r for r in rows if r["n"] > 0][::-1]  # plotly draws bottom-up
    zero = len(rows) - len(listed)
    labels = [f"{r['organization']} ({ABBR.get(r['state'], r['state'])})" for r in listed]
    hover = [f"<b>{lab}</b><br>{r['n']} PII terms<br>" + "<br>".join(r["pii_items"].split("; "))
             for lab, r in zip(labels, listed)]

    fig = go.Figure(go.Bar(
        x=[r["n"] for r in listed], y=labels, orientation="h",
        marker=dict(color=BLUE, line=dict(color=SURFACE, width=1)),
        text=[r["n"] for r in listed], textposition="outside", textfont=dict(color=INK_2, size=11),
        hovertext=hover, hoverinfo="text", width=0.72,
    ))
    fig.update_layout(
        title=dict(
            text=(f"How many PII terms do district AI policies list?"
                  f"<br><sup>{len(listed)} of {len(rows)} districts name at least one specific item. "
                  f"The other {zero} only say \"don't share PII\" or never define it, so they aren't shown.</sup>"),
            x=0.01, font=dict(color=INK, size=18)),
        xaxis=dict(title="Number of distinct PII terms (of 29 categories)", dtick=2, gridcolor=GRID,
                   zeroline=False, color=INK_2, range=[0, max(r["n"] for r in listed) + 1.5]),
        yaxis=dict(color=INK, tickfont=dict(size=11), automargin=True),
        plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, bargap=0.25,
        margin=dict(l=10, r=30, t=90, b=50), height=22 * len(listed) + 160, width=1000,
        font=dict(family="Segoe UI, Arial, sans-serif"),
    )
    fig.write_html(HERE / "pii_term_spectrum.html", include_plotlyjs="cdn")
    fig.write_image(HERE / "pii_term_spectrum.png", scale=2)
    print(f"{len(rows)} districts ranked; {len(listed)} charted, {zero} with no specific terms")


if __name__ == "__main__":
    main()
