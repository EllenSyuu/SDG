"""End-to-end orchestration: raw releases -> panel -> tables -> figures -> summary."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from sdg4_revisions import analysis, io, plots
from sdg4_revisions.config import Settings
from sdg4_revisions.taxonomy import Taxonomy, load_taxonomy

HEADLINE_CODES = ["4.1.2", "4.1.3", "4.1.4", "4.1.5", "4.c.1", "1.a.2"]
HERO_CODE = "4.c.1"


@dataclass
class RunResult:
    panel_rows: int
    tables: dict[str, Path] = field(default_factory=dict)
    figures: dict[str, Path] = field(default_factory=dict)
    seconds: float = 0.0


def compute_tables(
    panel: pl.DataFrame, settings: Settings, population: pl.DataFrame | None
) -> dict[str, pl.DataFrame]:
    obs = analysis.observations(panel, settings)
    flows = analysis.transition_flows(obs, settings) if len(settings.releases) > 1 else None
    tables = {
        "vintage_curves": analysis.vintage_curves(obs, settings),
        "expanding_coverage": analysis.expanding_coverage(obs, settings),
        "rolling_coverage": analysis.rolling_coverage(obs, settings, population),
        "source_layers": analysis.source_layers(panel, settings),
    }
    if flows is not None:
        tables["transition_flows"] = flows
        tables["transition_summary"] = analysis.transition_summary(flows)
        tables["value_revisions"] = analysis.value_revisions(panel, settings)
        tables["series_transitions"] = analysis.series_transitions(panel, settings)
    return tables


def run(settings: Settings, taxonomy: Taxonomy | None = None, figures: bool = True) -> RunResult:
    start = time.perf_counter()
    taxonomy = taxonomy or load_taxonomy(settings.paths.indicators_file)
    panel = io.build_panel(settings, taxonomy)
    io.write_panel(panel, settings)

    population = None
    if settings.paths.population_file and settings.paths.population_file.exists():
        population = io.read_population(settings.paths.population_file)

    tables = compute_tables(panel, settings, population)
    result = RunResult(panel_rows=panel.height)
    settings.paths.tables_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        path = settings.paths.tables_dir / f"{name}.csv"
        frame.write_csv(path, float_precision=4)
        result.tables[name] = path

    if figures:
        result.figures = make_figures(tables, taxonomy, settings)

    result.seconds = time.perf_counter() - start
    write_summary(panel, tables, settings, result)
    return result


def make_figures(
    tables: dict[str, pl.DataFrame],
    taxonomy: Taxonomy,
    settings: Settings,
    theme: str = "light",
    suffix: str = "",
) -> dict[str, Path]:
    """Render every figure in one theme; ``suffix`` is appended to file stems."""
    plots.set_theme(theme)
    out = settings.paths.figures_dir
    out.mkdir(parents=True, exist_ok=True)
    names = {i.code: i.name for i in taxonomy.indicators}
    present = set(tables["vintage_curves"]["code"].unique().to_list())
    headline = [c for c in HEADLINE_CODES if c in present] or sorted(present)
    ordered = [c for c in taxonomy.codes if c in present]
    hero_code = HERO_CODE if HERO_CODE in present else headline[0]
    figures = {
        "hero": plots.hero(tables["vintage_curves"], names, hero_code, out / f"hero{suffix}.png"),
        "vintage_curves": plots.vintage_curves(
            tables["vintage_curves"], names, headline, out / f"vintage_curves{suffix}.png"
        ),
        "source_layers": plots.source_layers(
            tables["source_layers"],
            names,
            max(settings.release_years),
            out / f"source_layers{suffix}.png",
        ),
    }
    if "transition_flows" in tables:
        figures["transition_flows"] = plots.transition_heatmap(
            tables["transition_flows"], names, ordered, out / f"transition_flows{suffix}.png"
        )
        figures["value_revisions"] = plots.value_revisions(
            tables["value_revisions"], names, ordered, out / f"value_revisions{suffix}.png"
        )
    plots.set_theme("light")
    return figures


def write_summary(
    panel: pl.DataFrame, tables: dict[str, pl.DataFrame], settings: Settings, result: RunResult
) -> Path:
    summary: dict[str, object] = {
        "releases": settings.releases,
        "panel_rows": panel.height,
        "series": panel["series_id"].n_unique(),
        "countries": panel["country"].n_unique(),
        "indicators": panel["code"].n_unique(),
        "runtime_seconds": round(result.seconds, 2),
    }
    if "transition_summary" in tables:
        totals = (
            tables["transition_summary"]
            .select(pl.col("added", "dropped", "retained").sum())
            .row(0, named=True)
        )
        summary["coverage_revisions"] = totals
        revisions = tables["value_revisions"]
        summary["value_revisions"] = {
            "pairs_compared": int(revisions["n_pairs"].sum()),
            "share_revised": round(
                float(
                    revisions.select(
                        (pl.col("share_revised") * pl.col("n_pairs")).sum()
                        / pl.col("n_pairs").sum()
                    ).item()
                ),
                4,
            ),
        }
    path = settings.paths.tables_dir / "summary.json"
    path.write_text(json.dumps(summary, indent=2, default=int), encoding="utf-8")
    return path
