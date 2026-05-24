"""Build docs/index.html: an interactive map of the candidate homes.

Reads data/candidates.json (always) and data/enrichment.json (if present, to color by
the analyst verdict and show it in popups). Markers are colored by score; clicking one
shows price, beds/baths, acres, and the analyst verdict. The output is a single
self-contained HTML file suitable for GitHub Pages.

Usage:
    python scripts/build_dashboard.py
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import folium

CANDIDATES = Path("data/candidates.json")
ENRICHMENT = Path("data/enrichment.json")
OUT = Path("docs/index.html")


def _load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def _color(score: float) -> str:
    if score >= 70:
        return "green"
    if score >= 45:
        return "orange"
    return "red"


def _popup(home: dict, enr: dict | None) -> str:
    price = f"${home['price']:,.0f}" if home.get("price") else "n/a"
    rows = [
        f"<b>{home.get('address', 'Unknown')}</b>",
        f"Score: {home.get('score', '?')}/100",
        f"{price} &middot; {home.get('bedrooms') or '?'}bd/"
        f"{home.get('bathrooms') or '?'}ba &middot; {home.get('acres') or '?'} ac",
    ]
    if enr:
        rows.append(f"Analyst: {enr.get('qual_score', '?')}/10 "
                    f"({enr.get('deal_breaker_status', '?')})")
        if enr.get("verdict"):
            rows.append(f"<i>{enr['verdict']}</i>")
    return "<br>".join(rows)


def main() -> int:
    data = _load(CANDIDATES, {"candidates": []})
    homes = data.get("candidates", [])
    enrichment = {e.get("id"): e for e in _load(ENRICHMENT, [])}

    located = [h for h in homes if h.get("lat") and h.get("lon")]
    if located:
        center = [
            sum(h["lat"] for h in located) / len(located),
            sum(h["lon"] for h in located) / len(located),
        ]
        zoom = 11
    else:
        center, zoom = [30.5, -97.8], 9  # Austin metro fallback

    m = folium.Map(location=center, zoom_start=zoom, tiles="cartodbpositron")

    title = (f"<h3 style='font-family:sans-serif'>Home shortlist "
             f"&middot; {len(homes)} candidates &middot; "
             f"{dt.date.today().isoformat()}</h3>")
    m.get_root().html.add_child(folium.Element(title))

    for h in located:
        enr = enrichment.get(h.get("id"))
        score = h.get("score", 0)
        if enr and enr.get("deal_breaker_status") == "eliminate":
            color = "black"
        else:
            color = _color(score)
        folium.CircleMarker(
            location=[h["lat"], h["lon"]],
            radius=8,
            color=color,
            fill=True,
            fill_opacity=0.85,
            popup=folium.Popup(_popup(h, enr), max_width=320),
            tooltip=f"{score}/100",
        ).add_to(m)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(OUT))
    print(f"Wrote {OUT} with {len(located)} mapped homes "
          f"({len(homes) - len(located)} lacked coordinates).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
