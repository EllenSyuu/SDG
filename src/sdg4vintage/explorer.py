"""Export a compact JSON for the static, client-side coverage explorer (docs/explorer).

Encoding: for each indicator and release, every country maps to an integer bitmask
whose bit *k* is set when the country has a value for ``reference_start + k``. The
whole 12-indicator x 4-release panel fits in a few tens of kilobytes, so the explorer
needs no server and can be hosted on GitHub Pages.
"""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from sdg4vintage import analysis, io
from sdg4vintage.config import Settings
from sdg4vintage.taxonomy import load_taxonomy


def encode(obs: pl.DataFrame, reference_start: int) -> dict[str, dict[str, dict[str, int]]]:
    masks = (
        obs.with_columns(
            pl.lit(2, dtype=pl.Int64)
            .pow(pl.col("ref_year").cast(pl.Int64) - reference_start)
            .cast(pl.Int64)
            .alias("bit")
        )
        .group_by(["code", "release", "country"])
        .agg(pl.col("bit").sum().alias("mask"))  # bits are distinct, so sum == bitwise OR
    )
    out: dict[str, dict[str, dict[str, int]]] = {}
    for code, release, country, mask in masks.sort(["code", "release", "country"]).iter_rows():
        out.setdefault(code, {}).setdefault(str(release), {})[country] = int(mask)
    return out


def export(settings: Settings, out: Path) -> Path:
    taxonomy = load_taxonomy(settings.paths.indicators_file)
    panel = io.read_panel(settings)
    obs = analysis.observations(panel, settings)
    payload = {
        "reference_start": settings.reference_start,
        "reference_end": settings.reference_end,
        "eligibility": settings.eligibility.value,
        "releases": settings.release_years,
        "indicators": [
            {"code": i.code, "name": i.name, "target": i.target} for i in taxonomy.indicators
        ],
        "masks": encode(obs, settings.reference_start),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return out
