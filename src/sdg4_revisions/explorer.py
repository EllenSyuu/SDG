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

from sdg4_revisions import analysis, io
from sdg4_revisions.config import Settings
from sdg4_revisions.taxonomy import load_taxonomy


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


def _rows(frame: pl.DataFrame, columns: list[str]) -> list[list[object]]:
    """Compact column-ordered rows (floats rounded) for the JSON payload."""
    out = frame.select(columns).with_columns(pl.col(pl.Float64).round(4))
    return [list(row) for row in out.iter_rows()]


def export(settings: Settings, out: Path, planted: list[dict[str, int]] | None = None) -> Path:
    """Write everything the explorer page draws into one JSON file.

    ``planted`` is the synthetic generator's ledger; when given, the page shows it next
    to the pipeline's own counts and checks them against each other in the browser.
    """
    taxonomy = load_taxonomy(settings.paths.indicators_file)
    panel = io.read_panel(settings)
    obs = analysis.observations(panel, settings)
    present = set(obs["code"].unique().to_list())
    payload: dict[str, object] = {
        "reference_start": settings.reference_start,
        "reference_end": settings.reference_end,
        "eligibility": settings.eligibility.value,
        "releases": settings.release_years,
        "indicators": [
            {"code": i.code, "name": i.name, "target": i.target}
            for i in taxonomy.indicators
            if i.code in present
        ],
        "masks": encode(obs, settings.reference_start),
        "curves": _rows(
            analysis.vintage_curves(obs, settings), ["code", "release", "ref_year", "n_countries"]
        ),
    }
    if len(settings.releases) > 1:
        flows = analysis.transition_flows(obs, settings)
        payload["flows"] = _rows(flows, ["code", "from_release", "ref_year", "added", "dropped"])
        payload["revisions"] = _rows(
            analysis.value_revisions(panel, settings),
            ["code", "from_release", "n_pairs", "share_revised", "median_abs_revision"],
        )
        payload["ledger"] = _rows(
            analysis.series_transitions(panel, settings),
            ["from_release", "to_release", "retained", "backfilled", "retracted", "revised"],
        )
    if planted is not None:
        keys = ["from_release", "to_release", "retained", "backfilled", "retracted", "revised"]
        payload["planted"] = [[row[k] for k in keys] for row in planted]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return out
