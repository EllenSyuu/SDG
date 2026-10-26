"""Re-render every image in docs/img from synthetic data (light and dark themes).

    python scripts/render_assets.py

Nothing here reads real data: the generator writes synthetic releases to build/assets,
the pipeline runs on them, and only the resulting figures are copied into docs/img.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import polars as pl

from sdg4_revisions import io, pipeline, plots
from sdg4_revisions.config import load_settings
from sdg4_revisions.synthetic import generate
from sdg4_revisions.taxonomy import load_taxonomy

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"


def animate_figures(
    tables: dict[str, pl.DataFrame], planted: pl.DataFrame, names: dict[str, str], theme: str
) -> None:
    """Animated GIF companions of the README figures (same layout as the PNGs)."""
    present = set(tables["vintage_curves"]["code"].unique().to_list())
    headline = [c for c in pipeline.HEADLINE_CODES if c in present]
    ordered = [c for c in names if c in present]
    jobs = {
        "vintage_curves": lambda buf, p: plots.vintage_curves(
            tables["vintage_curves"], names, headline, buf, progress=p
        ),
        "flow_bars": lambda buf, p: plots.flow_bars(
            tables["transition_summary"], names, ordered, buf, progress=p
        ),
        "value_revisions": lambda buf, p: plots.value_revisions(
            tables["value_revisions"], names, ordered, buf, progress=p
        ),
        "ground_truth": lambda buf, p: plots.ground_truth(
            tables["series_transitions"], planted, buf, progress=p
        ),
    }
    for name, render in jobs.items():
        plots.set_theme(theme)
        plots.animate(render, IMG / f"{name}-{theme}.gif")


def main() -> None:
    settings = load_settings(ROOT / "config" / "demo.yaml")
    work = ROOT / "build" / "assets"
    if work.exists():
        shutil.rmtree(work)
    settings = settings.model_copy(
        update={
            "paths": settings.paths.model_copy(
                update={
                    "raw_dir": work / "raw",
                    "processed_dir": work / "processed",
                    "population_file": work / "raw" / "wpp" / "total_population_by_sex.csv",
                    "figures_dir": IMG,
                    "tables_dir": work / "tables",
                }
            )
        }
    )
    truth = generate(settings.paths.raw_dir)
    taxonomy = load_taxonomy(settings.paths.indicators_file)
    panel = io.build_panel(settings, taxonomy)
    population = io.read_population(settings.paths.population_file)  # type: ignore[arg-type]
    tables = pipeline.compute_tables(panel, settings, population)

    planted = pl.DataFrame([vars(t) for t in truth.transitions])
    IMG.mkdir(parents=True, exist_ok=True)
    for theme in ("light", "dark"):
        pipeline.make_figures(tables, taxonomy, settings, theme=theme, suffix=f"-{theme}")
        plots.set_theme(theme)
        plots.ground_truth(tables["series_transitions"], planted, IMG / f"ground_truth-{theme}.png")
        names = {i.code: i.name for i in taxonomy.indicators}
        plots.hero_animation(
            tables["vintage_curves"], names, pipeline.HERO_CODE, IMG / f"hero-{theme}.gif"
        )
        animate_figures(tables, planted, names, theme)
    plots.set_theme("light")
    plots.social_card(tables["vintage_curves"], pipeline.HERO_CODE, IMG / "social-preview.png")
    for path in sorted([*IMG.glob("*.png"), *IMG.glob("*.gif")]):
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
