"""Parse wishlist.md into a structured config.

The wishlist is human-authored markdown with one fenced ```yaml block holding the
hard filters and scoring weights. We parse only that block here; the prose sections
are read by the Claude subagents, not by this code.

We avoid a YAML dependency by parsing the small, flat schema ourselves. The block is
simple enough (scalars, one-level lists, one nested `weights` map) that a tiny parser
keeps the project dependency-light and the parsing transparent.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Wishlist:
    zip_codes: list[str]
    region: str | None
    center: str | None
    center_lat: float | None
    center_lon: float | None
    radius_miles: float | None
    prefer_near: str | None
    prefer_lat: float | None
    prefer_lon: float | None
    acres_sweet_min: float | None
    acres_sweet_max: float | None
    price_min: float
    price_max: float
    bedrooms_min: float
    bathrooms_min: float
    acres_min: float
    property_types: list[str]
    max_days_on_market: int | None
    weights: dict[str, float]
    enrich_top_n: int
    raw_markdown: str = field(repr=False, default="")

    @property
    def search_mode(self) -> str:
        """'radius' if a geocoded center + radius is set, else 'zips'."""
        if self.center_lat is not None and self.center_lon is not None and self.radius_miles:
            return "radius"
        return "zips"


def _coerce(value: str):
    """Turn a YAML scalar/list literal into a Python value."""
    value = value.strip()
    if value in ("null", "~", ""):
        return None
    # Lists and quoted strings are valid Python literals.
    if value.startswith("[") or value.startswith('"') or value.startswith("'"):
        return ast.literal_eval(value)
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _extract_yaml_block(md: str) -> str:
    m = re.search(r"```ya?ml\s*\n(.*?)```", md, re.DOTALL)
    if not m:
        raise ValueError("wishlist.md has no ```yaml block")
    return m.group(1)


def _parse_block(block: str) -> dict:
    """Parse the flat schema with a single nested `weights` map."""
    out: dict = {}
    weights: dict[str, float] = {}
    in_weights = False
    for raw in block.splitlines():
        line = raw.split("#", 1)[0].rstrip()  # strip inline comments
        if not line.strip():
            continue
        indented = line[0] in " \t"
        stripped = line.strip()
        if not indented:
            in_weights = False
        if stripped == "weights:":
            in_weights = True
            continue
        if ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key = key.strip()
        if in_weights and indented:
            weights[key] = float(_coerce(val))
        else:
            out[key] = _coerce(val)
    out["weights"] = weights
    return out


def load_wishlist(path: str | Path = "wishlist.md") -> Wishlist:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not found. Copy wishlist.example.md to wishlist.md and edit it."
        )
    md = p.read_text()
    parsed = _parse_block(_extract_yaml_block(md))
    zips = [str(z) for z in (parsed.get("zip_codes") or [])]
    region = parsed.get("region") or None
    center = parsed.get("center") or None
    center_lat = parsed.get("center_lat")
    center_lon = parsed.get("center_lon")
    radius = parsed.get("radius_miles")
    has_radius = center_lat is not None and center_lon is not None and radius
    if not zips and not region and not has_radius and not center:
        raise ValueError(
            "wishlist.md needs a search area: zip_codes, a region, or a center + "
            "radius_miles for a skill to resolve."
        )
    return Wishlist(
        zip_codes=zips,
        region=str(region) if region else None,
        center=str(center) if center else None,
        center_lat=float(center_lat) if center_lat is not None else None,
        center_lon=float(center_lon) if center_lon is not None else None,
        radius_miles=float(radius) if radius else None,
        prefer_near=str(parsed["prefer_near"]) if parsed.get("prefer_near") else None,
        prefer_lat=float(parsed["prefer_lat"]) if parsed.get("prefer_lat") is not None else None,
        prefer_lon=float(parsed["prefer_lon"]) if parsed.get("prefer_lon") is not None else None,
        acres_sweet_min=float(parsed["acres_sweet_min"]) if parsed.get("acres_sweet_min") is not None else None,
        acres_sweet_max=float(parsed["acres_sweet_max"]) if parsed.get("acres_sweet_max") is not None else None,
        price_min=float(parsed.get("price_min", 0) or 0),
        price_max=float(parsed.get("price_max", 0) or 0),
        bedrooms_min=float(parsed.get("bedrooms_min", 0) or 0),
        bathrooms_min=float(parsed.get("bathrooms_min", 0) or 0),
        acres_min=float(parsed.get("acres_min", 0) or 0),
        property_types=[str(t) for t in (parsed.get("property_types") or [])],
        max_days_on_market=parsed.get("max_days_on_market"),
        weights=parsed.get("weights") or {},
        enrich_top_n=int(parsed.get("enrich_top_n", 8) or 8),
        raw_markdown=md,
    )
